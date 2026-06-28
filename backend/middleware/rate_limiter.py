import os
import time
import asyncio
from collections import defaultdict
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
import structlog

logger = structlog.get_logger()

class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, rate_limit: int = 100, window: int = 60):
        super().__init__(app)
        self.rate_limit = rate_limit
        self.window = window
        self._local_counts = defaultdict(lambda: [0, 0.0])  # [count, window_start]

    async def dispatch(self, request: Request, call_next):
        # Skip rate limiting for health check
        if request.url.path == "/health":
            return await call_next(request)
            
        client_ip = request.client.host if request.client else "127.0.0.1"
        key = f"rate_limit:{client_ip}"
        
        try:
            redis_client = getattr(request.app.state, "redis", None)
            if redis_client:
                # Use Redis if available
                current = await redis_client.incr(key)
                if current == 1:
                    await redis_client.expire(key, self.window)
                if current > self.rate_limit:
                    logger.warning("Rate limit exceeded (Redis)", ip=client_ip, path=request.url.path)
                    raise HTTPException(status_code=429, detail="Too Many Requests")
            else:
                raise RuntimeError("Redis client not initialized")
        except HTTPException:
            raise
        except Exception as e:
            # In-process fallback when Redis is unavailable
            # Adjust limit by worker count so total across workers equals intended rate_limit
            workers = int(os.environ.get("WEB_CONCURRENCY", 4))
            local_limit = max(1, self.rate_limit // workers)
            
            if not hasattr(self, "_lock"):
                self._lock = asyncio.Lock()
                
            async with self._lock:
                now = time.time()
                # Prune old IPs to prevent memory leak under DDoS
                if len(self._local_counts) > 5000:
                    expired = [ip for ip, val in self._local_counts.items() if now - val[1] > self.window]
                    for ip in expired:
                        del self._local_counts[ip]
                        
                count, window_start = self._local_counts[client_ip]
                if now - window_start > self.window:
                    self._local_counts[client_ip] = [1, now]
                else:
                    self._local_counts[client_ip][0] += 1
                    if self._local_counts[client_ip][0] > local_limit:
                        logger.warning("Rate limit exceeded (Local Fallback)", ip=client_ip, path=request.url.path)
                        raise HTTPException(status_code=429, detail="Too Many Requests")
            
            if os.environ.get("SARTHI_ENV", "development").lower() == "production" and "Redis" not in str(e):
                pass
            
        response = await call_next(request)
        return response
