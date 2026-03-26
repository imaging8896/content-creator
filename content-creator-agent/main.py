"""FastAPI application for content generation agent."""
import logging
import os
from typing import List, Optional, Dict, Any
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from content_generator import ContentGenerator, GenerationRequest, GenerationResult
from llm_client import LLMFactory

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize app
app = FastAPI(
    title="Content Creator Agent",
    description="API for generating content from trends using Claude/GPT",
    version="0.1.0"
)

# Initialize generator
generator = ContentGenerator(default_provider="claude")


# Pydantic models for API
class ContentGenerationRequest(BaseModel):
    """Request model for content generation."""
    trend_topic: str = Field(..., description="The trending topic")
    content_type: str = Field(
        "article",
        description="Type: video_script, article, caption, hashtags, thumbnail_description"
    )
    provider: Optional[str] = Field("claude", description="LLM provider: claude or gpt")
    metadata: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Additional metadata for template rendering"
    )


class QualityScoreResponse(BaseModel):
    """Quality score for generated content."""
    overall_score: float
    readability_score: float
    length_score: float
    structure_score: float
    metadata: Dict[str, Any]


class ContentGenerationResponse(BaseModel):
    """Response model for content generation."""
    success: bool
    content: str
    content_type: str
    model: str
    metadata: Dict[str, Any]
    errors: List[str]
    quality_score: Optional[QualityScoreResponse] = None


class FullPackageRequest(BaseModel):
    """Request model for full content package generation."""
    trend_topic: str = Field(..., description="The trending topic")
    content_types: Optional[List[str]] = Field(
        default=None,
        description="List of content types to generate"
    )
    provider: Optional[str] = Field("claude", description="Default LLM provider")


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    providers: List[str]


# API Endpoints

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return HealthResponse(
        status="healthy",
        providers=["claude", "gpt"]
    )


@app.post("/generate", response_model=ContentGenerationResponse)
async def generate_content(request: ContentGenerationRequest) -> ContentGenerationResponse:
    """Generate content for a given trend.

    Args:
        request: ContentGenerationRequest with topic and content type

    Returns:
        Generated content with metadata
    """
    try:
        # Validate provider
        if request.provider and request.provider not in ["claude", "gpt"]:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid provider: {request.provider}. Must be 'claude' or 'gpt'"
            )

        # Create generation request
        gen_request = GenerationRequest(
            trend_topic=request.trend_topic,
            content_type=request.content_type,
            provider=request.provider,
            metadata=request.metadata,
        )

        # Generate
        result = generator.generate(gen_request)

        quality_score_response = None
        if result.quality_score:
            quality_score_response = QualityScoreResponse(
                overall_score=result.quality_score['overall_score'],
                readability_score=result.quality_score['readability_score'],
                length_score=result.quality_score['length_score'],
                structure_score=result.quality_score['structure_score'],
                metadata=result.quality_score['metadata'],
            )

        return ContentGenerationResponse(
            success=result.success,
            content=result.content,
            content_type=result.content_type,
            model=result.model,
            metadata=result.metadata,
            errors=result.errors,
            quality_score=quality_score_response,
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error in /generate: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/generate-package")
async def generate_package(request: FullPackageRequest):
    """Generate a full content package for a trend.

    Args:
        request: FullPackageRequest with topic and optional content types

    Returns:
        Dictionary of content type to generated content
    """
    try:
        # Validate provider
        if request.provider and request.provider not in ["claude", "gpt"]:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid provider: {request.provider}"
            )

        # Override generator provider if specified
        if request.provider:
            generator.default_provider = request.provider

        # Generate package
        results = generator.generate_full_package(
            trend_topic=request.trend_topic,
            include_types=request.content_types,
        )

        # Convert results to JSON-serializable format
        response_dict = {}
        for content_type, result in results.items():
            quality_score_dict = None
            if result.quality_score:
                quality_score_dict = {
                    "overall_score": result.quality_score['overall_score'],
                    "readability_score": result.quality_score['readability_score'],
                    "length_score": result.quality_score['length_score'],
                    "structure_score": result.quality_score['structure_score'],
                    "metadata": result.quality_score['metadata'],
                }

            response_dict[content_type] = {
                "success": result.success,
                "content": result.content,
                "model": result.model,
                "metadata": result.metadata,
                "errors": result.errors,
                "quality_score": quality_score_dict,
            }
        return response_dict

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error in /generate-package: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/supported-types")
async def get_supported_types():
    """Get list of supported content types."""
    from prompt_templates import PromptTemplateLibrary
    return {
        "supported_types": PromptTemplateLibrary.get_all_template_types()
    }


@app.get("/providers")
async def get_providers():
    """Get available LLM providers."""
    return {
        "providers": ["claude", "gpt"],
        "default": "claude"
    }


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8001))
    uvicorn.run(app, host="0.0.0.0", port=port)
