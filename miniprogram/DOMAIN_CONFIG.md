# Miniprogram Domain Configuration

## For Local Development
When developing locally, you need to configure "不校验合法域名" in 微信开发者工具:

1. Open 微信开发者工具
2. Click 右上角 "详情"
3. Go to "本地设置" tab
4. Check ✅ "不校验合法域名、web-view（业务域名）、TLS 版本以及 HTTPS 证书"

## For Production Deployment
Add these domains to the miniprogram backend configuration at:
https://mp.weixin.qq.com/

### Required Domain Whitelist

**Request Legal Domains (request合法域名):**
- `localhost:8324` (for development only)
- Your actual backend API domain

**Download File Legal Domains (downloadFile合法域名):**
- `image.tmdb.org` (TMDB movie posters/backdrops)

**Upload File Legal Domains (uploadFile合法域名):**
- Add your backend upload endpoint domain

**Socket Legal Domains:**
- `wss://...` (if using WebSocket for real-time chat)

### Network Configuration
Make sure your server supports:
- HTTPS with valid TLS certificate
- HTTP/2 for better performance
- Proper CORS headers if accessing web APIs

### Environment-Specific Configuration
For different environments (dev/staging/prod), consider:
1. Using different appids for each environment
2. Configuring environment-specific API endpoints
3. Setting up separate domain whitelists per environment
