# Distribution & SEO Agent

Phase 3 of the Content Creator Agent system. Distributes generated content to multiple platforms (YouTube, blogs, social media) and optimizes for SEO.

## Current Implementation

### YouTube Shorts Distribution (AIC-25)

Complete YouTube Data API v3 integration for uploading videos to YouTube Shorts with:
- OAuth2 authentication
- Resumable upload support (handles large files and network interruptions)
- Custom thumbnail upload
- Video metadata management (title, description, tags, privacy)
- Video status tracking and monitoring
- Channel information retrieval
- Batch video listing

## Architecture

```
distribution-seo-agent/
├── youtube_api_client.py      # YouTube API client implementation
├── main.py                     # FastAPI application
├── test_youtube_api_client.py  # Comprehensive test suite
├── requirements.txt            # Python dependencies
├── README.md                   # This file
├── DEVELOPMENT.md              # Development setup guide
└── YOUTUBE_API_SETUP.md        # YouTube OAuth setup guide
```

## API Endpoints

### Health & Status
- `GET /health` - Health check and authentication status
- `GET /youtube/status` - YouTube API status and available endpoints

### Video Upload & Management
- `POST /youtube/upload` - Upload video to YouTube Shorts
- `GET /youtube/video/{video_id}/status` - Get video processing status
- `PATCH /youtube/video/{video_id}` - Update video metadata
- `POST /youtube/refresh-token` - Refresh OAuth access token

### Channel Operations
- `GET /youtube/channel/{channel_id}/info` - Get channel information
- `GET /youtube/channels/{channel_id}/videos` - List channel videos

## Quick Start

### 1. Install Dependencies
```bash
cd distribution-seo-agent
pip install -r requirements.txt
```

### 2. Set Up YouTube OAuth (see YOUTUBE_API_SETUP.md)
```bash
export YOUTUBE_ACCESS_TOKEN="your_access_token_here"
export YOUTUBE_REFRESH_TOKEN="your_refresh_token_here"
export YOUTUBE_CLIENT_ID="your_client_id_here"
export YOUTUBE_CLIENT_SECRET="your_client_secret_here"
```

### 3. Start the Server
```bash
python main.py
# Server starts on http://localhost:8002
```

### 4. Upload a Video
```bash
curl -X POST "http://localhost:8002/youtube/upload" \
  -F "title=My YouTube Short" \
  -F "description=Great content!" \
  -F "channel_id=UC123456" \
  -F "video_file=@path/to/video.mp4" \
  -F "thumbnail_file=@path/to/thumbnail.jpg" \
  -F "tags=trending,viral"
```

## Features

### YouTube Upload
- **Resumable uploads**: Supports large files and automatic resume on network failure
- **Metadata management**: Title, description, tags, category, privacy settings
- **Thumbnail upload**: Custom thumbnail images for better engagement
- **Kids content flag**: Proper content classification
- **Subscriber notifications**: Optional notification to channel subscribers

### Video Management
- **Status tracking**: Monitor video processing and availability
- **Metadata updates**: Change title, description, tags after upload
- **Channel browsing**: List videos and get channel statistics

### Error Handling
- Graceful failure recovery with detailed error messages
- OAuth token refresh support
- Network timeout handling
- File validation before upload

## Integration with Other Phases

### Phase 1: Trend Discovery
- Consumes trending topics and trend data
- Uses trend metadata for YouTube video descriptions and tags

### Phase 2: Content Creation
- Receives generated video scripts and content
- Uploads generated videos to YouTube
- Handles thumbnail images from content generation

### Phase 3: Distribution (This Module)
- **YouTube Shorts**: Uploads short-form videos
- **Blog Auto-Publish** (upcoming): WordPress and static site integration
- **SEO Optimization** (upcoming): Title, description, and tag optimization
- **Publishing Pipeline** (upcoming): Automated publishing workflow
- **Analytics** (upcoming): Google Analytics and YouTube Analytics integration

## Configuration

### Environment Variables

**Required for authentication:**
- `YOUTUBE_ACCESS_TOKEN` - OAuth2 access token from Google
- `YOUTUBE_REFRESH_TOKEN` - Refresh token for automatic token renewal
- `YOUTUBE_CLIENT_ID` - OAuth2 client ID
- `YOUTUBE_CLIENT_SECRET` - OAuth2 client secret

**Optional:**
- `PORT` - Server port (default: 8002)

### OAuth Scopes Required

The following YouTube API scopes are required:
- `https://www.googleapis.com/auth/youtube.upload` - Upload videos
- `https://www.googleapis.com/auth/youtube` - Manage videos and account
- `https://www.googleapis.com/auth/youtube.readonly` - Read channel information

## Testing

Run the comprehensive test suite:
```bash
pytest test_youtube_api_client.py -v
```

Test coverage includes:
- Metadata validation
- Upload result handling
- API client initialization
- Authentication and authorization
- Header and parameter generation
- Token refresh
- Video upload workflow
- Thumbnail upload
- Status retrieval
- Video updates
- Channel operations
- Error handling and edge cases

## Performance Characteristics

### Upload Speed
- Typical speed: 5-20 Mbps depending on network
- Large file handling: Resumable uploads support interruption recovery
- Timeout: 5 minutes per upload

### API Rate Limits
- Standard YouTube API quota: 10,000 units/day
- Upload operation cost: ~1,500 units
- Query operations cost: 1 unit each

### Concurrent Operations
- Thread-safe request session
- Support for multiple uploads in parallel

## Troubleshooting

### Common Issues

**"Access token required" error**
- Ensure `YOUTUBE_ACCESS_TOKEN` environment variable is set
- Token may be expired - try `POST /youtube/refresh-token`

**"Video file not found" error**
- Verify the file path is correct and file exists
- Use absolute paths when possible

**"Upload timeout" error**
- Network connection issue or file too large
- Resumable uploads will retry automatically
- Check network connectivity

**"Channel not found" error**
- Verify the channel ID is correct (format: UC + 24 characters)
- Ensure you have permission to access the channel

## Future Enhancements

1. **Playlist Management**: Create and manage playlists
2. **Captions/Subtitles**: Auto-generate and upload captions
3. **Analytics Dashboard**: Real-time video performance metrics
4. **Bulk Upload**: Upload multiple videos concurrently
5. **Scheduling**: Schedule videos for specific publish times
6. **Community Posts**: YouTube community tab integration
7. **Livestream Support**: Go live to YouTube
8. **End Screens & Cards**: Automatic end screen generation

## API Documentation

For detailed API documentation, start the server and navigate to:
- Swagger UI: `http://localhost:8002/docs`
- ReDoc: `http://localhost:8002/redoc`

## License

Part of the Content Creator Agent system.

## Author

CTO - Content Creator Agent Team
