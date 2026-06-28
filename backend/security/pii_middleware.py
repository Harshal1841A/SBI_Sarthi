import json
from typing import Any, Callable
from security.pii_scrubber import scrub_pii


def _scrub_data(data: Any) -> Any:
    """Recursively scrub PII strings from JSON data structures."""
    if isinstance(data, str):
        return scrub_pii(data)
    elif isinstance(data, dict):
        return {k: _scrub_data(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [_scrub_data(item) for item in data]
    return data


class PIIIngressMiddleware:
    """Pure ASGI middleware to intercept and scrub PII from chat request bodies."""

    def __init__(self, app: Any) -> None:
        """Initialize the ASGI middleware with the wrapped app."""
        self.app = app

    async def __call__(self, scope: dict, receive: Callable, send: Callable) -> None:
        """Inspect POST requests to /api/chat/* or /chat/* and scrub JSON bodies."""
        if scope["type"] == "http" and scope["method"] == "POST" and (
            scope["path"].startswith("/api/chat") or scope["path"].startswith("/chat")
        ):
            headers = dict(scope.get("headers", []))
            content_type = headers.get(b"content-type", b"").decode("latin-1").lower()
            if "application/json" in content_type:
                body = b""
                more_body = True
                while more_body:
                    msg = await receive()
                    body += msg.get("body", b"")
                    more_body = msg.get("more_body", False)

                try:
                    data = json.loads(body.decode("utf-8"))
                    scrubbed_data = _scrub_data(data)
                    new_body = json.dumps(scrubbed_data).encode("utf-8")
                except Exception:
                    new_body = body

                new_headers = []
                for k, v in scope.get("headers", []):
                    if k.lower() == b"content-length":
                        new_headers.append((k, str(len(new_body)).encode("ascii")))
                    else:
                        new_headers.append((k, v))
                scope["headers"] = new_headers

                received = False

                async def new_receive() -> dict:
                    """Return the scrubbed request body once, then delegate to original receive."""
                    nonlocal received
                    if not received:
                        received = True
                        return {"type": "http.request", "body": new_body, "more_body": False}
                    return await receive()

                return await self.app(scope, new_receive, send)
        return await self.app(scope, receive, send)
