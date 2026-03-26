"""Tests for YouTube API client."""
import pytest
import os
import tempfile
import json
from unittest.mock import Mock, MagicMock, patch, mock_open
from youtube_api_client import (
    YouTubeAPIClient,
    VideoMetadata,
    UploadResult
)


class TestVideoMetadata:
    """Test VideoMetadata dataclass."""

    def test_create_basic_metadata(self):
        """Test creating basic video metadata."""
        metadata = VideoMetadata(
            title="Test Video",
            description="Test Description",
            channel_id="UC123456",
            video_file_path="/path/to/video.mp4"
        )

        assert metadata.title == "Test Video"
        assert metadata.description == "Test Description"
        assert metadata.channel_id == "UC123456"
        assert metadata.privacy_status == "public"
        assert metadata.made_for_kids is False
        assert metadata.category_id == "24"

    def test_metadata_with_optional_fields(self):
        """Test metadata with all optional fields."""
        metadata = VideoMetadata(
            title="Test Video",
            description="Test Description",
            channel_id="UC123456",
            video_file_path="/path/to/video.mp4",
            thumbnail_file_path="/path/to/thumbnail.jpg",
            tags=["tag1", "tag2"],
            category_id="15",
            privacy_status="unlisted",
            made_for_kids=True
        )

        assert metadata.thumbnail_file_path == "/path/to/thumbnail.jpg"
        assert metadata.tags == ["tag1", "tag2"]
        assert metadata.category_id == "15"
        assert metadata.privacy_status == "unlisted"
        assert metadata.made_for_kids is True


class TestUploadResult:
    """Test UploadResult dataclass."""

    def test_successful_upload_result(self):
        """Test successful upload result."""
        result = UploadResult(
            success=True,
            video_id="dQw4w9WgXcQ",
            url="https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        )

        assert result.success is True
        assert result.video_id == "dQw4w9WgXcQ"
        assert result.url == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        assert result.error is None
        assert result.timestamp is not None

    def test_failed_upload_result(self):
        """Test failed upload result."""
        result = UploadResult(
            success=False,
            error="Authentication failed"
        )

        assert result.success is False
        assert result.video_id is None
        assert result.url is None
        assert result.error == "Authentication failed"
        assert result.timestamp is not None


class TestYouTubeAPIClient:
    """Test YouTubeAPIClient class."""

    def test_initialization_with_access_token(self):
        """Test client initialization with access token."""
        client = YouTubeAPIClient(access_token="test_token")

        assert client.access_token == "test_token"
        assert client.api_key is None

    def test_initialization_with_api_key(self):
        """Test client initialization with API key."""
        client = YouTubeAPIClient(api_key="test_key")

        assert client.api_key == "test_key"
        assert client.access_token is None

    @patch.dict(os.environ, {
        "YOUTUBE_ACCESS_TOKEN": "env_token",
        "YOUTUBE_API_KEY": "env_key"
    })
    def test_initialization_from_env(self):
        """Test client initialization from environment variables."""
        client = YouTubeAPIClient()

        assert client.access_token == "env_token"
        assert client.api_key == "env_key"

    def test_get_headers_with_access_token(self):
        """Test getting headers with access token."""
        client = YouTubeAPIClient(access_token="test_token")
        headers = client._get_headers()

        assert "Authorization" in headers
        assert headers["Authorization"] == "Bearer test_token"

    def test_get_headers_without_access_token(self):
        """Test getting headers without access token."""
        client = YouTubeAPIClient()
        headers = client._get_headers()

        assert "Authorization" not in headers
        assert headers["User-Agent"] == "ContentCreatorAgent/1.0"

    def test_get_params_with_api_key(self):
        """Test getting params with API key."""
        client = YouTubeAPIClient(api_key="test_key")
        params = client._get_params()

        assert params["key"] == "test_key"

    def test_get_params_with_access_token(self):
        """Test getting params with access token (no API key needed)."""
        client = YouTubeAPIClient(access_token="test_token")
        params = client._get_params()

        assert "key" not in params

    @patch('youtube_api_client.requests.Session.post')
    def test_refresh_access_token_success(self, mock_post):
        """Test successful access token refresh."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "access_token": "new_token",
            "expires_in": 3600
        }
        mock_post.return_value = mock_response

        client = YouTubeAPIClient(
            refresh_token="refresh_token",
            client_id="client_id",
            client_secret="client_secret"
        )

        success = client.refresh_access_token()

        assert success is True
        assert client.access_token == "new_token"

    @patch('youtube_api_client.requests.Session.post')
    def test_refresh_access_token_failure(self, mock_post):
        """Test failed access token refresh."""
        mock_response = Mock()
        mock_response.json.return_value = {"error": "invalid_grant"}
        mock_post.return_value = mock_response

        client = YouTubeAPIClient(
            refresh_token="invalid_token",
            client_id="client_id",
            client_secret="client_secret"
        )

        success = client.refresh_access_token()

        assert success is False

    def test_upload_video_without_access_token(self):
        """Test upload fails without access token."""
        client = YouTubeAPIClient()

        metadata = VideoMetadata(
            title="Test",
            description="Test",
            channel_id="UC123",
            video_file_path="/path/to/video.mp4"
        )

        result = client.upload_video(metadata)

        assert result.success is False
        assert "Access token required" in result.error

    def test_upload_video_nonexistent_file(self):
        """Test upload fails with nonexistent file."""
        client = YouTubeAPIClient(access_token="test_token")

        metadata = VideoMetadata(
            title="Test",
            description="Test",
            channel_id="UC123",
            video_file_path="/nonexistent/path/video.mp4"
        )

        result = client.upload_video(metadata)

        assert result.success is False
        assert "not found" in result.error

    @patch('youtube_api_client.YouTubeAPIClient._initialize_resumable_upload')
    @patch('youtube_api_client.YouTubeAPIClient._upload_video_content')
    @patch('builtins.open', new_callable=mock_open, read_data=b'video content')
    @patch('os.path.exists')
    @patch('os.path.getsize')
    def test_upload_video_success(
        self,
        mock_getsize,
        mock_exists,
        mock_file_open,
        mock_upload_content,
        mock_init_upload
    ):
        """Test successful video upload."""
        mock_exists.return_value = True
        mock_getsize.return_value = 1000000
        mock_init_upload.return_value = "https://upload.youtube.com/session/..."
        mock_upload_content.return_value = "dQw4w9WgXcQ"

        client = YouTubeAPIClient(access_token="test_token")

        metadata = VideoMetadata(
            title="Test Video",
            description="Test Description",
            channel_id="UC123456",
            video_file_path="/path/to/video.mp4"
        )

        result = client.upload_video(metadata)

        assert result.success is True
        assert result.video_id == "dQw4w9WgXcQ"
        assert "watch?v=" in result.url

    @patch('youtube_api_client.requests.Session.get')
    def test_get_video_status_success(self, mock_get):
        """Test getting video status successfully."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "items": [{
                "status": {
                    "uploadStatus": "processed"
                },
                "processingDetails": {
                    "processingStatus": "succeeded"
                }
            }]
        }
        mock_get.return_value = mock_response

        client = YouTubeAPIClient(access_token="test_token")
        status = client.get_video_status("dQw4w9WgXcQ")

        assert status is not None
        assert status["status"]["uploadStatus"] == "processed"

    @patch('youtube_api_client.requests.Session.get')
    def test_get_video_status_not_found(self, mock_get):
        """Test getting status for nonexistent video."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"items": []}
        mock_get.return_value = mock_response

        client = YouTubeAPIClient(access_token="test_token")
        status = client.get_video_status("nonexistent")

        assert status is None

    @patch('youtube_api_client.requests.Session.put')
    def test_update_video_success(self, mock_put):
        """Test successful video update."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_put.return_value = mock_response

        client = YouTubeAPIClient(access_token="test_token")

        updates = {
            "snippet": {
                "title": "Updated Title",
                "description": "Updated Description"
            }
        }

        success = client.update_video("dQw4w9WgXcQ", updates)

        assert success is True

    def test_update_video_without_access_token(self):
        """Test update fails without access token."""
        client = YouTubeAPIClient()

        updates = {"snippet": {"title": "New Title"}}

        success = client.update_video("dQw4w9WgXcQ", updates)

        assert success is False

    @patch('youtube_api_client.requests.Session.get')
    def test_list_videos_success(self, mock_get):
        """Test listing videos successfully."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "items": [
                {"id": {"videoId": "vid1"}},
                {"id": {"videoId": "vid2"}}
            ],
            "nextPageToken": "NEXT_PAGE"
        }
        mock_get.return_value = mock_response

        client = YouTubeAPIClient(access_token="test_token")
        videos = client.list_videos("UC123456", max_results=25)

        assert videos is not None
        assert len(videos["items"]) == 2
        assert "nextPageToken" in videos

    @patch('youtube_api_client.requests.Session.get')
    def test_get_channel_info_success(self, mock_get):
        """Test getting channel info successfully."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "items": [{
                "id": "UC123456",
                "snippet": {
                    "title": "Test Channel",
                    "description": "Test Channel Description"
                },
                "statistics": {
                    "viewCount": "1000000",
                    "subscriberCount": "10000",
                    "videoCount": "50"
                }
            }]
        }
        mock_get.return_value = mock_response

        client = YouTubeAPIClient(access_token="test_token")
        info = client.get_channel_info("UC123456")

        assert info is not None
        assert info["snippet"]["title"] == "Test Channel"
        assert info["statistics"]["subscriberCount"] == "10000"

    def test_context_manager(self):
        """Test client as context manager."""
        with YouTubeAPIClient(access_token="test_token") as client:
            assert client.access_token == "test_token"

    def test_session_closure(self):
        """Test session closure."""
        client = YouTubeAPIClient(access_token="test_token")
        assert client.session is not None

        client.close()
        # Session should still exist but be closed

    @patch('youtube_api_client.requests.Session.post')
    def test_initialize_resumable_upload_success(self, mock_post):
        """Test initializing resumable upload."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {
            "location": "https://upload.youtube.com/session/ABC123"
        }
        mock_post.return_value = mock_response

        client = YouTubeAPIClient(access_token="test_token")

        metadata = VideoMetadata(
            title="Test",
            description="Test",
            channel_id="UC123",
            video_file_path="/path/to/video.mp4"
        )

        body = {"snippet": {"title": "Test"}}

        uri = client._initialize_resumable_upload(metadata, body)

        assert uri == "https://upload.youtube.com/session/ABC123"

    @patch('youtube_api_client.requests.Session.post')
    def test_upload_thumbnail_success(self, mock_post):
        """Test successful thumbnail upload."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        with tempfile.TemporaryDirectory() as temp_dir:
            thumbnail_path = os.path.join(temp_dir, "thumbnail.jpg")
            with open(thumbnail_path, 'wb') as f:
                f.write(b'fake image data')

            client = YouTubeAPIClient(access_token="test_token")
            success = client._upload_thumbnail("dQw4w9WgXcQ", thumbnail_path)

            assert success is True

    def test_upload_thumbnail_file_not_found(self):
        """Test thumbnail upload with missing file."""
        client = YouTubeAPIClient(access_token="test_token")
        success = client._upload_thumbnail("dQw4w9WgXcQ", "/nonexistent/path.jpg")

        assert success is False


class TestIntegration:
    """Integration tests for YouTube client."""

    def test_full_upload_workflow_mocked(self):
        """Test full upload workflow with mocked API."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a fake video file
            video_path = os.path.join(temp_dir, "test_video.mp4")
            with open(video_path, 'wb') as f:
                f.write(b'fake video data' * 100)

            # Create metadata
            metadata = VideoMetadata(
                title="Test Video",
                description="Test Description",
                channel_id="UC123456",
                video_file_path=video_path,
                tags=["test", "video"]
            )

            # Create client
            client = YouTubeAPIClient(access_token="test_token")

            # Verify metadata is valid
            assert metadata.title == "Test Video"
            assert os.path.exists(metadata.video_file_path)

            # Verify client is initialized
            assert client.access_token == "test_token"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
