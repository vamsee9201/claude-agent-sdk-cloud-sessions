from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    TextBlock,
    ToolResultBlock,
    ToolUseBlock,
    UserMessage,
    query,
)

from app.config import settings
from app.models.schemas import ToolCall
from app.tools.weather import weather_server

logger = logging.getLogger(__name__)


def _stderr_handler(line: str) -> None:
    logger.info("CLI stderr: %s", line.rstrip())


async def _streaming_prompt(text: str) -> AsyncIterator[dict[str, Any]]:
    """Wrap a string prompt as an async generator to force streaming mode.

    SDK MCP servers require bidirectional stdin/stdout communication.
    String prompts use --print mode which closes stdin immediately,
    preventing the SDK from writing MCP tool results back to the CLI.
    """
    yield {
        "type": "user",
        "message": {"role": "user", "content": text},
        "parent_tool_use_id": None,
        "session_id": "default",
    }


@dataclass
class AgentResponse:
    session_id: str = ""
    response_text: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    is_error: bool = False
    cost_usd: float | None = None
    duration_ms: int | None = None


def _build_options() -> ClaudeAgentOptions:
    return ClaudeAgentOptions(
        system_prompt=settings.CLAUDE_SYSTEM_PROMPT,
        max_turns=settings.CLAUDE_MAX_TURNS,
        max_budget_usd=settings.CLAUDE_MAX_BUDGET_USD,
        mcp_servers={"weather": weather_server},
        allowed_tools=["mcp__weather__get_weather"],
        permission_mode="bypassPermissions",
        env={"ANTHROPIC_API_KEY": settings.ANTHROPIC_API_KEY},
        stderr=_stderr_handler,
    )


async def _execute_query(message: str, options: ClaudeAgentOptions) -> AgentResponse:
    """Execute a query against the Claude agent. Lets exceptions propagate."""
    result = AgentResponse()
    text_parts: list[str] = []
    pending_tool_uses: dict[str, ToolCall] = {}

    async for msg in query(prompt=_streaming_prompt(message), options=options):
        if isinstance(msg, AssistantMessage):
            for block in msg.content:
                if isinstance(block, TextBlock):
                    text_parts.append(block.text)
                elif isinstance(block, ToolUseBlock):
                    tc = ToolCall(
                        tool_name=block.name,
                        tool_input=block.input,
                    )
                    pending_tool_uses[block.id] = tc
                    result.tool_calls.append(tc)

        elif isinstance(msg, UserMessage):
            if isinstance(msg.content, list):
                for block in msg.content:
                    if isinstance(block, ToolResultBlock):
                        tc = pending_tool_uses.get(block.tool_use_id)
                        if tc and block.content:
                            if isinstance(block.content, str):
                                tc.tool_result = block.content
                            elif isinstance(block.content, list):
                                texts = [
                                    c.get("text", "")
                                    for c in block.content
                                    if isinstance(c, dict) and c.get("type") == "text"
                                ]
                                tc.tool_result = "\n".join(texts)

        elif isinstance(msg, ResultMessage):
            result.session_id = msg.session_id
            result.is_error = msg.is_error
            result.cost_usd = msg.total_cost_usd
            result.duration_ms = msg.duration_ms

    result.response_text = "\n".join(text_parts)
    return result


async def run_agent(message: str, session_id: str | None = None) -> AgentResponse:
    options = _build_options()

    if session_id:
        options.resume = session_id

    try:
        return await _execute_query(message, options)
    except Exception:
        if session_id:
            logger.warning("Resume failed for session %s, starting fresh", session_id)
            options.resume = None
            try:
                return await _execute_query(message, options)
            except Exception:
                logger.exception("Agent query failed (after resume fallback)")
        else:
            logger.exception("Agent query failed")
        return AgentResponse(
            is_error=True,
            response_text="An error occurred while processing your request.",
        )
