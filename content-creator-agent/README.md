# Content Creator Agent

LLM-based content generation system for the Automated Content & Traffic Empire project. Generates multiple content formats from trending topics.

## Features

- **Multi-Format Content Generation**: Video scripts, articles, social media captions, hashtags, and thumbnail descriptions
- **Dual LLM Support**: Claude 3.5 Sonnet and OpenAI GPT-4 Turbo
- **Intelligent Provider Selection**: Automatically selects optimal LLM based on content type
- **Template System**: Structured prompt templates for consistent, high-quality output
- **Response Parsing**: Validates and extracts content in multiple formats (markdown, JSON, text)
- **Error Handling**: Comprehensive error handling and validation

## Architecture

### Core Components

1. **llm_client.py** - LLM provider abstraction
   - `ClaudeClient`: Anthropic API integration
   - `GPTClient`: OpenAI API integration
   - `LLMFactory`: Provider factory with content-type optimization

2. **prompt_templates.py** - Prompt template library
   - Structured templates for each content type
   - Template rendering with variable substitution
   - Output format specification (markdown, JSON, text)

3. **response_parser.py** - Response parsing and validation
   - Format-specific parsers (markdown, JSON, plain text)
   - Content extraction (sections, metadata)
   - Length validation

4. **content_generator.py** - Main orchestrator
   - `ContentGenerator`: Coordinates templates, LLM, and parsing
   - `GenerationRequest`: Input specification
   - `GenerationResult`: Structured output

5. **main.py** - FastAPI application
   - RESTful API endpoints
   - Health checks
   - Supported types and providers discovery

## Supported Content Types

- **video_script**: YouTube video scripts (markdown format)
- **article**: Blog articles (markdown format)
- **caption**: Social media captions (plain text)
- **hashtags**: Hashtag sets (JSON format)
- **thumbnail_description**: Video metadata and descriptions (JSON format)

## API Endpoints

### Health Check
```
GET /health
```
Returns service health status and available providers.

### Generate Single Content
```
POST /generate
Content-Type: application/json

{
  "trend_topic": "AI in healthcare",
  "content_type": "article",
  "provider": "claude",
  "metadata": {
    "word_count": 2000,
    "audience": "medical professionals"
  }
}
```

### Generate Content Package
```
POST /generate-package
Content-Type: application/json

{
  "trend_topic": "Quantum computing breakthroughs",
  "content_types": ["video_script", "article", "caption"],
  "provider": "claude"
}
```

### Get Supported Content Types
```
GET /supported-types
```

### Get Available Providers
```
GET /providers
```

## Setup

### Installation

```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables
export ANTHROPIC_API_KEY="your-key-here"
export OPENAI_API_KEY="your-key-here"
```

### Running the Service

```bash
# Development
python main.py

# Or with uvicorn directly
uvicorn main:app --reload --port 8001
```

The API will be available at `http://localhost:8001`.

API documentation: `http://localhost:8001/docs`

## Model Selection Strategy

Provider selection is optimized by content type:

| Content Type | Provider | Reason |
|---|---|---|
| video_script | Claude | Better narrative structure |
| article | Claude | Superior long-form writing |
| caption | GPT | Fast, good for short text |
| hashtags | GPT | Efficient tag generation |
| thumbnail_description | GPT | Concise metadata generation |

## Error Handling

The system provides detailed error reporting:

1. **Invalid Templates**: Returns error if content type not supported
2. **API Failures**: Catches LLM API errors with retry logic potential
3. **Parsing Errors**: Validates response format and returns parse errors
4. **Length Validation**: Checks word count for long-form content

All errors are returned in the `errors` field of the response with descriptive messages.

## Integration with Trend Discovery Agent

The Content Creator Agent consumes output from the Trend Discovery Agent:

1. Trend Discovery identifies high-opportunity trends
2. Content Creator generates multiple content formats per trend
3. Content is scored and queued for distribution

## Performance Considerations

- **Token Usage**: Tracked in response metadata for cost optimization
- **Template Caching**: Templates are loaded once and reused
- **Provider Selection**: Chosen based on content type to optimize cost/quality
- **Concurrent Generation**: Design supports async batch generation

## Testing

```bash
# Unit tests (to be added)
pytest test_*.py

# Manual testing via API docs
curl -X POST http://localhost:8001/generate \
  -H "Content-Type: application/json" \
  -d '{
    "trend_topic": "AI safety research",
    "content_type": "article",
    "provider": "claude"
  }'
```

## Success Metrics (Phase 2 Deadline: 2026-04-20)

- ✓ Dual LLM integration (Claude + GPT)
- ✓ 5+ content types supported
- ✓ Response parsing with validation
- ✓ Error handling framework
- 5+ pieces/day generation capacity
- Average quality score >70/100
- <5% human rejection rate

## Next Steps

1. Integration testing with Trend Discovery Agent
2. Quality scoring module implementation
3. Database storage for generated content
4. Batch generation pipeline (hourly/daily)
5. Content review queue for human sampling
6. Performance monitoring and optimization
