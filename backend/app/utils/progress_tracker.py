import redis
import json
import time
import os
from typing import Dict, Any, Optional
from flask import current_app

# Global connection pool for ProgressTracker (optimized for your 7-worker setup)
_progress_redis_pool = None

def get_progress_redis_pool():
    """Get or create Redis connection pool for progress tracking."""
    global _progress_redis_pool
    if _progress_redis_pool is None:
        # Try to get Redis URL from Flask app context first, fallback to environment
        try:
            redis_url = current_app.config.get('REDIS_URL', 'redis://localhost:6379/0')
        except RuntimeError:
            # Working outside Flask app context (e.g., in Celery worker)
            # Get Redis URL from environment variables
            redis_url = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
        
        _progress_redis_pool = redis.ConnectionPool.from_url(
            redis_url, 
            max_connections=15,  # 7 workers + 5 WebSocket + 3 buffer
            retry_on_timeout=True,
            socket_connect_timeout=5,
            socket_timeout=5
        )
    return _progress_redis_pool

class ProgressTracker:
    """Handles progress tracking and streaming for background tasks."""
    
    def __init__(self, job_id: str):
        self.job_id = job_id
        # Use connection pool (reduces connection overhead)
        self.redis_client = redis.Redis(connection_pool=get_progress_redis_pool())
        self.progress_key = f"progress:{job_id}"
        self.stream_key = f"stream:{job_id}"
        
    def update_progress(self, stage: str, current_file: str, progress: int, 
                       message: str, result: Optional[Dict] = None, 
                       error: Optional[str] = None):
        """Update the progress information."""
        progress_data = {
            'job_id': self.job_id,
            'stage': stage,
            'current_file': current_file,
            'progress': progress,
            'message': message,
            'timestamp': time.time(),
            'result': result,
            'error': error
        }
        
        # Store in Redis with 1 hour expiration
        self.redis_client.setex(
            self.progress_key, 
            3600,  # 1 hour
            json.dumps(progress_data)
        )
        
        # Filter out None values for Redis stream (Redis doesn't accept None)
        stream_data = {}
        for key, value in progress_data.items():
            if value is not None:
                if isinstance(value, dict):
                    # Convert dict to JSON string
                    stream_data[key] = json.dumps(value)
                else:
                    # Convert to string to ensure Redis compatibility
                    stream_data[key] = str(value)
        
        # Also add to stream for real-time updates
        self.redis_client.xadd(
            self.stream_key,
            stream_data,  # Use filtered data instead of progress_data
            maxlen=100  # Keep last 100 updates
        )
        
        # Set expiration on stream key too
        self.redis_client.expire(self.stream_key, 3600)
        
    def stream_partial_result(self, result_type: str, content: str):
        """Stream partial results as they become available."""
        partial_data = {
            'type': 'partial_result',
            'result_type': result_type,
            'content': content,
            'timestamp': time.time()
        }
        
        # Convert all values to strings for Redis compatibility
        stream_data = {k: str(v) for k, v in partial_data.items()}
        
        # Add to stream
        self.redis_client.xadd(
            self.stream_key,
            stream_data,  # Use converted data
            maxlen=200  # Keep more partial results
        )
        
    def get_progress(self) -> Optional[Dict]:
        """Get current progress."""
        data = self.redis_client.get(self.progress_key)
        if data:
            return json.loads(data)
        return None
