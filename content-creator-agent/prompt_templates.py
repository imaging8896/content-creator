"""Prompt templates for different content types."""
from typing import Dict, Any
from dataclasses import dataclass
import json


@dataclass
class PromptTemplate:
    """A prompt template for content generation."""
    name: str
    template: str
    content_type: str
    output_format: str
    example_variables: Dict[str, Any]

    def render(self, **kwargs) -> str:
        """Render the template with provided variables.

        Args:
            **kwargs: Variables to fill in the template

        Returns:
            Rendered prompt string
        """
        try:
            return self.template.format(**kwargs)
        except KeyError as e:
            raise ValueError(f"Missing template variable: {e}")


class PromptTemplateLibrary:
    """Library of prompt templates for different content types."""

    @staticmethod
    def get_video_script_template() -> PromptTemplate:
        """Template for YouTube video scripts."""
        return PromptTemplate(
            name="youtube_video_script",
            content_type="video_script",
            output_format="markdown",
            template="""You are an expert YouTube content creator. Create an engaging video script for a YouTube video.

**Topic:** {topic}
**Video Duration:** {duration_seconds} seconds (approximately {word_count} words)
**Tone:** {tone}
**Target Audience:** {audience}

Requirements:
- Start with a hook in the first 3 seconds to grab attention
- Use clear section breaks with [SCENE] markers
- Include visual directions in brackets like [SHOW: image/graph]
- Add speaking notes for pacing and emphasis
- Include a call-to-action at the end
- Make it conversational and engaging
- Length: approximately {word_count} words

Format your response as a structured script with sections.""",
            example_variables={
                "topic": "How AI is changing the job market",
                "duration_seconds": 600,
                "word_count": 1200,
                "tone": "informative and conversational",
                "audience": "tech professionals and job seekers",
            }
        )

    @staticmethod
    def get_article_template() -> PromptTemplate:
        """Template for blog articles."""
        return PromptTemplate(
            name="blog_article",
            content_type="article",
            output_format="markdown",
            template="""You are an expert blog writer. Create a well-researched blog article.

**Title:** {title}
**Topic:** {topic}
**Word Count:** {word_count} words
**Tone:** {tone}
**Target Audience:** {audience}
**Sections:** {sections}

Requirements:
- Write an engaging introduction that hooks the reader
- Include {section_count} main sections with subheadings
- Use clear, concise language
- Include relevant examples and facts
- Add a conclusion that summarizes key points
- Include a call-to-action or next steps
- Optimize for readability with short paragraphs
- Target word count: {word_count}

Format your response as a complete article with proper markdown formatting.""",
            example_variables={
                "title": "The Future of Remote Work in 2025",
                "topic": "Remote work trends",
                "word_count": 2000,
                "tone": "professional and informative",
                "audience": "business professionals",
                "sections": "Introduction, Market Trends, Benefits, Challenges, Best Practices, Conclusion",
                "section_count": 6,
            }
        )

    @staticmethod
    def get_social_media_caption_template() -> PromptTemplate:
        """Template for social media captions."""
        return PromptTemplate(
            name="social_caption",
            content_type="caption",
            output_format="text",
            template="""Create an engaging social media caption.

**Platform:** {platform}
**Topic:** {topic}
**Tone:** {tone}
**Include Hashtags:** {include_hashtags}
**Character Limit:** {char_limit}

Requirements:
- Be engaging and conversational
- Hook readers in the first line
- If hashtags requested: include {hashtag_count} relevant hashtags
- Emojis: use {emoji_style}
- Keep under {char_limit} characters
- Include call-to-action if appropriate
- Match the tone: {tone}

Create a caption optimized for {platform}.""",
            example_variables={
                "platform": "Instagram",
                "topic": "New AI technology",
                "tone": "exciting and trendy",
                "include_hashtags": True,
                "char_limit": 2200,
                "hashtag_count": 8,
                "emoji_style": "moderate",
            }
        )

    @staticmethod
    def get_thumbnail_description_template() -> PromptTemplate:
        """Template for video thumbnail descriptions and metadata."""
        return PromptTemplate(
            name="thumbnail_metadata",
            content_type="thumbnail_description",
            output_format="json",
            template="""Create metadata for a video thumbnail.

**Topic:** {topic}
**Video Title:** {video_title}
**Platform:** {platform}

Generate JSON with:
- "title": SEO-optimized title (60 chars max)
- "description": Brief description for search
- "keywords": List of relevant keywords
- "thumbnail_suggestion": What to show visually
- "visual_elements": Key design elements

Format as valid JSON.""",
            example_variables={
                "topic": "AI trends 2025",
                "video_title": "The Future of AI",
                "platform": "YouTube",
            }
        )

    @staticmethod
    def get_hashtags_template() -> PromptTemplate:
        """Template for generating hashtags."""
        return PromptTemplate(
            name="hashtag_generator",
            content_type="hashtags",
            output_format="json",
            template="""Generate relevant hashtags for content.

**Topic:** {topic}
**Platform:** {platform}
**Content Type:** {content_type}
**Trending Context:** {trending_context}

Generate JSON with:
- "trending": List of {hashtag_count} trending/popular hashtags
- "niche": List of {hashtag_count} niche hashtags
- "brand": List of {hashtag_count} brand-related hashtags

Each hashtag should be practical and increase discoverability.
Format as valid JSON.""",
            example_variables={
                "topic": "AI and machine learning",
                "platform": "Twitter",
                "content_type": "news article",
                "trending_context": "AI is trending",
                "hashtag_count": 5,
            }
        )

    @classmethod
    def get_template(cls, content_type: str) -> PromptTemplate:
        """Get a template by content type.

        Args:
            content_type: Type of content (video_script, article, caption, etc.)

        Returns:
            PromptTemplate instance

        Raises:
            ValueError: If content type not found
        """
        templates = {
            "video_script": cls.get_video_script_template(),
            "article": cls.get_article_template(),
            "caption": cls.get_social_media_caption_template(),
            "thumbnail_description": cls.get_thumbnail_description_template(),
            "hashtags": cls.get_hashtags_template(),
        }

        if content_type not in templates:
            raise ValueError(f"Unknown content type: {content_type}")

        return templates[content_type]

    @classmethod
    def get_all_template_types(cls) -> list:
        """Get list of available template types.

        Returns:
            List of content type strings
        """
        return [
            "video_script",
            "article",
            "caption",
            "thumbnail_description",
            "hashtags",
        ]
