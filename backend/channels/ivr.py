from fastapi import APIRouter, Request, Response
import structlog
import xml.etree.ElementTree as ET

logger = structlog.get_logger()
ivr_router = APIRouter()

def generate_twiml_response(text: str) -> str:
    """Generate Twilio TwiML response for IVR."""
    response = ET.Element("Response")
    say = ET.SubElement(response, "Say", voice="Polly.Aditi", language="en-IN")
    say.text = text
    
    # We could also use Gather for DTMF or voice input
    gather = ET.SubElement(response, "Gather", input="speech dtmf", timeout="3", speechTimeout="auto")
    return "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n" + ET.tostring(response, encoding="unicode")

@ivr_router.post("/incoming")
async def handle_ivr_call(request: Request):
    """Handle incoming IVR call from Twilio or similar."""
    form_data = await request.form()
    call_sid = form_data.get("CallSid")
    speech_result = form_data.get("SpeechResult")
    
    logger.info("Received IVR request", call_sid=call_sid, speech=speech_result)
    
    if not speech_result:
        # Initial greeting
        twiml = generate_twiml_response("Welcome to SBI Sarthi. How can I help you today?")
    else:
        # In production: pass speech_result to the graph
        # For now, return mock response
        twiml = generate_twiml_response("I have received your request and am processing it.")
        
    return Response(content=twiml, media_type="application/xml")
