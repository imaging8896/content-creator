"""Main content generator orchestrating LLM, templates, and parsing."""
import logging
import asyncio
from typing import Optional, Dict, Any
from dataclasses import dataclass
import json

from llm_client import LLMFactory, ContentResponse
from prompt_templates import PromptTemplateLibrary
from response_parser import ResponseParser, ParsedContent

logger = logging.getLogger(__name__)


@dataclass
class GenerationRequest:
    """Request for content generation."""
    trend_topic: str
    content_type: str  # video_script, article, caption, hashtags, etc.
    provider: str = "claude"  # claude or gpt
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


@dataclass
class GenerationResult:
    """Result of content generation."""
    success: bool
    content: str
    content_type: str
    model: str
    metadata: Dict[str, Any]
    errors: list


class ContentGenerator:
    """Main content generation orchestrator."""

    def __init__(self, default_provider: str = "claude"):
        """Initialize content generator.

        Args:
            default_provider: Default LLM provider (claude or gpt)
        """
        self.default_provider = default_provider

    def generate(self, request: GenerationRequest) -> GenerationResult:
        """Generate content based on a trend.

        Args:
            request: GenerationRequest with topic and content type

        Returns:
            GenerationResult with generated content
        """
        errors = []

        try:
            # Step 1: Get appropriate template
            try:
                template = PromptTemplateLibrary.get_template(request.content_type)
            except ValueError as e:
                return GenerationResult(
                    success=False,
                    content="",
                    content_type=request.content_type,
                    model="",
                    metadata={},
                    errors=[str(e)],
                )

            # Step 2: Prepare template variables
            template_vars = self._prepare_template_variables(
                request.trend_topic,
                request.content_type,
                request.metadata,
            )

            # Step 3: Render prompt
            try:
                prompt = template.render(**template_vars)
            except ValueError as e:
                return GenerationResult(
                    success=False,
                    content="",
                    content_type=request.content_type,
                    model="",
                    metadata={},
                    errors=[f"Template rendering error: {str(e)}"],
                )

            # Step 4: Get LLM provider
            provider = request.provider or self.default_provider
            try:
                llm_provider = LLMFactory.get_provider_for_content_type(
                    request.content_type,
                    default_provider=provider,
                )
            except Exception as e:
                return GenerationResult(
                    success=False,
                    content="",
                    content_type=request.content_type,
                    model="",
                    metadata={},
                    errors=[f"LLM provider error: {str(e)}"],
                )

            # Step 5: Generate content
            logger.info(f"Generating {request.content_type} for trend: {request.trend_topic}")
            try:
                llm_response = llm_provider.generate(
                    prompt,
                    temperature=0.7,
                    max_tokens=2048,
                )
            except Exception as e:
                logger.error(f"LLM generation failed: {str(e)}")
                return GenerationResult(
                    success=False,
                    content="",
                    content_type=request.content_type,
                    model=getattr(llm_response, 'model', 'unknown'),
                    metadata={},
                    errors=[f"Generation error: {str(e)}"],
                )

            # Step 6: Parse response
            parsed = ResponseParser.parse(
                llm_response.content,
                request.content_type,
                template.output_format,
            )

            if not parsed.is_valid:
                logger.warning(f"Parser errors for {request.content_type}: {parsed.parse_errors}")
                errors.extend(parsed.parse_errors)

            # Step 7: Validate length (if applicable)
            if request.content_type in ("video_script", "article"):
                is_valid, error_msg = ResponseParser.validate_length(
                    parsed.content,
                    min_words=100,
                )
                if not is_valid:
                    errors.append(error_msg)

            # Build metadata
            result_metadata = {
                "template_used": template.name,
                "model": llm_response.model,
                "tokens_used": llm_response.tokens_used,
                "parser_metadata": parsed.metadata,
            }

            return GenerationResult(
                success=len(errors) == 0,
                content=parsed.content,
                content_type=request.content_type,
                model=llm_response.model,
                metadata=result_metadata,
                errors=errors,
            )

        except Exception as e:
            logger.error(f"Unexpected error in content generation: {str(e)}")
            return GenerationResult(
                success=False,
                content="",
                content_type=request.content_type,
                model="",
                metadata={},
                errors=[f"Unexpected error: {str(e)}"],
            )

    def generate_full_package(
        self,
        trend_topic: str,
        include_types: Optional[list] = None,
    ) -> Dict[str, GenerationResult]:
        """Generate a complete content package for a trend.

        Args:
            trend_topic: The trend topic
            include_types: List of content types to generate (defaults to all)

        Returns:
            Dictionary mapping content type to GenerationResult
        """
        if include_types is None:
            include_types = [
                "video_script",
                "article",
                "caption",
                "thumbnail_description",
                "hashtags",
            ]

        results = {}
        for content_type in include_types:
            request = GenerationRequest(
                trend_topic=trend_topic,
                content_type=content_type,
                provider=self.default_provider,
            )
            results[content_type] = self.generate(request)

        return results

    @staticmethod
    def _prepare_template_variables(
        trend_topic: str,
        content_type: str,
        custom_metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Prepare variables for template rendering.

        Args:
            trend_topic: The trend topic
            content_type: Type of content
            custom_metadata: Additional metadata from request

        Returns:
            Dictionary of template variables
        """
        defaults = {
            # Common variables
            "topic": trend_topic,
            "title": f"{trend_topic} - Latest Insights",

            # Video script defaults
            "duration_seconds": 600,
            "word_count": 1200,
            "tone": "informative and engaging",
            "audience": "general tech audience",

            # Article defaults
            "sections": "Introduction, Context, Analysis, Implications, Conclusion",
            "section_count": 5,

            # Social media defaults
            "platform": "Instagram",
            "include_hashtags": True,
            "hashtag_count": 8,
            "char_limit": 2200,
            "emoji_style": "moderate",

            # Thumbnail defaults
            "video_title": f"Exploring {trend_topic}",
        }

        # Override with custom metadata
        defaults.update(custom_metadata)

        return defaults
