"""FastAPI application for content generation agent."""
import logging
import os
import uuid
from typing import List, Optional, Dict, Any
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from content_generator import ContentGenerator, GenerationRequest, GenerationResult
from llm_client import LLMFactory
from content_storage import ContentStorage
from quality_review_queue import QualityReviewQueue, ReviewFeedback

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
    version="0.2.0"
)

# Initialize generator, storage, and review queue
generator = ContentGenerator(default_provider="claude")
storage = ContentStorage()
review_queue = QualityReviewQueue(storage)


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


class ReviewItemResponse(BaseModel):
    """Review item for the quality review queue."""
    id: str
    trend_topic: str
    content_type: str
    content: str
    provider: str
    quality_score: float
    created_at: str
    metadata: Dict[str, Any]


class ReviewFeedbackRequest(BaseModel):
    """Request to submit review feedback."""
    content_id: str = Field(..., description="ID of content being reviewed")
    status: str = Field(..., description="'approved' or 'rejected'")
    feedback: Optional[str] = Field(None, description="Optional reviewer feedback")
    reviewer_id: Optional[str] = Field(None, description="ID of reviewer")


class QualityMetricsResponse(BaseModel):
    """Quality metrics response."""
    period_days: int
    total_content: int
    sampled_content: int
    sampling_rate: float
    reviewed_content: int
    approved_content: int
    rejected_content: int
    rejection_rate: float
    average_quality_score: float
    high_quality_count: int
    meets_target_rejection_rate: bool
    meets_target_quality_score: bool
    health_status: str


class RecommendationResponse(BaseModel):
    """Quality improvement recommendations."""
    actions: List[str]
    focus_areas: List[str]
    positive_notes: List[str]


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
        quality_score_value = 0.0
        if result.quality_score:
            quality_score_response = QualityScoreResponse(
                overall_score=result.quality_score['overall_score'],
                readability_score=result.quality_score['readability_score'],
                length_score=result.quality_score['length_score'],
                structure_score=result.quality_score['structure_score'],
                metadata=result.quality_score['metadata'],
            )
            quality_score_value = result.quality_score['overall_score']

        # Store generated content if successful
        if result.success:
            content_id = str(uuid.uuid4())
            storage.store_content(
                content_id=content_id,
                trend_topic=request.trend_topic,
                content_type=request.content_type,
                content=result.content,
                provider=request.provider,
                quality_score=quality_score_value,
                metadata=result.metadata or {},
            )

            # Process for quality review (10% sampling)
            sampled = review_queue.process_generated_content(content_id)
            logger.info(f"Content {content_id} stored, sampled_for_review={sampled}")

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


# Quality Review Queue Endpoints

@app.get("/review-queue", response_model=List[ReviewItemResponse])
async def get_review_queue(limit: int = Query(10, ge=1, le=100)):
    """Get pending items from the quality review queue.

    Args:
        limit: Maximum number of items to return

    Returns:
        List of content items pending human review
    """
    try:
        items = review_queue.get_review_queue(limit)
        return [
            ReviewItemResponse(
                id=item.id,
                trend_topic=item.trend_topic,
                content_type=item.content_type,
                content=item.content,
                provider=item.provider,
                quality_score=item.quality_score,
                created_at=item.created_at,
                metadata=item.metadata,
            )
            for item in items
        ]
    except Exception as e:
        logger.error(f"Error retrieving review queue: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/submit-review")
async def submit_review(request: ReviewFeedbackRequest) -> Dict[str, Any]:
    """Submit review feedback for generated content.

    Args:
        request: ReviewFeedbackRequest with content ID, status, and optional feedback

    Returns:
        Confirmation of review submission
    """
    try:
        # Validate status
        if request.status not in ['approved', 'rejected']:
            raise HTTPException(
                status_code=400,
                detail="Status must be 'approved' or 'rejected'"
            )

        feedback = ReviewFeedback(
            content_id=request.content_id,
            status=request.status,
            feedback=request.feedback,
            reviewer_id=request.reviewer_id,
        )

        success = review_queue.submit_review(feedback)

        if not success:
            raise HTTPException(
                status_code=400,
                detail=f"Failed to submit review for content {request.content_id}"
            )

        return {
            "success": True,
            "content_id": request.content_id,
            "status": request.status,
            "message": f"Content {request.status} successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error submitting review: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/quality-metrics", response_model=QualityMetricsResponse)
async def get_quality_metrics(days: int = Query(7, ge=1, le=90)):
    """Get quality review metrics and statistics.

    Args:
        days: Number of days to look back (default 7, max 90)

    Returns:
        Quality metrics including rejection rate, average scores, and health status
    """
    try:
        metrics = review_queue.get_quality_metrics(days)
        return QualityMetricsResponse(**metrics)
    except Exception as e:
        logger.error(f"Error retrieving quality metrics: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/quality-recommendations", response_model=RecommendationResponse)
async def get_recommendations() -> RecommendationResponse:
    """Get recommendations for improving content quality.

    Returns:
        Recommendations based on current quality metrics and targets
    """
    try:
        recommendations = review_queue.get_recommendations()
        return RecommendationResponse(**recommendations)
    except Exception as e:
        logger.error(f"Error retrieving recommendations: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/batch-sample-unreviewed")
async def batch_sample_unreviewed(limit: int = Query(100, ge=1, le=1000)) -> Dict[str, Any]:
    """Batch process unsampled content and add 10% to review queue.

    Useful for backfilling sampling coverage on existing content.

    Args:
        limit: Maximum number of unsampled items to process

    Returns:
        Count of items added to review queue
    """
    try:
        sampled_count = review_queue.batch_process_unsampled_content(limit)
        return {
            "success": True,
            "sampled_count": sampled_count,
            "message": f"{sampled_count} items added to review queue"
        }
    except Exception as e:
        logger.error(f"Error in batch sampling: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8001))
    uvicorn.run(app, host="0.0.0.0", port=port)
