"""LLM client module for content generation using Claude and OpenAI GPT."""
import logging
import os
from typing import Optional, Literal
from abc import ABC, abstractmethod
from dataclasses import dataclass
import anthropic
import openai

logger = logging.getLogger(__name__)


@dataclass
class ContentResponse:
    """Structured response from content generation."""
    content: str
    model: str
    tokens_used: Optional[int] = None
    stop_reason: Optional[str] = None


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    def generate(self, prompt: str, **kwargs) -> ContentResponse:
        """Generate content using the LLM."""
        pass


class ClaudeClient(LLMProvider):
    """Claude API client for content generation."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "claude-3-5-sonnet-20241022",
        max_tokens: int = 2048,
    ):
        """Initialize Claude client.

        Args:
            api_key: Anthropic API key (defaults to ANTHROPIC_API_KEY env var)
            model: Model to use (defaults to claude-3-5-sonnet)
            max_tokens: Maximum tokens in response
        """
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self.model = model
        self.max_tokens = max_tokens

        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable not set")

        self.client = anthropic.Anthropic(api_key=self.api_key)

    def generate(self, prompt: str, **kwargs) -> ContentResponse:
        """Generate content using Claude.

        Args:
            prompt: The prompt to send to Claude
            **kwargs: Additional parameters (temperature, max_tokens, etc.)

        Returns:
            ContentResponse with generated content
        """
        try:
            max_tokens = kwargs.get("max_tokens", self.max_tokens)
            temperature = kwargs.get("temperature", 0.7)

            message = self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                temperature=temperature,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )

            content = message.content[0].text

            return ContentResponse(
                content=content,
                model=self.model,
                tokens_used=message.usage.output_tokens,
                stop_reason=message.stop_reason
            )
        except anthropic.APIError as e:
            logger.error(f"Claude API error: {str(e)}")
            raise


class GPTClient(LLMProvider):
    """OpenAI GPT client for content generation."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gpt-4-turbo-preview",
        max_tokens: int = 2048,
    ):
        """Initialize GPT client.

        Args:
            api_key: OpenAI API key (defaults to OPENAI_API_KEY env var)
            model: Model to use (defaults to gpt-4-turbo-preview)
            max_tokens: Maximum tokens in response
        """
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = model
        self.max_tokens = max_tokens

        if not self.api_key:
            raise ValueError("OPENAI_API_KEY environment variable not set")

        openai.api_key = self.api_key
        self.client = openai.OpenAI(api_key=self.api_key)

    def generate(self, prompt: str, **kwargs) -> ContentResponse:
        """Generate content using GPT.

        Args:
            prompt: The prompt to send to GPT
            **kwargs: Additional parameters (temperature, max_tokens, etc.)

        Returns:
            ContentResponse with generated content
        """
        try:
            max_tokens = kwargs.get("max_tokens", self.max_tokens)
            temperature = kwargs.get("temperature", 0.7)

            response = self.client.chat.completions.create(
                model=self.model,
                max_tokens=max_tokens,
                temperature=temperature,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )

            content = response.choices[0].message.content

            return ContentResponse(
                content=content,
                model=self.model,
                tokens_used=response.usage.completion_tokens,
                stop_reason=response.choices[0].finish_reason
            )
        except openai.APIError as e:
            logger.error(f"OpenAI API error: {str(e)}")
            raise


class LLMFactory:
    """Factory for creating LLM clients based on content type and configuration."""

    _providers = {
        "claude": ClaudeClient,
        "gpt": GPTClient,
    }

    @classmethod
    def get_provider(
        cls,
        provider_name: Literal["claude", "gpt"],
        **kwargs
    ) -> LLMProvider:
        """Get an LLM provider instance.

        Args:
            provider_name: Name of the provider ("claude" or "gpt")
            **kwargs: Provider-specific kwargs (api_key, model, etc.)

        Returns:
            LLMProvider instance
        """
        provider_class = cls._providers.get(provider_name.lower())
        if not provider_class:
            raise ValueError(f"Unknown provider: {provider_name}")

        return provider_class(**kwargs)

    @classmethod
    def get_provider_for_content_type(
        cls,
        content_type: str,
        default_provider: str = "claude",
    ) -> LLMProvider:
        """Get a provider optimized for a specific content type.

        Args:
            content_type: Type of content (e.g., "video_script", "article", "caption")
            default_provider: Provider to use if no optimization exists

        Returns:
            LLMProvider instance
        """
        # Provider selection based on content type and quality/cost tradeoffs
        provider_map = {
            "video_script": "claude",      # Better narrative structure
            "article": "claude",            # Better long-form writing
            "caption": "gpt",               # Fast, good for short text
            "thumbnail_description": "gpt", # Fast, concise
            "hashtags": "gpt",              # Efficient for tags
        }

        provider_name = provider_map.get(content_type, default_provider)
        return cls.get_provider(provider_name)
