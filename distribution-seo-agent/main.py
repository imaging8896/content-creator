"""FastAPI application for distribution and SEO agent."""
import logging
import os
from typing import List, Optional, Dict, Any
from fastapi import FastAPI, HTTPException, File, UploadFile, Form, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from youtube_api_client import YouTubeAPIClient, VideoMetadata, UploadResult

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize app
app = FastAPI(
    title="Distribution & SEO Agent",
    description="API for distributing content to multiple platforms and optimizing SEO",
    version="0.3.0"
)

# Initialize YouTube client
youtube_client = YouTubeAPIClient()


# Pydantic models
class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    youtube_authenticated: bool
    timestamp: str


class YouTubeUploadRequest(BaseModel):
    """Request model for YouTube video upload."""
    title: str = Field(..., description="Video title")
    description: str = Field(..., description="Video description")
    channel_id: str = Field(..., description="Target YouTube channel ID")
    tags: Optional[List[str]] = Field(None, description="Video tags/keywords")
    privacy_status: str = Field(
        "public",
        description="Privacy status: public, unlisted, or private"
    )
    category_id: str = Field("24", description="YouTube category ID (24=Entertainment)")
    made_for_kids: bool = Field(False, description="Whether video is made for kids")
    notify_subscribers: bool = Field(True, description="Notify channel subscribers")


class YouTubeUploadResponse(BaseModel):
    """Response model for YouTube upload."""
    success: bool
    video_id: Optional[str] = None
    url: Optional[str] = None
    error: Optional[str] = None
    timestamp: str


class VideoStatusResponse(BaseModel):
    """Response model for video status."""
    video_id: str
    status: str
    processing_status: Optional[str] = None
    available_at: Optional[str] = None
    error_details: Optional[Dict[str, Any]] = None


class ChannelInfoResponse(BaseModel):
    """Response model for channel information."""
    channel_id: str
    title: str
    description: Optional[str] = None
    subscriber_count: Optional[str] = None
    view_count: Optional[str] = None
    video_count: Optional[str] = None


# API Endpoints

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    from datetime import datetime
    return HealthResponse(
        status="healthy",
        youtube_authenticated=bool(youtube_client.access_token),
        timestamp=datetime.utcnow().isoformat() + 'Z'
    )


@app.post("/youtube/upload", response_model=YouTubeUploadResponse)
async def upload_youtube_video(
    title: str = Form(...),
    description: str = Form(...),
    channel_id: str = Form(...),
    video_file: UploadFile = File(...),
    thumbnail_file: Optional[UploadFile] = File(None),
    tags: Optional[str] = Form(None),
    privacy_status: str = Form("public"),
    category_id: str = Form("24"),
    made_for_kids: bool = Form(False),
    notify_subscribers: bool = Form(True),
) -> YouTubeUploadResponse:
    """Upload a video to YouTube Shorts.

    Args:
        title: Video title
        description: Video description
        channel_id: Target YouTube channel ID
        video_file: Video file to upload
        thumbnail_file: Optional custom thumbnail image
        tags: Comma-separated tags
        privacy_status: public, unlisted, or private
        category_id: YouTube category ID
        made_for_kids: Whether video is made for kids
        notify_subscribers: Whether to notify subscribers

    Returns:
        YouTubeUploadResponse with video_id if successful
    """
    try:
        if not youtube_client.access_token:
            raise HTTPException(
                status_code=401,
                detail="YouTube authentication required. Set YOUTUBE_ACCESS_TOKEN."
            )

        # Save uploaded files temporarily
        import tempfile
        import shutil

        with tempfile.TemporaryDirectory() as temp_dir:
            # Save video file
            video_path = os.path.join(temp_dir, video_file.filename)
            with open(video_path, 'wb') as f:
                content = await video_file.read()
                f.write(content)

            # Save thumbnail if provided
            thumbnail_path = None
            if thumbnail_file:
                thumbnail_path = os.path.join(temp_dir, thumbnail_file.filename)
                with open(thumbnail_path, 'wb') as f:
                    content = await thumbnail_file.read()
                    f.write(content)

            # Parse tags
            parsed_tags = [t.strip() for t in tags.split(',')] if tags else []

            # Create metadata
            metadata = VideoMetadata(
                title=title,
                description=description,
                channel_id=channel_id,
                video_file_path=video_path,
                thumbnail_file_path=thumbnail_path,
                tags=parsed_tags,
                category_id=category_id,
                privacy_status=privacy_status,
                made_for_kids=made_for_kids,
                notify_subscribers=notify_subscribers,
            )

            # Upload to YouTube
            result = youtube_client.upload_video(metadata)

            return YouTubeUploadResponse(
                success=result.success,
                video_id=result.video_id,
                url=result.url,
                error=result.error,
                timestamp=result.timestamp
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading video: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/youtube/video/{video_id}/status", response_model=VideoStatusResponse)
async def get_video_status(video_id: str) -> VideoStatusResponse:
    """Get the status of a YouTube video.

    Args:
        video_id: YouTube video ID

    Returns:
        VideoStatusResponse with current processing status
    """
    try:
        if not youtube_client.access_token:
            raise HTTPException(
                status_code=401,
                detail="YouTube authentication required."
            )

        status_info = youtube_client.get_video_status(video_id)

        if not status_info:
            raise HTTPException(
                status_code=404,
                detail=f"Video {video_id} not found"
            )

        status = status_info.get("status", {}).get("uploadStatus")
        processing = status_info.get("processingDetails", {}).get("processingStatus")
        available_at = status_info.get("processingDetails", {}).get("processingFailureReason")
        failure_reason = status_info.get("processingDetails", {}).get("processingFailureReason")

        return VideoStatusResponse(
            video_id=video_id,
            status=status or "unknown",
            processing_status=processing,
            available_at=available_at,
            error_details={"failure_reason": failure_reason} if failure_reason else None
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting video status: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.patch("/youtube/video/{video_id}", response_model=Dict[str, Any])
async def update_video(
    video_id: str,
    title: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    tags: Optional[str] = Form(None),
    privacy_status: Optional[str] = Form(None),
) -> Dict[str, Any]:
    """Update YouTube video metadata.

    Args:
        video_id: YouTube video ID
        title: New video title
        description: New video description
        tags: New tags (comma-separated)
        privacy_status: New privacy status

    Returns:
        Confirmation of update
    """
    try:
        if not youtube_client.access_token:
            raise HTTPException(
                status_code=401,
                detail="YouTube authentication required."
            )

        updates: Dict[str, Any] = {}

        if title or description or tags:
            snippet = {}
            if title:
                snippet["title"] = title
            if description:
                snippet["description"] = description
            if tags:
                snippet["tags"] = [t.strip() for t in tags.split(',')]
            updates["snippet"] = snippet

        if privacy_status:
            updates["status"] = {"privacyStatus": privacy_status}

        if not updates:
            return {
                "success": False,
                "message": "No fields to update"
            }

        success = youtube_client.update_video(video_id, updates)

        return {
            "success": success,
            "video_id": video_id,
            "message": "Video updated successfully" if success else "Failed to update video"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating video: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/youtube/channel/{channel_id}/info", response_model=ChannelInfoResponse)
async def get_channel_info(channel_id: str) -> ChannelInfoResponse:
    """Get information about a YouTube channel.

    Args:
        channel_id: YouTube channel ID

    Returns:
        ChannelInfoResponse with channel statistics
    """
    try:
        if not youtube_client.access_token:
            raise HTTPException(
                status_code=401,
                detail="YouTube authentication required."
            )

        channel_info = youtube_client.get_channel_info(channel_id)

        if not channel_info:
            raise HTTPException(
                status_code=404,
                detail=f"Channel {channel_id} not found"
            )

        snippet = channel_info.get("snippet", {})
        statistics = channel_info.get("statistics", {})

        return ChannelInfoResponse(
            channel_id=channel_id,
            title=snippet.get("title", ""),
            description=snippet.get("description"),
            subscriber_count=statistics.get("subscriberCount"),
            view_count=statistics.get("viewCount"),
            video_count=statistics.get("videoCount"),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting channel info: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/youtube/channels/{channel_id}/videos")
async def list_channel_videos(
    channel_id: str,
    max_results: int = Query(25, ge=1, le=50),
    page_token: Optional[str] = Query(None)
) -> Dict[str, Any]:
    """List videos from a YouTube channel.

    Args:
        channel_id: YouTube channel ID
        max_results: Maximum results to return (1-50)
        page_token: Pagination token

    Returns:
        List of videos with pagination info
    """
    try:
        if not youtube_client.access_token:
            raise HTTPException(
                status_code=401,
                detail="YouTube authentication required."
            )

        videos = youtube_client.list_videos(
            channel_id=channel_id,
            max_results=max_results,
            page_token=page_token
        )

        if not videos:
            raise HTTPException(
                status_code=404,
                detail=f"No videos found for channel {channel_id}"
            )

        return videos

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing videos: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/youtube/refresh-token", response_model=Dict[str, Any])
async def refresh_youtube_token() -> Dict[str, Any]:
    """Refresh the YouTube access token.

    Returns:
        Confirmation of token refresh
    """
    try:
        success = youtube_client.refresh_access_token()

        return {
            "success": success,
            "message": "Token refreshed successfully" if success else "Failed to refresh token",
            "error": youtube_client.last_error
        }

    except Exception as e:
        logger.error(f"Error refreshing token: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/youtube/status", response_model=Dict[str, Any])
async def get_youtube_status() -> Dict[str, Any]:
    """Get current YouTube API status and authentication state.

    Returns:
        Status information
    """
    return {
        "authenticated": bool(youtube_client.access_token),
        "has_refresh_token": bool(youtube_client.refresh_token),
        "last_error": youtube_client.last_error,
        "endpoints": [
            "POST /youtube/upload",
            "GET /youtube/video/{video_id}/status",
            "PATCH /youtube/video/{video_id}",
            "GET /youtube/channel/{channel_id}/info",
            "GET /youtube/channels/{channel_id}/videos",
            "POST /youtube/refresh-token"
        ]
    }


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8002))
    uvicorn.run(app, host="0.0.0.0", port=port)
