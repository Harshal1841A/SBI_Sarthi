import os
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import structlog

logger = structlog.get_logger()
whatsapp_router = APIRouter()

# Webhook verification token for WhatsApp API — MUST be set in env
WHATSAPP_VERIFY_TOKEN = os.environ.get("WHATSAPP_VERIFY_TOKEN", "")
if not WHATSAPP_VERIFY_TOKEN:
    import secrets
    WHATSAPP_VERIFY_TOKEN = secrets.token_hex(16)
    logger.warning("whatsapp_verify_token_missing", temp_token=WHATSAPP_VERIFY_TOKEN)

class WhatsAppMessage(BaseModel):
    # Simplified model for WhatsApp webhook payload
    object: str
    entry: list

@whatsapp_router.get("/webhook")
async def verify_webhook(
    hub_mode: str = None,
    hub_challenge: str = None,
    hub_verify_token: str = None
):
    """WhatsApp webhook verification."""
    if hub_mode == "subscribe" and hub_verify_token == WHATSAPP_VERIFY_TOKEN:
        return int(hub_challenge)
    raise HTTPException(status_code=403, detail="Invalid verify token")

@whatsapp_router.post("/webhook")
async def receive_message(payload: WhatsAppMessage):
    """Receive messages from WhatsApp."""
    logger.info("Received WhatsApp payload", payload=payload.dict())
    
    # In production: extract phone number, message text, and route to the LangGraph
    # We will simulate routing to the graph in main.py
    
    return {"status": "received"}

async def send_whatsapp_message(to: str, message: str):
    """Send message to user via WhatsApp API."""
    import httpx
    token = os.environ.get("WHATSAPP_API_TOKEN", "")
    phone_id = os.environ.get("WHATSAPP_PHONE_ID", "")
    
    if not token or not phone_id:
        logger.warning("WhatsApp API not configured. Mocking send.")
        return True
        
    url = f"https://graph.facebook.com/v17.0/{phone_id}/messages"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    data = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": message}
    }
    
    async with httpx.AsyncClient() as client:
        resp = await client.post(url, headers=headers, json=data)
        if resp.status_code != 200:
            logger.error("WhatsApp send failed", response=resp.text)
            return False
        return True
