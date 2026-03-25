"""Response parser for extracting structured content from LLM responses."""
import json
import logging
import re
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)


@dataclass
class ParsedContent:
    """Structured representation of parsed content."""
    content: str
    content_type: str
    metadata: Dict[str, Any]
    is_valid: bool
    parse_errors: List[str]


class ResponseParser:
    """Parser for LLM responses in various formats."""

    @staticmethod
    def parse_markdown(content: str, content_type: str) -> ParsedContent:
        """Parse markdown formatted content.

        Args:
            content: Raw markdown content from LLM
            content_type: Type of content being parsed

        Returns:
            ParsedContent with structured data
        """
        errors = []

        # Basic validation
        if not content or len(content.strip()) < 10:
            errors.append("Content too short (minimum 10 characters)")

        # Extract sections if present
        sections = re.findall(r'^#+\s+(.+)$', content, re.MULTILINE)

        metadata = {
            "sections": sections,
            "word_count": len(content.split()),
            "character_count": len(content),
            "has_images": "[SHOW:" in content or "![" in content,
        }

        return ParsedContent(
            content=content,
            content_type=content_type,
            metadata=metadata,
            is_valid=len(errors) == 0,
            parse_errors=errors,
        )

    @staticmethod
    def parse_json(content: str, content_type: str) -> ParsedContent:
        """Parse JSON formatted content.

        Args:
            content: Raw JSON content from LLM
            content_type: Type of content being parsed

        Returns:
            ParsedContent with structured data
        """
        errors = []
        parsed_json = {}

        try:
            # Try to extract JSON from markdown code blocks if present
            json_match = re.search(r'```(?:json)?\s*(\{[\s\S]*?\})\s*```', content)
            if json_match:
                json_str = json_match.group(1)
            else:
                json_str = content

            parsed_json = json.loads(json_str)
        except json.JSONDecodeError as e:
            errors.append(f"Invalid JSON: {str(e)}")
            # Try to use raw content if JSON parsing fails
            parsed_json = {"raw_content": content}

        metadata = {
            "json_keys": list(parsed_json.keys()) if isinstance(parsed_json, dict) else [],
            "is_json_valid": len(errors) == 0,
        }

        return ParsedContent(
            content=json.dumps(parsed_json) if parsed_json else content,
            content_type=content_type,
            metadata=metadata,
            is_valid=len(errors) == 0,
            parse_errors=errors,
        )

    @staticmethod
    def parse_plain_text(content: str, content_type: str) -> ParsedContent:
        """Parse plain text content.

        Args:
            content: Raw text content from LLM
            content_type: Type of content being parsed

        Returns:
            ParsedContent with structured data
        """
        errors = []

        if not content or len(content.strip()) < 5:
            errors.append("Content too short")

        # Extract hashtags if content type is hashtags
        hashtags = []
        if content_type == "hashtags":
            hashtags = re.findall(r'#\w+', content)

        lines = content.split('\n')
        metadata = {
            "line_count": len(lines),
            "word_count": len(content.split()),
            "hashtags": hashtags,
        }

        return ParsedContent(
            content=content,
            content_type=content_type,
            metadata=metadata,
            is_valid=len(errors) == 0,
            parse_errors=errors,
        )

    @classmethod
    def parse(
        cls,
        content: str,
        content_type: str,
        output_format: str,
    ) -> ParsedContent:
        """Parse LLM response based on expected format.

        Args:
            content: Raw content from LLM
            content_type: Type of content
            output_format: Expected format (markdown, json, text)

        Returns:
            ParsedContent with structured data
        """
        if output_format == "json":
            return cls.parse_json(content, content_type)
        elif output_format == "markdown":
            return cls.parse_markdown(content, content_type)
        else:
            return cls.parse_plain_text(content, content_type)

    @staticmethod
    def extract_sections(content: str) -> Dict[str, str]:
        """Extract sections from markdown content.

        Args:
            content: Markdown content

        Returns:
            Dictionary mapping section names to content
        """
        sections = {}
        current_section = "intro"
        current_content = []

        for line in content.split('\n'):
            if line.startswith('#'):
                if current_content:
                    sections[current_section] = '\n'.join(current_content).strip()
                    current_content = []
                current_section = line.strip('#').strip().lower()
            else:
                current_content.append(line)

        if current_content:
            sections[current_section] = '\n'.join(current_content).strip()

        return sections

    @staticmethod
    def validate_length(
        content: str,
        min_words: Optional[int] = None,
        max_words: Optional[int] = None,
    ) -> tuple[bool, str]:
        """Validate content length.

        Args:
            content: Content to validate
            min_words: Minimum word count (optional)
            max_words: Maximum word count (optional)

        Returns:
            Tuple of (is_valid, error_message)
        """
        word_count = len(content.split())

        if min_words and word_count < min_words:
            return False, f"Content too short: {word_count} words (min: {min_words})"

        if max_words and word_count > max_words:
            return False, f"Content too long: {word_count} words (max: {max_words})"

        return True, ""
