import os, asyncio
from openai import AsyncOpenAI
from dotenv import load_dotenv

load_dotenv()

async def run():
    client = AsyncOpenAI(
        base_url='https://integrate.api.nvidia.com/v1',
        api_key=os.environ.get('NIM_API_KEY')
    )
    print('sending request...')
    try:
        resp = await client.chat.completions.create(
            model='nvidia/nemotron-3-ultra-550b-a55b',
            messages=[{'role':'user', 'content':'hi'}],
            stream=True,
            timeout=10.0
        )
        print('resp received')
        async for c in resp:
            print(c)
    except Exception as e:
        print(f"Exception: {e}")

if __name__ == '__main__':
    asyncio.run(run())
