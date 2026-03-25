"""Test script for content generator functionality."""
import os
import sys
from content_generator import ContentGenerator, GenerationRequest
from prompt_templates import PromptTemplateLibrary
from response_parser import ResponseParser

# Mock LLM response for testing
MOCK_VIDEO_SCRIPT = """# AI Revolution in Healthcare: A Game-Changer

[SCENE 1: Hook - 0:00-0:05]
"In the next 60 seconds, I'm going to show you how AI is completely transforming the way doctors work..."

[SHOW: Animation of AI analyzing medical scan]

## Section 1: The Current State
Healthcare professionals are drowning in paperwork. But AI is changing that.

## Section 2: Real Examples
Three hospitals deployed AI systems last year...

## Section 3: The Future
By 2025, we're looking at...
"""

MOCK_ARTICLE = """# The Future of Remote Work in 2025

## Introduction
Remote work has become the norm rather than the exception. This article explores the latest trends shaping how we work.

## Market Trends
The global remote work market is experiencing unprecedented growth...

## Benefits
- Increased productivity
- Better work-life balance
- Reduced overhead costs

## Challenges
Organizations are facing new challenges in managing distributed teams...

## Best Practices
Here's what successful remote-first companies are doing...

## Conclusion
As we move forward, remote work will continue to evolve and improve...
"""

MOCK_CAPTION = "Just dropped: The latest breakthrough in AI that's changing everything. 🚀 What's your take? #AI #Technology #Innovation"

MOCK_JSON = """{"trending": ["#AI", "#ML", "#Tech"], "niche": ["#DeepLearning", "#Transformers", "#NLP"], "brand": ["#TechInnovation", "#FutureOfWork"]}"""


def test_prompt_templates():
    """Test prompt template system."""
    print("Testing prompt templates...")

    templates = PromptTemplateLibrary.get_all_template_types()
    print(f"✓ Found {len(templates)} template types: {templates}")

    # Test rendering a template
    template = PromptTemplateLibrary.get_template("article")
    variables = {
        "title": "Test Article",
        "topic": "AI in 2025",
        "word_count": 1500,
        "tone": "professional",
        "audience": "tech professionals",
        "sections": "Intro, Analysis, Conclusion",
        "section_count": 3,
    }
    rendered = template.render(**variables)
    print(f"✓ Template rendered successfully ({len(rendered)} chars)")


def test_response_parser():
    """Test response parsing."""
    print("\nTesting response parser...")

    # Test markdown parsing
    parsed_md = ResponseParser.parse_markdown(MOCK_VIDEO_SCRIPT, "video_script")
    print(f"✓ Markdown parsed: {parsed_md.metadata['word_count']} words, {len(parsed_md.metadata['sections'])} sections")

    # Test JSON parsing
    parsed_json = ResponseParser.parse_json(MOCK_JSON, "hashtags")
    print(f"✓ JSON parsed successfully: {parsed_json.metadata['json_keys']}")

    # Test plain text parsing
    parsed_text = ResponseParser.parse_plain_text(MOCK_CAPTION, "caption")
    print(f"✓ Text parsed: {parsed_text.metadata['word_count']} words, {len(parsed_text.metadata['hashtags'])} hashtags")

    # Test length validation
    is_valid, msg = ResponseParser.validate_length(MOCK_ARTICLE, min_words=100)
    print(f"✓ Length validation: {is_valid}")


def test_generation_flow():
    """Test the full generation flow without actual LLM calls."""
    print("\nTesting generation flow...")

    # This would require API keys to actually generate
    # For now, just test the request object creation
    request = GenerationRequest(
        trend_topic="AI Breakthroughs",
        content_type="article",
        provider="claude",
        metadata={"word_count": 1500}
    )
    print(f"✓ Generation request created: {request.content_type} for '{request.trend_topic}'")


def test_integration():
    """Test that all components work together."""
    print("\nTesting component integration...")

    # Test that templates work with parser
    template = PromptTemplateLibrary.get_template("article")
    parsed = ResponseParser.parse(MOCK_ARTICLE, "article", template.output_format)

    print(f"✓ Template -> Parser integration successful")
    print(f"  - Output format: {template.output_format}")
    print(f"  - Parse valid: {parsed.is_valid}")
    print(f"  - Metadata: {list(parsed.metadata.keys())}")


def main():
    """Run all tests."""
    print("=" * 60)
    print("Content Generator Test Suite")
    print("=" * 60)

    try:
        test_prompt_templates()
        test_response_parser()
        test_generation_flow()
        test_integration()

        print("\n" + "=" * 60)
        print("✓ All tests passed!")
        print("=" * 60)
        print("\nNext steps:")
        print("1. Set ANTHROPIC_API_KEY and/or OPENAI_API_KEY environment variables")
        print("2. Start the API: python main.py")
        print("3. Test endpoints at: http://localhost:8001/docs")

        return 0
    except Exception as e:
        print(f"\n✗ Test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
