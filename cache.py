"""
Redis Caching Module for AI Assignment Checker
Provides caching decorators for OCR results and AI evaluations.
Gracefully falls back to no-op if Redis is unavailable.
"""

import os
import hashlib
import json
import functools
from datetime import datetime

# Try to import redis, fallback gracefully
try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    print("⚠️  Redis package not installed. Caching disabled.")
    print("   Install with: pip install redis hiredis")

# Environment configuration
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
CACHE_ENABLED = os.getenv('CACHE_ENABLED', 'true').lower() in ('true', '1', 'yes')

# TTL Configuration (in seconds)
OCR_CACHE_TTL = 30 * 24 * 60 * 60  # 30 days for OCR results
EVAL_CACHE_TTL = 7 * 24 * 60 * 60   # 7 days for AI evaluations

# Cache key prefixes
OCR_KEY_PREFIX = "cache:ocr:"
EVAL_KEY_PREFIX = "cache:eval:"
SIMILARITY_KEY_PREFIX = "cache:similarity:"

# Similarity threshold for returning cached results
SIMILARITY_THRESHOLD = 0.95  # 95% Jaccard similarity

# Redis client (initialized lazily)
_redis_client = None
_connection_checked = False


def get_redis_client():
    """Get or create Redis client with lazy initialization and connection check."""
    global _redis_client, _connection_checked
    
    if not REDIS_AVAILABLE or not CACHE_ENABLED:
        return None
    
    if _redis_client is None and not _connection_checked:
        _connection_checked = True
        try:
            _redis_client = redis.from_url(
                REDIS_URL,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True
            )
            # Test connection
            _redis_client.ping()
            print(f"✅ Redis connected: {REDIS_URL.split('@')[-1] if '@' in REDIS_URL else REDIS_URL}")
        except Exception as e:
            print(f"⚠️  Redis connection failed: {e}")
            print("   System will work without caching (slightly slower)")
            _redis_client = None
    
    return _redis_client


def compute_sha256(content):
    """Compute SHA256 hash of content (bytes or string)."""
    if isinstance(content, str):
        content = content.encode('utf-8')
    return hashlib.sha256(content).hexdigest()


def compute_file_hash(file_path):
    """Compute SHA256 hash of file content."""
    hasher = hashlib.sha256()
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            hasher.update(chunk)
    return hasher.hexdigest()


def jaccard_similarity(text1, text2):
    """
    Calculate Jaccard similarity between two texts based on word sets.
    Returns value between 0 and 1 (1 = identical).
    """
    if not text1 or not text2:
        return 0.0
    
    # Normalize: lowercase, split into words
    words1 = set(text1.lower().split())
    words2 = set(text2.lower().split())
    
    if not words1 or not words2:
        return 0.0
    
    intersection = len(words1 & words2)
    union = len(words1 | words2)
    
    return intersection / union if union > 0 else 0.0


def find_similar_cached_evaluation(client, question_hash, answer_text):
    """
    Find a cached evaluation with similar answer (>= 95% Jaccard similarity).
    Returns (cached_result, answer_hash) if found, else (None, None).
    """
    if not client:
        return None, None
    
    try:
        # Get all similarity keys for this question
        pattern = f"{SIMILARITY_KEY_PREFIX}{question_hash}:*"
        keys = client.keys(pattern)
        
        for key in keys[:50]:  # Check max 50 cached answers for performance
            try:
                cached_data = client.get(key)
                if cached_data:
                    data = json.loads(cached_data)
                    cached_answer = data.get('answer_text', '')
                    similarity = jaccard_similarity(answer_text, cached_answer)
                    
                    if similarity >= SIMILARITY_THRESHOLD:
                        answer_hash = key.split(':')[-1]
                        eval_key = f"{EVAL_KEY_PREFIX}{question_hash}:{answer_hash}"
                        eval_data = client.get(eval_key)
                        
                        if eval_data:
                            print(f"✨ cache HIT (similarity: {similarity:.1%})")
                            return json.loads(eval_data), answer_hash
            except Exception:
                continue
        
        return None, None
    except Exception as e:
        print(f"⚠️  Similarity search error: {e}")
        return None, None


def cache_ocr_result(func):
    """
    Decorator to cache OCR results using file content SHA256 hash.
    TTL: 30 days
    Key format: cache:ocr:{file_hash}
    """
    @functools.wraps(func)
    def wrapper(file_path, *args, **kwargs):
        client = get_redis_client()
        
        if not client:
            # No caching, just call the function
            return func(file_path, *args, **kwargs)
        
        try:
            # Compute file hash
            file_hash = compute_file_hash(file_path)
            cache_key = f"{OCR_KEY_PREFIX}{file_hash}"
            
            # Check cache
            cached = client.get(cache_key)
            if cached:
                print(f"✨ cache HIT for OCR: {os.path.basename(file_path)}")
                return cached
            
            print(f"⏳ cache MISS for OCR: {os.path.basename(file_path)}")
            
            # Call the actual function
            result = func(file_path, *args, **kwargs)
            
            # Cache the result if it's not empty
            if result and result.strip():
                client.setex(cache_key, OCR_CACHE_TTL, result)
                print(f"💾 cached OCR result ({len(result)} chars)")
            
            return result
            
        except Exception as e:
            print(f"⚠️  OCR cache error: {e}")
            return func(file_path, *args, **kwargs)
    
    return wrapper


def cache_ai_evaluation(func):
    """
    Decorator to cache AI evaluation results.
    Uses question+answer hash as key with semantic similarity detection.
    TTL: 7 days
    Key format: cache:eval:{question_hash}:{answer_hash}
    """
    @functools.wraps(func)
    def wrapper(question, correct_answer, student_answer, *args, **kwargs):
        client = get_redis_client()
        
        if not client:
            # No caching, just call the function
            return func(question, correct_answer, student_answer, *args, **kwargs)
        
        try:
            # Compute hashes
            question_hash = compute_sha256(question)[:16]  # First 16 chars for readability
            answer_hash = compute_sha256(student_answer)[:16]
            
            # Check exact match first
            cache_key = f"{EVAL_KEY_PREFIX}{question_hash}:{answer_hash}"
            cached = client.get(cache_key)
            
            if cached:
                print(f"✨ cache HIT for AI evaluation (exact match)")
                return json.loads(cached)
            
            # Check for similar answers (95%+ similarity)
            similar_result, similar_hash = find_similar_cached_evaluation(
                client, question_hash, student_answer
            )
            
            if similar_result:
                # Found similar answer, return cached evaluation
                return similar_result
            
            print(f"⏳ cache MISS for AI evaluation")
            
            # Call the actual function
            result = func(question, correct_answer, student_answer, *args, **kwargs)
            
            # Cache the result
            if result and 'score' in result:
                # Store evaluation
                client.setex(cache_key, EVAL_CACHE_TTL, json.dumps(result))
                
                # Store similarity data for future matching
                similarity_key = f"{SIMILARITY_KEY_PREFIX}{question_hash}:{answer_hash}"
                similarity_data = {
                    'answer_text': student_answer[:2000],  # Store first 2000 chars for matching
                    'timestamp': datetime.now().isoformat()
                }
                client.setex(similarity_key, EVAL_CACHE_TTL, json.dumps(similarity_data))
                
                print(f"💾 cached AI evaluation (score: {result['score']})")
            
            return result
            
        except Exception as e:
            print(f"⚠️  Evaluation cache error: {e}")
            return func(question, correct_answer, student_answer, *args, **kwargs)
    
    return wrapper


def get_cache_stats():
    """
    Get cache statistics including hit rate, keyspace info, and connection status.
    Returns dict with stats or empty dict if Redis unavailable.
    """
    client = get_redis_client()
    
    stats = {
        'enabled': CACHE_ENABLED,
        'redis_available': REDIS_AVAILABLE,
        'connected': False,
        'hit_rate': 0,
        'keyspace_hits': 0,
        'keyspace_misses': 0,
        'total_keys': 0,
        'ocr_keys': 0,
        'eval_keys': 0,
        'memory_used': 'N/A',
        'uptime_seconds': 0
    }
    
    if not client:
        return stats
    
    try:
        # Test connection
        client.ping()
        stats['connected'] = True
        
        # Get server info
        info = client.info()
        
        # Keyspace statistics
        stats['keyspace_hits'] = info.get('keyspace_hits', 0)
        stats['keyspace_misses'] = info.get('keyspace_misses', 0)
        
        total = stats['keyspace_hits'] + stats['keyspace_misses']
        if total > 0:
            stats['hit_rate'] = round((stats['keyspace_hits'] / total) * 100, 2)
        
        # Memory usage
        stats['memory_used'] = info.get('used_memory_human', 'N/A')
        stats['uptime_seconds'] = info.get('uptime_in_seconds', 0)
        
        # Count our cache keys
        stats['total_keys'] = client.dbsize()
        stats['ocr_keys'] = len(client.keys(f"{OCR_KEY_PREFIX}*"))
        stats['eval_keys'] = len(client.keys(f"{EVAL_KEY_PREFIX}*"))
        
    except Exception as e:
        stats['error'] = str(e)
    
    return stats


def clear_cache(pattern=None):
    """
    Clear cache keys matching pattern.
    If pattern is None, clears all cache keys (ocr, eval, similarity).
    Returns number of keys deleted.
    """
    client = get_redis_client()
    
    if not client:
        return 0
    
    try:
        deleted = 0
        
        if pattern:
            keys = client.keys(pattern)
            if keys:
                deleted = client.delete(*keys)
        else:
            # Clear all our cache keys
            for prefix in [OCR_KEY_PREFIX, EVAL_KEY_PREFIX, SIMILARITY_KEY_PREFIX]:
                keys = client.keys(f"{prefix}*")
                if keys:
                    deleted += client.delete(*keys)
        
        print(f"🗑️  Cleared {deleted} cache keys")
        return deleted
        
    except Exception as e:
        print(f"⚠️  Cache clear error: {e}")
        return 0


# No-op decorators for when caching is disabled
def noop_decorator(func):
    """No-operation decorator that just returns the original function."""
    return func


# Export appropriate decorators based on availability
if REDIS_AVAILABLE and CACHE_ENABLED:
    print("🚀 Redis caching module loaded")
else:
    print("ℹ️  Running without Redis caching")
    # Override decorators with no-ops
    cache_ocr_result = noop_decorator
    cache_ai_evaluation = noop_decorator
