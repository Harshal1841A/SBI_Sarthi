import time, asyncio
from typing import Callable, Any
from enum import Enum

import inspect

class State(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

class CircuitBreaker:
    def __init__(self, failure_threshold: int = 5, recovery_timeout: float = 30.0):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.state = State.CLOSED
        self.failure_count = 0
        self.last_failure_time = None
    
    def call(self, fn: Callable) -> Callable:
        if inspect.isasyncgenfunction(fn):
            async def gen_wrapper(*args, **kwargs):
                if self.state == State.OPEN:
                    if time.time() - self.last_failure_time < self.recovery_timeout:
                        raise RuntimeError("Circuit breaker OPEN")
                    self.state = State.HALF_OPEN
                    self.failure_count = 0
                
                try:
                    async for item in fn(*args, **kwargs):
                        yield item
                    if self.state == State.HALF_OPEN:
                        self.state = State.CLOSED
                        self.failure_count = 0
                except Exception as e:
                    self.failure_count += 1
                    self.last_failure_time = time.time()
                    if self.failure_count >= self.failure_threshold:
                        self.state = State.OPEN
                    raise
            return gen_wrapper
        else:
            async def wrapper(*args, **kwargs):
                if self.state == State.OPEN:
                    if time.time() - self.last_failure_time < self.recovery_timeout:
                        raise RuntimeError("Circuit breaker OPEN")
                    self.state = State.HALF_OPEN
                    self.failure_count = 0
                
                try:
                    result = await fn(*args, **kwargs)
                    if self.state == State.HALF_OPEN:
                        self.state = State.CLOSED
                        self.failure_count = 0
                    return result
                except Exception as e:
                    self.failure_count += 1
                    self.last_failure_time = time.time()
                    if self.failure_count >= self.failure_threshold:
                        self.state = State.OPEN
                    raise
            return wrapper
