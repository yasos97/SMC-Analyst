import os
import json
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

MODEL_ID = "nvidia/nemotron-3-super-120b-a12b"
api_key = os.getenv("NVIDIA_API_KEY")
base_url = "https://integrate.api.nvidia.com/v1"

print(f"Testing Model: {MODEL_ID}")
print(f"Base URL: {base_url}")
print(f"API Key starts with: {api_key[:10]}...")

client = OpenAI(base_url=base_url, api_key=api_key)

try:
    response = client.chat.completions.create(
        model=MODEL_ID,
        messages=[
            {"role": "user", "content": "Hello, can you hear me? Respond with one word: YES"}
        ],
        max_tokens=10
    )
    print("Response:")
    print(response.choices[0].message.content)
except Exception as e:
    print(f"Error: {e}")
