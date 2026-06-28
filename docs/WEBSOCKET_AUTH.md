# WebSocket Authentication Contract

## Overview
All WebSocket endpoints (`/ws/voice`, `/ws/chat/{user_id}`, `/ws/supervisor`) enforces strict authentication rules. By default, query parameter authentication (`?token=...`) is disabled to prevent token leakage in web server access logs and browser history.

## First-Frame Authentication (Preferred)
Upon connecting to any WebSocket endpoint, clients must send an authentication frame as their first JSON message within **3 seconds** of connection acceptance.

### Request Format
```json
{
  "type": "auth",
  "token": "your_api_or_supervisor_token"
}
```

### Server Behavior
- **Success**: The server keeps the connection open and proceeds with protocol initialization (e.g., sending `session_init` on `/ws/voice`).
- **Failure**: If the first frame is not received within 3 seconds, is not valid JSON, does not match the expected format, or contains an invalid token, the server closes the WebSocket connection with close code `4001`.

## Query Parameter Authentication (Legacy / Optional)
Connecting with `?token=...` is rejected by default with close code `4001`. 

To enable legacy query parameter authentication, set the following environment variable:
```env
SARTHI_ALLOW_QUERY_TOKEN=true
```
When enabled, if the query token is missing or invalid, the server closes the connection with code `4001`.
