import asyncio
import os
import httpx
from dotenv import load_dotenv

load_dotenv()

async def test_nvcf_tts():
    api_key = os.environ.get("NIM_API_KEY", "")
    url = "https://api.nvcf.nvidia.com/v2/nvcf/pexec/functions/ddacc747-1269-4fab-bfd9-8f593dead106"
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    
    # Payload as per standard NVIDIA Riva/Chatterbox NVCF
    payload = {
        "text": "Hello, this is a test of the NVIDIA Chatterbox API.",
        "language_code": "en-US", # sometimes languageCode
        "voice": "Chatterbox-Multilingual.en-US.Male", # or voiceName
        "output": "audio.wav"
    }
    
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, headers=headers, json=payload)
            print(f"Status: {resp.status_code}")
            if resp.status_code == 200:
                print(f"Success! Content-Type: {resp.headers.get('content-type')}")
                print(f"Data preview: {resp.text[:200]}")
            else:
                print(f"Error Response: {resp.text}")
    except Exception as e:
        print("Exception:", e)

    # Let's try alternative payload if the first fails
    payload_alt = {
        "text": "Hello, this is a test of the NVIDIA Chatterbox API.",
        "languageCode": "en-US",
        "voiceName": "Chatterbox-Multilingual.en-US.Male"
    }
    
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, headers=headers, json=payload_alt)
            print(f"\nAlt Status: {resp.status_code}")
            if resp.status_code == 200:
                print(f"Success! Content-Type: {resp.headers.get('content-type')}")
                print(f"Data preview: {resp.text[:200]}")
            else:
                print(f"Error Response: {resp.text}")
    except Exception as e:
        print("Exception:", e)

if __name__ == "__main__":
    asyncio.run(test_nvcf_tts())
