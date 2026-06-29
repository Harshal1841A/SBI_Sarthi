import json
from typing import Any, Callable
from security.pii_scrubber import scrub_pii  # pyrefly: ignore [missing-import]


def _scrub_data(data: Any) -> Any:
    """Recursively scrub PII strings from JSON data structures."""
    if isinstance(data, str):
        return scrub_pii(data)
    elif isinstance(data, dict):
        return {k: _scrub_data(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [_scrub_data(item) for item in data]
    return data


def _extract_scrubbed_text(scrubbed_data: Any) -> Any:
    if isinstance(scrubbed_data, dict):
        if "message" in scrubbed_data:
            return str(scrubbed_data["message"])
        elif "text" in scrubbed_data:
            val = scrubbed_data["text"]
            if isinstance(val, str):
                try:
                    inner = json.loads(val)
                    if isinstance(inner, dict) and "message" in inner:
                        return str(inner["message"])
                except Exception:
                    pass
            return str(val)
        return None
    return str(scrubbed_data)


class PIIIngressMiddleware:
    """Pure ASGI middleware to intercept and scrub PII from chat request bodies."""

    @staticmethod
    def _extract_scrubbed_text(scrubbed_data: Any) -> Any:
        return _extract_scrubbed_text(scrubbed_data)

    def __init__(self, app: Any) -> None:
        """Initialize the ASGI middleware with the wrapped app."""
        self.app = app

    async def __call__(self, scope: dict, receive: Callable, send: Callable) -> None:
        """Inspect HTTP requests and WebSocket frames to scrub PII."""
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

                state = scope.setdefault("state", {})
                try:
                    data = json.loads(body.decode("utf-8"))
                    scrubbed_data = _scrub_data(data)
                    new_body = json.dumps(scrubbed_data).encode("utf-8")
                    extracted = _extract_scrubbed_text(scrubbed_data)
                    if extracted is not None:
                        state["scrubbed_text"] = extracted
                except Exception:
                    new_body = body
                    state["scrubbed_text"] = scrub_pii(body.decode("utf-8", errors="ignore"))

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

        elif scope["type"] == "websocket" and (
            scope["path"].startswith("/ws/chat") or scope["path"].startswith("/ws/voice")
        ):
            state = scope.setdefault("state", {})

            async def ws_receive() -> dict:
                msg = await receive()
                if msg.get("type") == "websocket.receive" and "text" in msg and msg["text"]:
                    raw_text = msg["text"]
                    try:
                        data = json.loads(raw_text)
                        scrubbed_data = _scrub_data(data)
                        msg["text"] = json.dumps(scrubbed_data)
                        extracted = _extract_scrubbed_text(scrubbed_data)
                        if extracted is not None:
                            state["scrubbed_text"] = extracted
                    except Exception:
                        scrubbed = scrub_pii(raw_text)
                        msg["text"] = scrubbed
                        state["scrubbed_text"] = scrubbed
                return msg

            return await self.app(scope, ws_receive, send)

        return await self.app(scope, receive, send)
