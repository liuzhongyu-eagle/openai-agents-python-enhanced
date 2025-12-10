from __future__ import annotations

from typing import Any

from openai import AsyncOpenAI

from ..model_settings import ModelSettings
from ..version import __version__

_USER_AGENT = f"Agents/Python {__version__}"
HEADERS = {"User-Agent": _USER_AGENT}


class ChatCmplHelpers:
    @classmethod
    def is_openai(cls, client: AsyncOpenAI):
        return str(client.base_url).startswith("https://api.openai.com")

    @classmethod
    def get_store_param(cls, client: AsyncOpenAI, model_settings: ModelSettings) -> bool | None:
        # Match the behavior of Responses where store is True when not given
        default_store = True if cls.is_openai(client) else None
        return model_settings.store if model_settings.store is not None else default_store

    @classmethod
    def get_stream_options_param(
        cls, client: AsyncOpenAI, model_settings: ModelSettings, stream: bool
    ) -> dict[str, bool] | None:
        if not stream:
            return None

        default_include_usage = True if cls.is_openai(client) else None
        include_usage = (
            model_settings.include_usage
            if model_settings.include_usage is not None
            else default_include_usage
        )
        stream_options = {"include_usage": include_usage} if include_usage is not None else None
        return stream_options


def extract_reasoning_content(
    obj: Any,
    *,
    text_field: str = "reasoning_content",
    string_field: str = "reasoning",
    details_field: str = "reasoning_details",
) -> str | None:
    """
    Extract reasoning content from a delta or message object.

    Supports three formats (by priority):
    1. reasoning_content (string) - OpenAI Responses API native format
    2. reasoning (string) - OpenRouter simplified string
    3. reasoning_details (array) - OpenRouter detailed array
       - reasoning.text: plain text reasoning (Claude/Gemini/DeepSeek)
       - reasoning.summary: reasoning summary (OpenAI GPT-5)
       - reasoning.encrypted: ignored (encrypted content)

    Args:
        obj: delta or message object
        text_field: primary text field name
        string_field: simplified string field name
        details_field: detailed array field name

    Returns:
        Extracted reasoning content string, or None if not available.
    """
    # Priority 1: reasoning_content (OpenAI Responses API)
    if hasattr(obj, text_field):
        value = getattr(obj, text_field)
        if value:
            return str(value)

    # Priority 2: reasoning (OpenRouter simplified string)
    if hasattr(obj, string_field):
        value = getattr(obj, string_field)
        if value:
            return str(value)

    # Priority 3: reasoning_details (OpenRouter detailed array)
    if hasattr(obj, details_field):
        details = getattr(obj, details_field)
        if details:
            return _parse_reasoning_details(details)

    return None


def _parse_reasoning_details(details: Any) -> str | None:
    """
    Parse reasoning_details array and extract readable content.

    Supported types:
    - reasoning.text: extract 'text' field
    - reasoning.summary: extract 'summary' field
    - reasoning.encrypted: ignored (encrypted, not readable)
    - unknown types: ignored (forward compatibility)

    Args:
        details: reasoning_details array

    Returns:
        Concatenated reasoning content, or None if no readable content.
    """
    if not details:
        return None

    # Ensure it is an iterable
    if not isinstance(details, (list, tuple)):
        return None

    parts: list[str] = []

    for detail in details:
        # Skip non-dict types
        if not isinstance(detail, dict):
            continue

        detail_type = detail.get("type", "")

        if detail_type == "reasoning.text":
            # Claude/Gemini/DeepSeek plain text reasoning
            text = detail.get("text")
            if text:
                parts.append(str(text))

        elif detail_type == "reasoning.summary":
            # OpenAI GPT-5 reasoning summary
            summary = detail.get("summary")
            if summary:
                parts.append(str(summary))

        # reasoning.encrypted and other unknown types: silently ignored
        # This allows forward compatibility with future types

    if not parts:
        return None

    return "".join(parts)
