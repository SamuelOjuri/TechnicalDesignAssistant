import threading
import time
from typing import Optional
from flask import current_app
import logging

logger = logging.getLogger(__name__)

class GlobalGeminiRateLimiter:
    """
    Global rate limiter for Gemini API calls across all threads.
    Implements token bucket algorithm with semaphore coordination.
    """
    
    def __init__(self, 
                 requests_per_minute: int = 950,  # Increased to 950, still with safety margin
                 max_concurrent: int = 15):       # Increased from 7 to take advantage of higher limits
        self.requests_per_minute = requests_per_minute
        self.max_concurrent = max_concurrent
        
        # Semaphore to limit concurrent requests
        self._semaphore = threading.Semaphore(max_concurrent)
        
        # Token bucket for rate limiting
        self._tokens = requests_per_minute
        self._last_refill = time.time()
        self._lock = threading.Lock()
        
    def acquire(self) -> bool:
        """Acquire permission to make API call."""
        # Check tokens first, then acquire semaphore
        with self._lock:
            now = time.time()
            # Refill tokens
            time_passed = now - self._last_refill
            tokens_to_add = int(time_passed * self.requests_per_minute / 60)
            
            if tokens_to_add > 0:
                self._tokens = min(self.requests_per_minute, self._tokens + tokens_to_add)
                self._last_refill = now
            
            if self._tokens <= 0:
                return False
            
            # Only acquire semaphore if we have tokens
            if not self._semaphore.acquire(blocking=False):
                return False
            
            self._tokens -= 1
            logger.info(f"API call approved. Tokens remaining: {self._tokens}")
            return True
    
    def release(self):
        """Release the semaphore slot."""
        self._semaphore.release()
        
    def wait_for_availability(self, timeout: int = 300) -> bool:
        """Wait until API call can be made."""
        start_time = time.time()
        while time.time() - start_time < timeout:
            if self.acquire():
                return True
            time.sleep(1)
        return False

# Global instance
_rate_limiter: Optional[GlobalGeminiRateLimiter] = None

def get_rate_limiter() -> GlobalGeminiRateLimiter:
    """Get or create global rate limiter instance."""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = GlobalGeminiRateLimiter()
    return _rate_limiter