from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal, Union

from typing_extensions import TypeAlias

from .items import RunItem, TResponseStreamEvent

if TYPE_CHECKING:
    from .agent import Agent


@dataclass
class RawResponsesStreamEvent:
    """Streaming event from the LLM. These are 'raw' events, i.e. they are directly passed through
    from the LLM.
    """

    data: TResponseStreamEvent
    """The raw responses streaming event from the LLM."""

    type: Literal["raw_response_event"] = "raw_response_event"
    """The type of the event."""


@dataclass
class RunItemStreamEvent:
    """Streaming events that wrap a `RunItem`. As the agent processes the LLM response, it will
    generate these events for new messages, tool calls, tool outputs, handoffs, etc.
    """

    name: Literal[
        "message_output_created",
        "handoff_requested",
        # This is misspelled, but we can't change it because that would be a breaking change
        "handoff_occured",
        "tool_called",
        "tool_output",
        "reasoning_item_created",
        "mcp_approval_requested",
        "mcp_list_tools",
    ]
    """The name of the event."""

    item: RunItem
    """The item that was created."""

    type: Literal["run_item_stream_event"] = "run_item_stream_event"


@dataclass
class NotifyStreamEvent:
    """An event for notification purposes that does not affect the run history."""

    data: str
    """The notification message."""

    is_delta: bool = False
    """If True, the data is a delta and should be appended to the previous data."""

    tag: str | None = None
    """A tag for the notification, used for UI purposes."""

    tool_name: str | None = None
    """The name of the tool that generated the event."""

    tool_call_id: str | None = None
    """The ID of the tool call that generated the event."""

    type: Literal["notify_stream_event"] = "notify_stream_event"


@dataclass
class StreamingToolStartEvent:
    """Event that notifies that a streaming tool is starting."""

    tool_name: str
    """The name of the streaming tool that is starting."""

    tool_call_id: str
    """The ID of the tool call that is starting."""

    input_args: dict[str, Any]
    """The input arguments to the tool."""

    type: Literal["streaming_tool_start_event"] = "streaming_tool_start_event"


@dataclass
class StreamingToolEndEvent:
    """Event that notifies that a streaming tool is ending."""

    tool_name: str
    """The name of the streaming tool that is ending."""

    tool_call_id: str
    """The ID of the tool call that is ending."""

    type: Literal["streaming_tool_end_event"] = "streaming_tool_end_event"


@dataclass
class AgentUpdatedStreamEvent:
    """Event that notifies that there is a new agent running."""

    new_agent: Agent[Any]
    """The new agent."""

    type: Literal["agent_updated_stream_event"] = "agent_updated_stream_event"


@dataclass
class StreamingToolContextEvent:
    """streaming_tool 内部上下文事件容器

    用于包装 streaming_tool 内部产生的事件，这些事件仅用于展示，
    不会影响主 agent 的对话历史。实现上下文隔离的关键机制。
    """
    tool_name: str
    """生成此事件的 streaming_tool 名称"""

    tool_call_id: str
    """streaming_tool 调用的唯一标识符"""

    internal_event: StreamEvent
    """被包装的内部事件，仅用于展示目的"""

    type: Literal["streaming_tool_context_event"] = "streaming_tool_context_event"


StreamEvent: TypeAlias = Union[
    RawResponsesStreamEvent,
    RunItemStreamEvent,
    AgentUpdatedStreamEvent,
    NotifyStreamEvent,
    StreamingToolStartEvent,
    StreamingToolEndEvent,
    StreamingToolContextEvent,
]
"""A streaming event from an agent."""
