"""Claude AI agent with tool-use loop for natural language finance queries."""

import logging
import time
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import anthropic

from pysequence_bot.ai.memory import MemoryStore
from pysequence_bot.ai.tools import TOOLS, execute_tool
from pysequence_bot.config import AgentConfig, SdkConfig
from pysequence_sdk import SequenceClient
from pysequence_sdk.safeguards import AuditLog, DailyLimitTracker

log = logging.getLogger(__name__)


SYSTEM_PROMPT = """\
You are a personal finance assistant that helps manage a GetSequence account. \
You help users check pod balances and transfer money between pods. Be concise — this is \
Telegram.

Personality:
- You're upbeat, friendly, and fun! Use emojis naturally throughout your responses 🎉
- You're like a helpful friend who happens to be great with money, not a stuffy banker.
- When the context of a request hints at something going on (dinner out, grocery \
shopping, a trip, paying bills, etc.), add a short, warm, creative comment about it. \
For example, if someone asks to transfer money for dinner, you might say "Enjoy your \
dinner tonight! 🍽️" or if they're transferring for groceries, "Happy shopping! 🛒". \
Keep it natural and varied — don't be robotic or repetitive about it.
- Celebrate wins! If a balance is looking good, say so. If they just got paid, hype it up.
- Keep the energy positive but never forced. Read the room — if someone seems stressed \
about money, be supportive and encouraging rather than overly cheerful.

Rules:
- NEVER invent pod names, balances, or IDs. Always use tools to look up real data.
- When the user asks about a specific pod, use get_pod_balance.
- When the user asks about all pods, totals, sums, or rankings, use get_all_pods and \
compute from the returned data.
- Be proactive about checking balances. When the user mentions needing money for \
something (e.g. "I need to get gas", "gotta grab groceries", "paying rent today"), \
don't just ask how much to transfer — first check the relevant pod balance using \
get_pod_balance. Then respond based on what you find:
  - If the pod has plenty of money (enough for that type of expense), let them know \
they're already covered (e.g. "You've got $180.00 in Gas ⛽ — you're all set!").
  - If the pod is low, tell them and offer to help top it up (e.g. "Your Gas pod only \
has $12.50 right now — want me to transfer some more over?").
  - Use your judgment on what "enough" means for the category (gas ~$40-80, groceries \
~$100-200, etc.) and adjust based on any memories about their spending patterns.
- When the user wants to transfer money, use request_transfer to stage it. Present the \
transfer details clearly (including the note). The user will confirm or cancel via \
buttons in the chat — you do not need to handle confirmation yourself. Do NOT attempt \
to confirm transfers. If the user says "yes" or "confirm", let them know to use the \
buttons instead.
- If the user says "cancel", "never mind", or wants to abandon a pending transfer, \
use cancel_transfer to cancel it.
- Always include a note/description when staging a transfer. Infer a short, clear \
description from the conversation context (e.g. "Weekly groceries", "Rent payment", \
"Topping up savings"). If the reason for the transfer is too vague to guess, ask the \
user what it's for before staging. Only skip the note if the user explicitly says not to \
worry about it.
- When the user requests a transfer but doesn't specify the source pod, don't just ask \
"which pod?" — be smart about it. Call get_all_pods, look at balances and pod names, \
consider the context of the transfer, check your memories for past preferences, and \
suggest your top 3 best guesses for where the money should come from (as a numbered \
list). Once the user picks one, save their preference to memory so you learn over time \
and can suggest even better next time. If a memory already exists for that category, \
update it rather than creating a duplicate.
- Format monetary amounts with $ and two decimal places (e.g. $50.00).
- If a tool returns an error, relay it to the user clearly.
- Do not make up data. If you don't know something, say so.

Memory:
- You have persistent memory that survives restarts. Use save_memory to remember \
preferences, pod nicknames, spending patterns, or any useful context the user shares.
- When the user says "remember that..." or shares a preference, save it immediately.
- When the user corrects a fact, update the existing fact (pass its fact_id) rather than \
creating a duplicate.
- When the user says "forget..." or asks you to stop remembering something, delete it.
- Use list_memories when the user asks what you remember.
- Use remembered facts to resolve nicknames and preferences without asking again.
- If memory is full, tell the user and ask which fact(s) they'd like you to forget \
to make room. Do not silently delete facts on your own.\
"""


def _build_system_prompt(
    user_name: str | None, memory_context: str | None = None
) -> str:
    """Build the system prompt, optionally with memory and user identity context."""
    now = datetime.now(ZoneInfo("America/New_York"))
    parts = [SYSTEM_PROMPT]
    parts.append(
        f"Current date and time: {now.strftime('%A, %B %-d, %Y at %-I:%M %p ET')}."
    )
    if memory_context:
        parts.append(memory_context)
    if user_name:
        parts.append(f"The current user is {user_name}.")
    return "\n\n".join(parts)


class Agent:
    """Claude-powered agent that uses tools to interact with the Sequence SDK."""

    def __init__(
        self,
        client: SequenceClient,
        sdk_config: SdkConfig | None = None,
        agent_config: AgentConfig | None = None,
        memory: MemoryStore | None = None,
        daily_limits: DailyLimitTracker | None = None,
        audit: AuditLog | None = None,
    ) -> None:
        self._anthropic = anthropic.Anthropic()
        self._client = client
        self._sdk_config = sdk_config
        self._agent_config = agent_config or AgentConfig()
        self._memory = memory
        self._daily_limits = daily_limits
        self._audit = audit
        self._messages: list[dict[str, Any]] = []
        self._pending_transfers: dict[str, dict] = {}
        self._staged_this_turn: list[str] = []
        self._last_activity: float = 0.0

    @property
    def staged_this_turn(self) -> list[str]:
        """Transfer IDs staged during the most recent process_message() call."""
        return list(self._staged_this_turn)

    @property
    def pending_transfers(self) -> dict[str, dict]:
        """All currently pending (staged) transfers."""
        return self._pending_transfers

    def process_message(
        self,
        user_text: str,
        user_name: str | None = None,
        user_id: int | None = None,
    ) -> str:
        """Process a user message and return the assistant's response."""
        self._staged_this_turn = []
        now = time.time()
        if (
            self._last_activity
            and now - self._last_activity > self._agent_config.conversation_ttl
        ):
            log.info("Conversation TTL expired, resetting context")
            self._messages.clear()
            self._pending_transfers.clear()
        self._last_activity = now

        self._messages.append({"role": "user", "content": user_text})
        self._trim_history()

        memory_context = self._memory.format_for_prompt() if self._memory else None
        system_prompt = _build_system_prompt(user_name, memory_context)

        while True:
            log.info("Calling Claude API with %d messages", len(self._messages))
            response = self._anthropic.messages.create(
                model=self._agent_config.model,
                max_tokens=self._agent_config.max_tokens,
                temperature=0,
                system=system_prompt,
                tools=TOOLS,
                messages=self._messages,
            )

            # Build assistant message content
            assistant_content = []
            for block in response.content:
                if block.type == "text":
                    assistant_content.append({"type": "text", "text": block.text})
                elif block.type == "tool_use":
                    assistant_content.append(
                        {
                            "type": "tool_use",
                            "id": block.id,
                            "name": block.name,
                            "input": block.input,
                        }
                    )

            self._messages.append({"role": "assistant", "content": assistant_content})

            if response.stop_reason != "tool_use":
                # Extract text from response
                text_parts = [b.text for b in response.content if b.type == "text"]
                return "\n".join(text_parts)

            # Execute tool calls and append results
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    log.info("Tool call: %s(%s)", block.name, block.input)
                    result = execute_tool(
                        block.name,
                        block.input,
                        self._client,
                        self._agent_config,
                        self._pending_transfers,
                        sdk_config=self._sdk_config,
                        memory=self._memory,
                        user_name=user_name,
                        user_id=user_id,
                        staged_this_turn=self._staged_this_turn,
                        daily_limits=self._daily_limits,
                        audit=self._audit,
                    )
                    log.info("Tool result: %s", result[:200])
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result,
                        }
                    )

            self._messages.append({"role": "user", "content": tool_results})

    def _trim_history(self) -> None:
        """Trim conversation history if it exceeds max_history messages."""
        max_history = self._agent_config.max_history
        trim_to = self._agent_config.trim_to
        if len(self._messages) > max_history:
            self._messages = self._messages[:10] + self._messages[-(trim_to - 10) :]
