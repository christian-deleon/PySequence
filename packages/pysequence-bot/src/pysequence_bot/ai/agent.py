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


def _build_system_prompt(
    base_prompt: str,
    user_name: str | None,
    memory_context: str | None = None,
) -> str:
    """Build the system prompt, optionally with memory and user identity context."""
    now = datetime.now(ZoneInfo("America/New_York"))
    parts = [base_prompt]
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
        system_prompt = _build_system_prompt(
            self._agent_config.system_prompt, user_name, memory_context
        )

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
                text_parts = [
                    b.text for b in response.content if b.type == "text" and b.text
                ]
                return "\n".join(text_parts) if text_parts else "Here you go!"

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
