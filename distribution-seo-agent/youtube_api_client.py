"""YouTube Data API client for uploading Shorts and managing videos."""
import os
import json
import logging
import mimetypes
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime
import requests
from requests.exceptions import RequestException, Timeout

# Configure logging
logger = logging.getLogger(__name__)


@dataclass
class VideoMetadata:
    """Video metadata for YouTube upload."""
    title: str
    description: str
    channel_id: str
    video_file_path: str
    thumbnail_file_path: Optional[str] = None
    tags: Optional[List[str]] = None
    category_id: str = "24"  # Entertainment category
    privacy_status: str = "public"  # public, unlisted, private
    made_for_kids: bool = False
    auto_chapters: bool = True
    auto_language: bool = True
    notify_subscribers: bool = True


@dataclass
class UploadResult:
    """Result of a video upload operation."""
    success: bool
    video_id: Optional[str] = None
    url: Optional[str] = None
    error: Optional[str] = None
    timestamp: str = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow().isoformat() + 'Z'


class YouTubeAPIClient:
    """Client for YouTube Data API v3 operations."""

    API_BASE_URL = "https://www.googleapis.com/youtube/v3"
    UPLOAD_TIMEOUT = 300  # 5 minutes for uploads
    RETRY_COUNT = 3

    def __init__(
        self,
        access_token: Optional[str] = None,
        api_key: Optional[str] = None,
        refresh_token: Optional[str] = None,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
    ):
        """Initialize YouTube API client.

        Args:
            access_token: OAuth2 access token for authenticated requests
            api_key: API key for quota-free requests (limited to public data)
            refresh_token: Refresh token for automatic access token renewal
            client_id: OAuth2 client ID for token refresh
            client_secret: OAuth2 client secret for token refresh
        """
        self.access_token = access_token
        self.api_key = api_key
        self.refresh_token = refresh_token
        self.client_id = client_id
        self.client_secret = client_secret

        # Load from environment if not provided
        if not self.access_token:
            self.access_token = os.getenv("YOUTUBE_ACCESS_TOKEN")
        if not self.api_key:
            self.api_key = os.getenv("YOUTUBE_API_KEY")
        if not self.refresh_token:
            self.refresh_token = os.getenv("YOUTUBE_REFRESH_TOKEN")
        if not self.client_id:
            self.client_id = os.getenv("YOUTUBE_CLIENT_ID")
        if not self.client_secret:
            self.client_secret = os.getenv("YOUTUBE_CLIENT_SECRET")

        self.session = requests.Session()
        self.upload_session_uri: Optional[str] = None
        self.last_error: Optional[str] = None

    def _get_headers(self) -> Dict[str, str]:
        """Get authorization headers for API requests."""
        headers = {
            "User-Agent": "ContentCreatorAgent/1.0"
        }

        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"

        return headers

    def _get_params(self) -> Dict[str, str]:
        """Get query parameters for API requests."""
        params = {}

        if not self.access_token and self.api_key:
            params["key"] = self.api_key

        return params

    def refresh_access_token(self) -> bool:
        """Refresh the access token using refresh token."""
        if not all([self.refresh_token, self.client_id, self.client_secret]):
            logger.warning("Cannot refresh access token: missing refresh_token, client_id, or client_secret")
            return False

        try:
            url = "https://oauth2.googleapis.com/token"
            data = {
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "refresh_token": self.refresh_token,
                "grant_type": "refresh_token"
            }

            response = self.session.post(url, data=data, timeout=10)
            response.raise_for_status()

            token_data = response.json()
            self.access_token = token_data.get("access_token")

            if self.access_token:
                logger.info("Successfully refreshed access token")
                return True
            else:
                logger.error("No access token in refresh response")
                return False

        except Exception as e:
            logger.error(f"Failed to refresh access token: {e}")
            self.last_error = str(e)
            return False

    def upload_video(self, metadata: VideoMetadata) -> UploadResult:
        """Upload a video to YouTube.

        Args:
            metadata: VideoMetadata object with video details

        Returns:
            UploadResult with video_id if successful
        """
        if not self.access_token:
            error = "Access token required for video uploads"
            logger.error(error)
            self.last_error = error
            return UploadResult(success=False, error=error)

        # Validate video file exists
        if not os.path.exists(metadata.video_file_path):
            error = f"Video file not found: {metadata.video_file_path}"
            logger.error(error)
            self.last_error = error
            return UploadResult(success=False, error=error)

        # Get file size
        file_size = os.path.getsize(metadata.video_file_path)
        logger.info(f"Starting upload of {metadata.video_file_path} ({file_size} bytes)")

        # Prepare upload request body
        body = {
            "snippet": {
                "title": metadata.title,
                "description": metadata.description,
                "tags": metadata.tags or [],
                "categoryId": metadata.category_id,
            },
            "status": {
                "privacyStatus": metadata.privacy_status,
                "madeForKids": metadata.made_for_kids,
                "selfDeclaredMadeForKids": metadata.made_for_kids,
            },
            "processingDetails": {
                "processingStatus": "processing"
            }
        }

        # Add optional settings
        if metadata.auto_chapters:
            body["processingDetails"]["processingProgress"] = {
                "partsProcessed": 0,
                "partsTotal": 1
            }

        try:
            # Initialize resumable upload session
            upload_session_uri = self._initialize_resumable_upload(metadata, body)

            if not upload_session_uri:
                error = "Failed to initialize resumable upload session"
                logger.error(error)
                self.last_error = error
                return UploadResult(success=False, error=error)

            # Upload the video content
            video_id = self._upload_video_content(upload_session_uri, metadata)

            if video_id:
                # Upload thumbnail if provided
                if metadata.thumbnail_file_path and os.path.exists(metadata.thumbnail_file_path):
                    self._upload_thumbnail(video_id, metadata.thumbnail_file_path)

                url = f"https://www.youtube.com/watch?v={video_id}"
                logger.info(f"Successfully uploaded video: {url}")

                return UploadResult(
                    success=True,
                    video_id=video_id,
                    url=url
                )
            else:
                error = "Upload completed but no video_id received"
                logger.error(error)
                self.last_error = error
                return UploadResult(success=False, error=error)

        except Exception as e:
            error = f"Upload failed: {str(e)}"
            logger.error(error)
            self.last_error = error
            return UploadResult(success=False, error=error)

    def _initialize_resumable_upload(
        self,
        metadata: VideoMetadata,
        body: Dict[str, Any]
    ) -> Optional[str]:
        """Initialize a resumable upload session.

        Returns:
            Upload session URI for resumable upload
        """
        try:
            url = f"{self.API_BASE_URL}/videos"
            params = self._get_params()
            params["part"] = "snippet,status,processingDetails"
            params["uploadType"] = "resumable"
            params["onUploadProgress"] = "true"

            headers = self._get_headers()
            headers["X-Goog-Upload-Protocol"] = "resumable"
            headers["X-Goog-Upload-Command"] = "start"
            headers["X-Goog-Upload-Header-Content-Type"] = "application/json"
            headers["Content-Type"] = "application/json"

            response = self.session.post(
                url,
                json=body,
                params=params,
                headers=headers,
                timeout=30
            )

            if response.status_code in [200, 201]:
                upload_uri = response.headers.get("location")
                logger.info(f"Initialized resumable upload: {upload_uri[:50]}...")
                return upload_uri
            else:
                logger.error(f"Failed to initialize upload: {response.status_code} - {response.text}")
                return None

        except Exception as e:
            logger.error(f"Error initializing resumable upload: {e}")
            return None

    def _upload_video_content(
        self,
        upload_uri: str,
        metadata: VideoMetadata
    ) -> Optional[str]:
        """Upload video content to the resumable upload session.

        Returns:
            video_id if upload successful
        """
        try:
            file_size = os.path.getsize(metadata.video_file_path)

            with open(metadata.video_file_path, 'rb') as f:
                headers = {
                    "X-Goog-Upload-Command": "upload, finalize",
                    "X-Goog-Upload-Offset": "0",
                    "X-Goog-Upload-Size": str(file_size),
                }

                response = self.session.put(
                    upload_uri,
                    data=f,
                    headers=headers,
                    timeout=self.UPLOAD_TIMEOUT
                )

            if response.status_code in [200, 201]:
                response_body = response.json()
                video_id = response_body.get("id")
                logger.info(f"Video upload successful: {video_id}")
                return video_id
            else:
                logger.error(f"Video upload failed: {response.status_code} - {response.text}")
                return None

        except Timeout:
            logger.error(f"Upload timeout after {self.UPLOAD_TIMEOUT} seconds")
            return None
        except Exception as e:
            logger.error(f"Error uploading video content: {e}")
            return None

    def _upload_thumbnail(self, video_id: str, thumbnail_path: str) -> bool:
        """Upload custom thumbnail for a video.

        Args:
            video_id: YouTube video ID
            thumbnail_path: Path to thumbnail image file

        Returns:
            True if successful
        """
        try:
            if not os.path.exists(thumbnail_path):
                logger.warning(f"Thumbnail file not found: {thumbnail_path}")
                return False

            url = f"{self.API_BASE_URL}/thumbnails/set"
            params = self._get_params()
            params["videoId"] = video_id

            with open(thumbnail_path, 'rb') as f:
                files = {
                    "data": (os.path.basename(thumbnail_path), f)
                }
                headers = self._get_headers()

                response = self.session.post(
                    url,
                    files=files,
                    params=params,
                    headers=headers,
                    timeout=30
                )

            if response.status_code in [200, 201]:
                logger.info(f"Thumbnail uploaded for video: {video_id}")
                return True
            else:
                logger.warning(f"Thumbnail upload failed: {response.status_code}")
                return False

        except Exception as e:
            logger.error(f"Error uploading thumbnail: {e}")
            return False

    def get_video_status(self, video_id: str) -> Optional[Dict[str, Any]]:
        """Get video status and processing details.

        Args:
            video_id: YouTube video ID

        Returns:
            Video status information or None if error
        """
        try:
            url = f"{self.API_BASE_URL}/videos"
            params = self._get_params()
            params["part"] = "status,processingDetails"
            params["id"] = video_id

            headers = self._get_headers()

            response = self.session.get(
                url,
                params=params,
                headers=headers,
                timeout=10
            )

            if response.status_code == 200:
                items = response.json().get("items", [])
                if items:
                    return items[0]
            else:
                logger.error(f"Failed to get video status: {response.status_code}")

            return None

        except Exception as e:
            logger.error(f"Error getting video status: {e}")
            return None

    def update_video(self, video_id: str, updates: Dict[str, Any]) -> bool:
        """Update video metadata (title, description, tags, etc).

        Args:
            video_id: YouTube video ID
            updates: Dictionary of fields to update

        Returns:
            True if successful
        """
        if not self.access_token:
            logger.error("Access token required for video updates")
            return False

        try:
            url = f"{self.API_BASE_URL}/videos"
            params = self._get_params()
            params["part"] = "snippet,status"

            body = {
                "id": video_id,
                "snippet": updates.get("snippet", {}),
                "status": updates.get("status", {})
            }

            headers = self._get_headers()
            headers["Content-Type"] = "application/json"

            response = self.session.put(
                url,
                json=body,
                params=params,
                headers=headers,
                timeout=10
            )

            if response.status_code in [200, 201]:
                logger.info(f"Updated video: {video_id}")
                return True
            else:
                logger.error(f"Failed to update video: {response.status_code}")
                return False

        except Exception as e:
            logger.error(f"Error updating video: {e}")
            return False

    def list_videos(
        self,
        channel_id: str,
        max_results: int = 25,
        page_token: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """List videos for a channel.

        Args:
            channel_id: YouTube channel ID
            max_results: Maximum results to return (default 25, max 50)
            page_token: Token for pagination

        Returns:
            List response with videos
        """
        try:
            url = f"{self.API_BASE_URL}/search"
            params = self._get_params()
            params["part"] = "snippet"
            params["channelId"] = channel_id
            params["maxResults"] = min(max_results, 50)
            params["type"] = "video"
            params["order"] = "date"

            if page_token:
                params["pageToken"] = page_token

            headers = self._get_headers()

            response = self.session.get(
                url,
                params=params,
                headers=headers,
                timeout=10
            )

            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Failed to list videos: {response.status_code}")
                return None

        except Exception as e:
            logger.error(f"Error listing videos: {e}")
            return None

    def get_channel_info(self, channel_id: str) -> Optional[Dict[str, Any]]:
        """Get channel information.

        Args:
            channel_id: YouTube channel ID

        Returns:
            Channel information or None if error
        """
        try:
            url = f"{self.API_BASE_URL}/channels"
            params = self._get_params()
            params["part"] = "snippet,statistics,contentDetails,topicDetails"
            params["id"] = channel_id

            headers = self._get_headers()

            response = self.session.get(
                url,
                params=params,
                headers=headers,
                timeout=10
            )

            if response.status_code == 200:
                items = response.json().get("items", [])
                if items:
                    return items[0]
            else:
                logger.error(f"Failed to get channel info: {response.status_code}")

            return None

        except Exception as e:
            logger.error(f"Error getting channel info: {e}")
            return None

    def close(self):
        """Close the session."""
        if self.session:
            self.session.close()

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
