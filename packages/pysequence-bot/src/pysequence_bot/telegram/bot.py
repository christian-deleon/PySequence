"""Telegram bot for querying balances and transferring money via natural language."""

import asyncio
import json
import logging
import time
from collections import deque
from functools import partial

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ChatAction
from telegram.error import BadRequest
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from pysequence_sdk import SequenceClient, get_access_token
from pysequence_sdk.safeguards import AuditLog, DailyLimitTracker
from pysequence_bot.ai.agent import Agent
from pysequence_bot.ai.memory import MemoryStore
from pysequence_bot.ai.tools import _handle_confirm_transfer
from pysequence_bot.config import (
    AgentConfig,
    SdkConfig,
    TelegramConfig,
    get_sdk_config,
    load_config,
)

log = logging.getLogger(__name__)

# Per-user sliding window rate limiter: user_id -> deque of timestamps
_message_timestamps: dict[int, deque] = {}


def _is_rate_limited(user_id: int, max_messages: int, window_seconds: int) -> bool:
    """Check if a user has exceeded the message rate limit."""
    now = time.time()
    if user_id not in _message_timestamps:
        _message_timestamps[user_id] = deque()

    timestamps = _message_timestamps[user_id]

    # Remove timestamps outside the window
    while timestamps and now - timestamps[0] > window_seconds:
        timestamps.popleft()

    if len(timestamps) >= max_messages:
        return True

    timestamps.append(now)
    return False


class _AllowedUserFilter(filters.MessageFilter):
    """Only accept messages from allowed Telegram user IDs in the allowed group."""

    def __init__(self, allowed_user_ids: set[int], group_id: int) -> None:
        super().__init__()
        self._allowed_user_ids = allowed_user_ids
        self._group_id = group_id

    def filter(self, message: object) -> bool:
        user = getattr(message, "from_user", None)
        if user is None or user.id not in self._allowed_user_ids:
            return False
        chat = getattr(message, "chat", None)
        if chat is None:
            return False
        # Allow DMs with the bot or messages in the allowed group
        if chat.type == "private":
            return True
        return chat.id == self._group_id


async def _keep_typing(chat) -> None:
    """Send typing indicator every 4 seconds until cancelled."""
    try:
        while True:
            await chat.send_action(ChatAction.TYPING)
            await asyncio.sleep(4)
    except asyncio.CancelledError:
        pass


async def _send_response(chat, text: str) -> None:
    """Send a message with Markdown, falling back to plain text on failure."""
    try:
        await chat.send_message(text, parse_mode="Markdown")
    except BadRequest:
        await chat.send_message(text)


async def _send_transfer_confirmation(chat, text: str, transfer_ids: list[str]) -> None:
    """Send a message with inline confirmation buttons for staged transfers."""
    # Build keyboard with Confirm/Cancel buttons for each transfer
    buttons = []
    for tid in transfer_ids:
        buttons.append(
            [
                InlineKeyboardButton("Confirm", callback_data=f"confirm:{tid}"),
                InlineKeyboardButton("Cancel", callback_data=f"cancel:{tid}"),
            ]
        )
    keyboard = InlineKeyboardMarkup(buttons)
    try:
        await chat.send_message(text, parse_mode="Markdown", reply_markup=keyboard)
    except BadRequest:
        await chat.send_message(text, reply_markup=keyboard)


async def _start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command."""
    await update.effective_chat.send_message(
        "Hey! \U0001f44b I'm your Sequence finance assistant. "
        "Ask me about your pod balances or transfer money between pods! \U0001f4b0"
    )


async def _handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle text messages by passing them to the AI agent."""
    agent: Agent = context.bot_data["agent"]
    telegram_config: TelegramConfig = context.bot_data["telegram_config"]
    user_text = update.message.text
    user_id = update.effective_user.id
    user_names: dict[int, str] = context.bot_data.get("user_names", {})
    user_name = user_names.get(user_id)

    # Rate limiting
    if _is_rate_limited(
        user_id,
        telegram_config.rate_limit_messages,
        telegram_config.rate_limit_window_seconds,
    ):
        await update.effective_chat.send_message(
            "Whoa, slow down! \U0001f605 You're sending messages too fast. "
            "Give me a moment and try again."
        )
        return

    # Input length cap
    max_len = telegram_config.max_message_length
    if len(user_text) > max_len:
        user_text = user_text[:max_len]

    log.info("Message from user %s (%s): %s", user_id, user_name, user_text)

    chat = update.effective_chat
    typing_task = asyncio.create_task(_keep_typing(chat))

    try:
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            partial(
                agent.process_message,
                user_text,
                user_name=user_name,
                user_id=user_id,
            ),
        )
    except RuntimeError as e:
        log.exception("SDK error processing message: %s", e)
        response = (
            "Hmm, something went wrong talking to Sequence \U0001f61e "
            "Give me a minute and try again!"
        )
    except Exception:
        log.exception("Error processing message")
        response = (
            "Oops, something went wrong on my end \U0001f62c " "Try again in a sec!"
        )
    finally:
        typing_task.cancel()

    staged = agent.staged_this_turn
    if staged:
        await _send_transfer_confirmation(chat, response, staged)
    else:
        await _send_response(chat, response)


async def _handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle inline button callbacks for transfer confirmation/cancellation."""
    query = update.callback_query
    await query.answer()

    agent: Agent = context.bot_data["agent"]
    audit: AuditLog | None = context.bot_data.get("audit")
    daily_limits: DailyLimitTracker | None = context.bot_data.get("daily_limits")
    agent_config: AgentConfig = context.bot_data["agent_config"]
    sdk_config: SdkConfig | None = context.bot_data.get("sdk_config")
    user_names: dict[int, str] = context.bot_data.get("user_names", {})
    user_id = query.from_user.id
    user_name = user_names.get(user_id)

    data = query.data or ""
    if ":" not in data:
        return

    action, transfer_id = data.split(":", 1)

    pending = agent.pending_transfers
    if transfer_id not in pending:
        await query.edit_message_text(
            "This transfer has expired or was already handled."
        )
        return

    transfer = pending[transfer_id]

    # Ownership check
    if transfer.get("user_id") is not None and transfer["user_id"] != user_id:
        await query.answer("You can only manage your own transfers.", show_alert=True)
        return

    if action == "cancel":
        if audit:
            audit.log(
                "transfer_cancelled",
                user_id=user_id,
                user_name=user_name,
                transfer_id=transfer_id,
                amount_cents=transfer["amount_cents"],
                source=transfer["source_name"],
                destination=transfer["destination_name"],
            )
        del pending[transfer_id]
        await query.edit_message_text(
            f"Transfer cancelled. {transfer['amount_display']} from "
            f"{transfer['source_name']} to {transfer['destination_name']} "
            f"has been cancelled."
        )
        return

    if action == "confirm":
        # Check TTL
        elapsed = time.time() - transfer["created_at"]
        if elapsed > agent_config.pending_transfer_ttl:
            if audit:
                audit.log(
                    "transfer_expired",
                    user_id=user_id,
                    transfer_id=transfer_id,
                    amount_cents=transfer["amount_cents"],
                    source=transfer["source_name"],
                    destination=transfer["destination_name"],
                )
            del pending[transfer_id]
            await query.edit_message_text(
                "This transfer has expired. Please request a new one."
            )
            return

        # Check daily limit before executing
        if daily_limits is not None:
            allowed, remaining = daily_limits.check(
                transfer["amount_cents"], user_id=user_id
            )
            if not allowed:
                await query.edit_message_text(
                    f"This transfer would exceed your daily limit. "
                    f"Remaining today: ${remaining / 100:,.2f}."
                )
                return

        # Execute the transfer
        client: SequenceClient = context.bot_data["client"]
        try:
            tool_input = {"pending_transfer_id": transfer_id}
            result_json = _handle_confirm_transfer(
                tool_input, client, agent_config, pending, sdk_config=sdk_config
            )
            result = json.loads(result_json)
        except Exception as exc:
            log.exception("Transfer execution failed")
            if audit:
                audit.log(
                    "transfer_failed",
                    user_id=user_id,
                    user_name=user_name,
                    transfer_id=transfer_id,
                    amount_cents=transfer["amount_cents"],
                    source=transfer["source_name"],
                    destination=transfer["destination_name"],
                    error=str(exc),
                )
            await query.edit_message_text(
                "Something went wrong executing the transfer. Please try again."
            )
            return

        if "error" in result:
            if audit:
                audit.log(
                    "transfer_failed",
                    user_id=user_id,
                    user_name=user_name,
                    transfer_id=transfer_id,
                    amount_cents=transfer.get("amount_cents"),
                    source=transfer.get("source_name"),
                    destination=transfer.get("destination_name"),
                    error=result["error"],
                )
            await query.edit_message_text(f"Transfer failed: {result['error']}")
            return

        # Record daily limit and audit
        if daily_limits is not None:
            daily_limits.record(
                transfer.get("amount_cents", 0), transfer_id, user_id=user_id
            )
        if audit:
            audit.log(
                "transfer_confirmed",
                user_id=user_id,
                user_name=user_name,
                transfer_id=transfer_id,
                amount_cents=transfer.get("amount_cents"),
                source=result.get("source"),
                destination=result.get("destination"),
            )
        await query.edit_message_text(
            f"Transfer complete! {result['amount']} sent from "
            f"{result['source']} to {result['destination']}."
        )


def run_bot() -> None:
    """Start the Telegram bot."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )

    agent_config, telegram_config = load_config()
    sdk_config = get_sdk_config()
    memory = MemoryStore(max_facts=agent_config.max_memory_facts)
    daily_limits = DailyLimitTracker(
        max_daily_cents=agent_config.max_daily_transfer_cents
    )
    audit = AuditLog()
    client = SequenceClient(get_access_token(), token_provider=get_access_token)
    agent = Agent(
        client,
        sdk_config=sdk_config,
        agent_config=agent_config,
        memory=memory,
        daily_limits=daily_limits,
        audit=audit,
    )

    user_filter = _AllowedUserFilter(
        telegram_config.allowed_user_ids, telegram_config.group_id
    )

    app = Application.builder().token(telegram_config.bot_token).build()

    app.bot_data["client"] = client
    app.bot_data["agent"] = agent
    app.bot_data["agent_config"] = agent_config
    app.bot_data["sdk_config"] = sdk_config
    app.bot_data["memory"] = memory
    app.bot_data["daily_limits"] = daily_limits
    app.bot_data["audit"] = audit
    app.bot_data["user_names"] = telegram_config.user_names
    app.bot_data["telegram_config"] = telegram_config

    app.add_handler(CommandHandler("start", _start, filters=user_filter))
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND & user_filter, _handle_message)
    )
    app.add_handler(CallbackQueryHandler(_handle_callback))

    log.info("Bot starting, polling for updates...")
    app.run_polling()
