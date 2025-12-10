"""Tests for extract_reasoning_content and _parse_reasoning_details functions."""

from unittest.mock import MagicMock

from agents.models.chatcmpl_helpers import _parse_reasoning_details, extract_reasoning_content


class TestExtractReasoningContent:
    """Test extract_reasoning_content main function."""

    def test_priority_reasoning_content_first(self):
        """Priority test: reasoning_content has highest priority."""
        obj = MagicMock()
        obj.reasoning_content = "From reasoning_content"
        obj.reasoning = "From reasoning"
        obj.reasoning_details = [{"type": "reasoning.text", "text": "From details"}]

        result = extract_reasoning_content(obj)
        assert result == "From reasoning_content"

    def test_priority_reasoning_second(self):
        """Priority test: reasoning is second."""
        obj = MagicMock()
        obj.reasoning_content = None
        obj.reasoning = "From reasoning"
        obj.reasoning_details = [{"type": "reasoning.text", "text": "From details"}]

        result = extract_reasoning_content(obj)
        assert result == "From reasoning"

    def test_fallback_to_reasoning_details(self):
        """Priority test: finally use reasoning_details."""
        obj = MagicMock()
        obj.reasoning_content = None
        obj.reasoning = None
        obj.reasoning_details = [{"type": "reasoning.text", "text": "From details"}]

        result = extract_reasoning_content(obj)
        assert result == "From details"

    def test_empty_string_not_used(self):
        """Empty string should be treated as invalid, continue checking next priority."""
        obj = MagicMock()
        obj.reasoning_content = ""
        obj.reasoning = ""
        obj.reasoning_details = [{"type": "reasoning.summary", "summary": "Fallback"}]

        result = extract_reasoning_content(obj)
        assert result == "Fallback"

    def test_no_reasoning_returns_none(self):
        """Returns None when no reasoning content is available."""
        obj = MagicMock()
        obj.reasoning_content = None
        obj.reasoning = None
        obj.reasoning_details = None

        result = extract_reasoning_content(obj)
        assert result is None

    def test_missing_attributes(self):
        """Handle objects without the expected attributes."""
        obj = MagicMock(spec=[])  # Empty spec, no attributes

        result = extract_reasoning_content(obj)
        assert result is None


class TestParseReasoningDetails:
    """Test _parse_reasoning_details parsing function."""

    def test_extract_reasoning_text(self):
        """Test reasoning.text type (Claude/Gemini/DeepSeek)."""
        details = [
            {"type": "reasoning.text", "text": "Step 1", "format": "anthropic-claude-v1"},
            {"type": "reasoning.text", "text": " Step 2", "format": "anthropic-claude-v1"},
        ]
        result = _parse_reasoning_details(details)
        assert result == "Step 1 Step 2"

    def test_extract_reasoning_summary(self):
        """Test reasoning.summary type (OpenAI GPT-5)."""
        details = [
            {"type": "reasoning.summary", "summary": "I should", "format": "openai-responses-v1"},
            {"type": "reasoning.summary", "summary": " respond", "format": "openai-responses-v1"},
        ]
        result = _parse_reasoning_details(details)
        assert result == "I should respond"

    def test_ignore_encrypted(self):
        """Test ignoring reasoning.encrypted type."""
        details = [
            {"type": "reasoning.encrypted", "data": "gAAAAABpOVy9..."},
            {"type": "reasoning.summary", "summary": "Summary here"},
        ]
        result = _parse_reasoning_details(details)
        assert result == "Summary here"

    def test_mixed_types(self):
        """Test mixed types."""
        details = [
            {"type": "reasoning.text", "text": "Thinking..."},
            {"type": "reasoning.encrypted", "data": "encrypted"},
            {"type": "reasoning.summary", "summary": " Done."},
        ]
        result = _parse_reasoning_details(details)
        assert result == "Thinking... Done."

    def test_unknown_type_ignored(self):
        """Test unknown types are ignored (forward compatibility)."""
        details = [
            {"type": "reasoning.future_type", "content": "Future content"},
            {"type": "reasoning.text", "text": "Known content"},
        ]
        result = _parse_reasoning_details(details)
        assert result == "Known content"

    def test_empty_array_returns_none(self):
        """Empty array returns None."""
        assert _parse_reasoning_details([]) is None

    def test_none_returns_none(self):
        """None returns None."""
        assert _parse_reasoning_details(None) is None

    def test_non_list_returns_none(self):
        """Non-list type returns None."""
        assert _parse_reasoning_details("not a list") is None
        assert _parse_reasoning_details({"type": "reasoning.text"}) is None

    def test_non_dict_items_skipped(self):
        """Non-dict items are skipped."""
        details = [
            "string item",
            None,
            {"type": "reasoning.text", "text": "Valid"},
            123,
        ]
        result = _parse_reasoning_details(details)
        assert result == "Valid"

    def test_empty_text_skipped(self):
        """Empty text is skipped."""
        details = [
            {"type": "reasoning.text", "text": ""},
            {"type": "reasoning.text", "text": "Valid"},
            {"type": "reasoning.summary", "summary": None},
        ]
        result = _parse_reasoning_details(details)
        assert result == "Valid"

    def test_only_encrypted_returns_none(self):
        """Returns None when only encrypted content is present."""
        details = [
            {"type": "reasoning.encrypted", "data": "encrypted1"},
            {"type": "reasoning.encrypted", "data": "encrypted2"},
        ]
        result = _parse_reasoning_details(details)
        assert result is None
