import asyncio
import os
from dotenv import load_dotenv
from nlp.nemotron_client import NemotronClient

load_dotenv()

async def test_nemotron():
    client = NemotronClient()
    messages = [{"role": "user", "content": "Hello, how are you? Answer in 1 sentence."}]
    print("Testing chat...")
    try:
        response = await client.chat(messages=messages, max_tokens=100)
        print("Response:", response)
        print("Nemotron chat is WORKING!")
    except Exception as e:
        print("Error during chat:", e)
        print("Nemotron chat is FAILING!")
        return

    print("\nTesting stream...")
    try:
        print("Streaming response: ", end="")
        async for chunk in client.stream(messages=messages):
            print(chunk, end="", flush=True)
        print("\nNemotron stream is WORKING!")
    except Exception as e:
        print("\nError during stream:", e)
        print("Nemotron stream is FAILING!")

if __name__ == "__main__":
    asyncio.run(test_nemotron())
