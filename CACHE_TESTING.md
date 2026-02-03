# Redis Cache Testing Guide

This guide explains how to set up and test the Redis caching system for the AI Assignment Checker.

## Overview

The caching system provides:
- **OCR Result Caching**: Stores extracted text for 30 days (SHA256 file hash as key)
- **AI Evaluation Caching**: Stores evaluation results for 7 days (question+answer hash as key)
- **Semantic Similarity Detection**: Returns cached results for 95%+ similar answers
- **Graceful Fallback**: System works perfectly without Redis installed

## Expected Performance Improvements

| Metric | Without Cache | With Cache |
|--------|---------------|------------|
| **Same file processing** | 5-10 seconds | <100ms |
| **100 identical files** | ~15 minutes | 2-3 minutes |
| **Monthly API costs** | ~$50-100 | ~$15-30 |
| **Handwriting accuracy** | 40-60% (Tesseract) | 85-95% (Groq Vision) |

---

## Installation Options

### Option 1: Local Redis (Development)

#### Windows
```powershell
# Using Chocolatey
choco install redis-64

# Or using WSL2 (recommended)
wsl --install
# In WSL:
sudo apt update
sudo apt install redis-server
sudo service redis-server start
```

#### macOS
```bash
# Using Homebrew
brew install redis
brew services start redis
```

#### Linux (Ubuntu/Debian)
```bash
sudo apt update
sudo apt install redis-server
sudo systemctl enable redis-server
sudo systemctl start redis-server
```

#### Verify Installation
```bash
redis-cli ping
# Should return: PONG
```

### Option 2: Upstash (Free Cloud - Recommended for Projects)

Upstash offers a generous free tier: **10,000 commands/day** (perfect for student projects!)

1. Go to [Upstash Console](https://console.upstash.com/)
2. Sign up for free (no credit card required)
3. Create a new Redis database
4. Copy the **Redis URL** from the dashboard
5. Add to your `.env` file:
   ```
   REDIS_URL=redis://default:your_password@your-instance.upstash.io:6379
   CACHE_ENABLED=true
   ```

### Option 3: Redis Cloud (Free Tier)

Redis Cloud offers **30MB free** storage.

1. Go to [Redis Cloud](https://redis.com/try-free/)
2. Create a free account
3. Create a new subscription (free tier)
4. Copy the connection details
5. Add to `.env`:
   ```
   REDIS_URL=redis://default:password@redis-xxxxx.redis-cloud.com:port
   CACHE_ENABLED=true
   ```

### Option 4: No Redis (Still Works!)

The system automatically detects if Redis is unavailable and continues without caching:
```
CACHE_ENABLED=false  # or just don't install redis
```

---

## Configuration

Add these to your `.env` file:

```env
# Redis URL (local or cloud)
REDIS_URL=redis://localhost:6379/0

# Enable/disable caching
CACHE_ENABLED=true
```

---

## Testing the Cache

### Test 1: Cache Hit on Duplicate Files

1. Start the application:
   ```bash
   python app.py
   ```

2. Upload a PDF/image file

3. Upload the **same file again**

4. Check the console output:
   - First upload: `⏳ cache MISS for OCR: filename.pdf`
   - Second upload: `✨ cache HIT for OCR: filename.pdf`

### Test 2: AI Evaluation Caching

1. Upload a question and answer file
2. Note the evaluation score
3. Upload the **same answer for the same question**
4. Check console:
   - First: `⏳ cache MISS for AI evaluation`
   - Second: `✨ cache HIT for AI evaluation (exact match)`

### Test 3: Semantic Similarity Caching

1. Upload an answer: "Python is a programming language"
2. Upload a similar answer: "Python is a computer programming language"
3. If similarity ≥95%, you'll see:
   ```
   ✨ cache HIT (similarity: 97%)
   ```

### Test 4: Cache Statistics Endpoint

```bash
# Check cache stats (requires login)
curl http://localhost:5000/cache/stats -H "Cookie: session=your_session"

# Response:
{
  "cache_statistics": {
    "connected": true,
    "hit_rate": 45.2,
    "ocr_keys": 15,
    "eval_keys": 42,
    "memory_used": "1.2M"
  }
}
```

### Test 5: Health Check with Cache Info

```bash
curl http://localhost:5000/health

# Response includes cache status:
{
  "status": "healthy",
  "optimizations": {
    "redis_cache_enabled": true,
    "redis_connected": true
  },
  "cache": {
    "hit_rate": 45.2,
    "total_keys": 57
  }
}
```

---

## Benchmark: 50 Identical Files

With caching properly configured:

| Scenario | Time | API Calls |
|----------|------|-----------|
| First upload (cold cache) | ~8-10 min | 50 OCR + 50 AI |
| Second upload (warm cache) | ~1 min | 0 |
| 50% new, 50% cached | ~5 min | 25 OCR + 25 AI |

---

## Troubleshooting

### "Redis connection failed" message

This is **not an error** - the system works without Redis:
```
⚠️  Redis connection failed: Connection refused
   System will work without caching (slightly slower)
```

### Check Redis is running

```bash
# Linux/macOS
redis-cli ping

# Windows (if using WSL)
wsl redis-cli ping
```

### Clear the cache

```bash
# Using the API (requires secret key confirmation)
curl -X POST http://localhost:5000/cache/clear \
  -H "Content-Type: application/json" \
  -H "Cookie: session=your_session" \
  -d '{"key": "first_8_chars_of_secret_key"}'

# Or directly with redis-cli
redis-cli FLUSHDB
```

### View cache keys

```bash
redis-cli KEYS "cache:*"
```

---

## Cost Comparison (Monthly)

| Usage Level | Without Cache | With Cache | Savings |
|-------------|---------------|------------|---------|
| 100 assignments/month | ~$10 | ~$3 | 70% |
| 500 assignments/month | ~$50 | ~$15 | 70% |
| 1000 assignments/month | ~$100 | ~$30 | 70% |

*Assumes Groq's free tier for evaluation, costs mainly from Vision API for handwriting.*

---

## Production Deployment

### Render.com
- Use Upstash Redis (they have Render integration)
- Add `REDIS_URL` to environment variables

### Railway
- Add Redis service from Railway dashboard
- Railway auto-injects `REDIS_URL`

### Heroku
- Add Heroku Redis addon (has free tier)
- Heroku auto-injects `REDIS_URL`

### Vercel
- Use Upstash Redis (Vercel integration available)
- Add env var in Vercel dashboard

---

## Cache Key Reference

| Key Pattern | TTL | Description |
|-------------|-----|-------------|
| `cache:ocr:{sha256}` | 30 days | OCR extracted text |
| `cache:eval:{q_hash}:{a_hash}` | 7 days | AI evaluation result |
| `cache:similarity:{q_hash}:{a_hash}` | 7 days | Answer text for similarity matching |

---

## Questions?

If caching isn't working as expected:
1. Check `/health` endpoint for cache status
2. Check console logs for cache HIT/MISS messages
3. Verify `REDIS_URL` and `CACHE_ENABLED` in `.env`
4. Test Redis connection with `redis-cli ping`
