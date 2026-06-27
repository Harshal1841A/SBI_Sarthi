import time
import asyncio
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
import structlog

logger = structlog.get_logger()

class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, rate_limit: int = 100, window: int = 60):
        super().__init__(app)
        self.rate_limit = rate_limit
        self.window = window

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
                    logger.warning("Rate limit exceeded", ip=client_ip, path=request.url.path)
                    raise HTTPException(status_code=429, detail="Too Many Requests")
        except Exception as e:
            # Fail closed: if Redis is down, deny the request for banking security
            logger.error("Rate limiter failed (Redis unavailable)", ip=client_ip, error=str(e))
            raise HTTPException(status_code=503, detail="Service temporarily unavailable — rate limiter offline")
            
        response = await call_next(request)
        return response
