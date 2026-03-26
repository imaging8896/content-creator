# Development Guide

Guide for developing and testing the Distribution & SEO Agent.

## Project Structure

```
distribution-seo-agent/
├── youtube_api_client.py           # YouTube API client implementation (400 lines)
├── main.py                         # FastAPI application (350 lines)
├── test_youtube_api_client.py      # Comprehensive tests (600+ lines)
├── requirements.txt                # Python dependencies
├── README.md                       # User guide
├── DEVELOPMENT.md                  # This file
└── YOUTUBE_API_SETUP.md           # OAuth setup instructions
```

## Local Development Setup

### 1. Install Dependencies

```bash
cd distribution-seo-agent
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
pip install pytest pytest-cov  # For testing
```

### 2. Set Up YouTube Credentials

Follow the [YouTube API Setup Guide](./YOUTUBE_API_SETUP.md) to:
1. Create a Google Cloud Project
2. Enable YouTube Data API v3
3. Create OAuth2 credentials
4. Get authorization tokens

Set environment variables:
```bash
export YOUTUBE_ACCESS_TOKEN="your_token_here"
export YOUTUBE_REFRESH_TOKEN="your_refresh_token_here"
export YOUTUBE_CLIENT_ID="your_client_id_here"
export YOUTUBE_CLIENT_SECRET="your_client_secret_here"
```

### 3. Start Development Server

```bash
python main.py
# Server runs on http://localhost:8002
```

## Running Tests

### All Tests
```bash
pytest test_youtube_api_client.py -v
```

### Test Coverage
```bash
pytest test_youtube_api_client.py --cov=youtube_api_client --cov-report=html
# View report in: htmlcov/index.html
```

### Specific Test Classes
```bash
pytest test_youtube_api_client.py::TestVideoMetadata -v
pytest test_youtube_api_client.py::TestYouTubeAPIClient -v
pytest test_youtube_api_client.py::TestIntegration -v
```

## Code Structure

### YouTubeAPIClient

Main class for interacting with YouTube Data API v3.

**Key Methods:**
- `upload_video(metadata)` - Upload video to YouTube
- `get_video_status(video_id)` - Check video processing status
- `update_video(video_id, updates)` - Update video metadata
- `list_videos(channel_id)` - List channel videos
- `get_channel_info(channel_id)` - Get channel statistics
- `refresh_access_token()` - Refresh OAuth token

**Properties:**
- `access_token` - OAuth2 access token
- `refresh_token` - OAuth2 refresh token
- `last_error` - Last error message

### VideoMetadata

Dataclass for video metadata:
```python
metadata = VideoMetadata(
    title="My Video",
    description="Video description",
    channel_id="UCxxxxxxxxxxxxxxxx",
    video_file_path="/path/to/video.mp4",
    thumbnail_file_path="/path/to/thumbnail.jpg",
    tags=["tag1", "tag2"],
    category_id="24",  # Entertainment
    privacy_status="public"  # public, unlisted, private
)
```

### UploadResult

Result dataclass:
```python
result = UploadResult(
    success=True,
    video_id="dQw4w9WgXcQ",
    url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    timestamp="2026-03-26T02:16:23.027Z"
)
```

## API Endpoints

### Health Check
```bash
curl http://localhost:8002/health
```

### YouTube Status
```bash
curl http://localhost:8002/youtube/status
```

### Upload Video
```bash
curl -X POST http://localhost:8002/youtube/upload \
  -F "title=My Video" \
  -F "description=My description" \
  -F "channel_id=UCxxxxxxxxxxxxxxxx" \
  -F "video_file=@video.mp4" \
  -F "tags=tag1,tag2"
```

### Get Video Status
```bash
curl http://localhost:8002/youtube/video/dQw4w9WgXcQ/status
```

### Update Video
```bash
curl -X PATCH http://localhost:8002/youtube/video/dQw4w9WgXcQ \
  -F "title=Updated Title" \
  -F "description=Updated description"
```

### Get Channel Info
```bash
curl http://localhost:8002/youtube/channel/UCxxxxxxxxxxxxxxxx/info
```

### List Videos
```bash
curl http://localhost:8002/youtube/channels/UCxxxxxxxxxxxxxxxx/videos
```

### Refresh Token
```bash
curl -X POST http://localhost:8002/youtube/refresh-token
```

## Testing Strategy

### Unit Tests
Test individual components in isolation:
- `VideoMetadata` creation and validation
- `UploadResult` creation
- Header/parameter generation
- Error handling

### Integration Tests
Test API interactions:
- Upload workflow with mocked API
- Error scenarios
- Context manager usage

### Manual Testing
Test with real YouTube API:
1. Set valid credentials
2. Upload a test video
3. Check status
4. Update metadata
5. Retrieve channel info

## Code Quality

### Style Guide
- PEP 8 compliant
- Type hints for all functions
- Docstrings for classes and public methods
- Comments for complex logic

### Linting
```bash
pip install pylint flake8
pylint youtube_api_client.py main.py
flake8 youtube_api_client.py main.py
```

### Type Checking
```bash
pip install mypy
mypy youtube_api_client.py main.py
```

## Common Development Tasks

### Adding a New Endpoint

1. Create method in `YouTubeAPIClient`
2. Add test in `test_youtube_api_client.py`
3. Create FastAPI endpoint in `main.py`
4. Document in `README.md`

Example:
```python
# In youtube_api_client.py
def new_method(self, param):
    """Description."""
    # Implementation

# In main.py
@app.get("/youtube/endpoint")
async def endpoint_name(param: str):
    """Endpoint description."""
    result = youtube_client.new_method(param)
    return result
```

### Handling API Errors

YouTube API errors are handled with:
- Logging to `logger`
- Return error in result object
- HTTPException in FastAPI endpoints

Example:
```python
try:
    # API call
    response = self.session.get(url, ...)
    if response.status_code != 200:
        logger.error(f"Error: {response.status_code}")
        return None
except Exception as e:
    logger.error(f"Exception: {e}")
    self.last_error = str(e)
    return None
```

### Testing with Sample Data

Create test files:
```bash
# Create test video
ffmpeg -f lavfi -i color=c=blue:s=1280x720:d=5 \
       -f lavfi -i sine=frequency=1000:duration=5 \
       -pix_fmt yuv420p test_video.mp4

# Create test thumbnail
convert -size 1280x720 xc:blue test_thumbnail.jpg
```

## Debugging

### Enable Debug Logging
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Print Request/Response
```python
import json
logger.debug(f"Request: {json.dumps(request_body, indent=2)}")
logger.debug(f"Response: {response.json()}")
```

### Interactive Testing
```bash
python -i -c "from youtube_api_client import YouTubeAPIClient; client = YouTubeAPIClient()"
# Now you can call methods interactively
>>> client.get_channel_info("UCxxxxxxxxxxxxxxxx")
```

## Performance Optimization

### API Call Caching
Consider adding caching for:
- Channel info (cache for 1 hour)
- Video status (cache for 5 minutes)
- Quota information

### Batch Operations
For multiple videos, batch requests where possible:
- List videos paginates automatically
- Update multiple videos in loop (respects rate limits)

### Connection Pooling
The client uses `requests.Session` for connection reuse:
```python
self.session = requests.Session()
# Reuses TCP connections across multiple requests
```

## Deployment

### Docker
Create a `Dockerfile`:
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
ENV YOUTUBE_ACCESS_TOKEN=$YOUTUBE_ACCESS_TOKEN
CMD ["python", "main.py"]
```

Build and run:
```bash
docker build -t distribution-agent .
docker run -e YOUTUBE_ACCESS_TOKEN=$YOUTUBE_ACCESS_TOKEN \
           -p 8002:8002 \
           distribution-agent
```

### Environment Variables for Production

In production, set:
```bash
YOUTUBE_ACCESS_TOKEN      # Your OAuth token
YOUTUBE_REFRESH_TOKEN     # Refresh token
YOUTUBE_CLIENT_ID         # OAuth client ID
YOUTUBE_CLIENT_SECRET     # OAuth secret (use secrets manager)
PORT                      # Server port (default 8002)
```

## Contributing

When adding new features:
1. Create feature branch
2. Write tests first (TDD)
3. Implement feature
4. Update documentation
5. Run full test suite
6. Create pull request

## Resources

- [YouTube Data API Docs](https://developers.google.com/youtube/v3)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Requests Library](https://requests.readthedocs.io/)
- [Python OAuth2](https://python-oauthlib.readthedocs.io/)

## Troubleshooting

### Import Errors
```bash
pip install -r requirements.txt
# Verify: python -c "import fastapi; import requests"
```

### Authentication Errors
- Check environment variables are set
- Verify access token hasn't expired
- Try refreshing token with POST /youtube/refresh-token

### Connection Errors
- Check internet connection
- Verify YouTube API is enabled in Cloud Console
- Check firewall/proxy settings

### Upload Fails
- Verify video file format is supported
- Check file size is under 256GB
- Ensure channel ID is correct
- Review detailed error in log output
