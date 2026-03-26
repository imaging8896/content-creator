# YouTube API Setup Guide

Complete guide to setting up YouTube OAuth2 authentication for video uploads.

## Prerequisites

- Google Cloud Project with YouTube Data API v3 enabled
- OAuth2 credentials (Client ID and Client Secret)
- YouTube channel that you own or have manager access to

## Step 1: Create a Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Click "Select a Project" → "New Project"
3. Enter project name: "Content Creator Agent"
4. Click "Create"
5. Wait for project creation to complete

## Step 2: Enable YouTube Data API v3

1. In the Cloud Console, go to "APIs & Services" → "Library"
2. Search for "YouTube Data API v3"
3. Click on it
4. Click "Enable"
5. Wait for the API to be enabled

## Step 3: Create OAuth2 Credentials

1. Go to "APIs & Services" → "Credentials"
2. Click "Create Credentials" → "OAuth client ID"
3. If prompted, configure the OAuth consent screen first:
   - User Type: Select "External"
   - Click "Create"
   - Fill in the application name: "Content Creator Agent"
   - Add your email as support email
   - Click "Save and Continue"
4. For OAuth consent screen scopes:
   - Click "Add or Remove Scopes"
   - Search for and add:
     - `https://www.googleapis.com/auth/youtube.upload`
     - `https://www.googleapis.com/auth/youtube`
     - `https://www.googleapis.com/auth/youtube.readonly`
   - Click "Update" and "Save and Continue"
5. Add test users (your email address)
6. Back to Credentials, click "Create Credentials" → "OAuth client ID"
7. Application type: "Web application"
8. Name: "Content Creator Agent"
9. Authorized JavaScript origins:
   - `http://localhost`
   - `http://localhost:8000` (or your server port)
   - `http://127.0.0.1`
10. Authorized redirect URIs:
    - `http://localhost:8000/callback`
    - `http://localhost:8080/callback`
    - `urn:ietf:wg:oauth:2.0:oob`
11. Click "Create"
12. Download the JSON file (client_secret_*.json)

## Step 4: Get Authorization Code

Use the OAuth2 flow to get an authorization code:

```bash
# Replace CLIENT_ID with your actual client ID
CLIENT_ID="your-client-id.apps.googleusercontent.com"
REDIRECT_URI="urn:ietf:wg:oauth:2.0:oob"  # Out-of-band flow

# Open this URL in your browser
echo "https://accounts.google.com/o/oauth2/v2/auth?scope=https%3A%2F%2Fwww.googleapis.com%2Fauth%2Fyoutube.upload%20https%3A%2F%2Fwww.googleapis.com%2Fauth%2Fyoutube%20https%3A%2F%2Fwww.googleapis.com%2Fauth%2Fyoutube.readonly&access_type=offline&include_granted_scopes=true&response_type=code&client_id=${CLIENT_ID}&redirect_uri=${REDIRECT_URI}"
```

## Step 5: Exchange Authorization Code for Tokens

Once you get the authorization code from the previous step:

```bash
CLIENT_ID="your-client-id.apps.googleusercontent.com"
CLIENT_SECRET="your-client-secret"
AUTHORIZATION_CODE="code_from_previous_step"

curl -X POST "https://oauth2.googleapis.com/token" \
  -d "client_id=${CLIENT_ID}" \
  -d "client_secret=${CLIENT_SECRET}" \
  -d "code=${AUTHORIZATION_CODE}" \
  -d "grant_type=authorization_code" \
  -d "redirect_uri=urn:ietf:wg:oauth:2.0:oob"
```

This will return:
```json
{
  "access_token": "ya29...",
  "refresh_token": "1//0...",
  "expires_in": 3599,
  "scope": "...",
  "token_type": "Bearer"
}
```

## Step 6: Get Your Channel ID

Your channel ID is typically in the format `UCxxxxxxxxxxxxxxxx` (24 characters).

Find it in the URL when viewing your channel:
1. Go to [YouTube Studio](https://studio.youtube.com/)
2. Click "Settings" (bottom left)
3. Look for the "Channel ID" field
4. Or check the URL: `youtube.com/@your-handle` or `youtube.com/channel/{CHANNEL_ID}`

## Step 7: Set Environment Variables

```bash
# Save these securely - DO NOT commit to version control
export YOUTUBE_ACCESS_TOKEN="ya29..."
export YOUTUBE_REFRESH_TOKEN="1//0..."
export YOUTUBE_CLIENT_ID="your-client-id.apps.googleusercontent.com"
export YOUTUBE_CLIENT_SECRET="your-client-secret"
export YOUTUBE_CHANNEL_ID="UCxxxxxxxxxxxxxxxx"  # Your channel ID
```

Or create a `.env` file (add to `.gitignore`):
```
YOUTUBE_ACCESS_TOKEN=ya29...
YOUTUBE_REFRESH_TOKEN=1//0...
YOUTUBE_CLIENT_ID=your-client-id.apps.googleusercontent.com
YOUTUBE_CLIENT_SECRET=your-client-secret
YOUTUBE_CHANNEL_ID=UCxxxxxxxxxxxxxxxx
```

Load it with:
```bash
source .env
```

## Step 8: Verify Setup

Test the authentication:

```bash
# Start the server
python main.py

# In another terminal, check YouTube status
curl http://localhost:8002/youtube/status

# You should see:
# {
#   "authenticated": true,
#   "has_refresh_token": true,
#   "last_error": null,
#   "endpoints": [...]
# }
```

## Testing Video Upload

Create a test video and upload:

```bash
# Create a simple test video (requires ffmpeg)
ffmpeg -f lavfi -i color=c=blue:s=1280x720:d=5 \
       -f lavfi -i sine=frequency=1000:duration=5 \
       -pix_fmt yuv420p -c:v libx264 -preset ultrafast test_video.mp4

# Upload to YouTube
curl -X POST "http://localhost:8002/youtube/upload" \
  -F "title=Test Video" \
  -F "description=Testing YouTube upload" \
  -F "channel_id=UCxxxxxxxxxxxxxxxx" \
  -F "video_file=@test_video.mp4" \
  -F "tags=test,api"
```

## Token Refresh

Access tokens expire after ~1 hour. The system automatically refreshes using the refresh token.

To manually refresh:
```bash
curl -X POST http://localhost:8002/youtube/refresh-token
```

## Troubleshooting

### "Invalid client" error
- Check CLIENT_ID and CLIENT_SECRET are correct
- Ensure they're set as environment variables

### "Unauthorized" error
- Access token may have expired
- Try refreshing: `POST /youtube/refresh-token`
- May need to re-authorize with new token

### "Channel not found" error
- Verify channel ID format (UC + 24 characters)
- Ensure you have access to the channel
- Check if the account was banned/suspended

### "Quota exceeded" error
- YouTube API has daily quota limits
- Standard quota: 10,000 units/day
- Video upload: ~1,500 units
- Wait 24 hours for quota to reset
- Or request quota increase in Cloud Console

### "Invalid video file" error
- Ensure video is in a supported format (MP4, WebM, AVI, MOV, etc.)
- Maximum file size: 256GB
- Check file is valid: `ffprobe video_file.mp4`

## Security Best Practices

1. **Never commit tokens**: Add `.env` to `.gitignore`
2. **Use environment variables**: Set via CI/CD secrets, not in code
3. **Rotate tokens regularly**: Regenerate credentials periodically
4. **Scope minimization**: Only request necessary scopes
5. **Secure storage**: Use secure credential management systems in production

## Advanced: Service Account (Alternative)

For server-to-server uploads, use a service account instead:

1. In Google Cloud Console, create a Service Account
2. Create a key and download the JSON file
3. Set `GOOGLE_APPLICATION_CREDENTIALS` to the JSON file path
4. The library will automatically use service account credentials

```bash
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account-key.json"
```

## Resources

- [YouTube Data API Documentation](https://developers.google.com/youtube/v3)
- [OAuth 2.0 Guide](https://developers.google.com/identity/protocols/oauth2)
- [Quotas & Limits](https://developers.google.com/youtube/v3/determine_quota_cost)
- [Supported Video Formats](https://support.google.com/youtube/answer/1722171)

## Support

For issues or questions about YouTube API setup:
1. Check [YouTube Data API Troubleshooting](https://developers.google.com/youtube/v3/docs/errors)
2. Review server logs for detailed error messages
3. Test with `curl` or Postman before integrating with your application
