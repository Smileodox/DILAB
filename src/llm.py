import json
import re
import time

from openai import AzureOpenAI, APIError, APITimeoutError, APIConnectionError, RateLimitError
from src import config

_client = None

def get_client() -> AzureOpenAI:
    global _client
    if _client is None:
        _client = AzureOpenAI(
            azure_endpoint=config.AZURE_OPENAI_ENDPOINT,
            api_key=config.AZURE_OPENAI_API_KEY,
            api_version=config.AZURE_OPENAI_API_VERSION,
        )
    return _client


def chat(prompt: str, system: str = "", temperature: float = 0.3, model: str | None = None) -> str:
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    response = get_client().chat.completions.create(
        model=model or config.AZURE_OPENAI_CHAT_DEPLOYMENT,
        messages=messages,
        temperature=temperature,
    )
    return response.choices[0].message.content


def chat_json(prompt: str, system: str = "", temperature: float = 0.1, model: str | None = None) -> str:
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    response = get_client().chat.completions.create(
        model=model or config.AZURE_OPENAI_CHAT_DEPLOYMENT,
        messages=messages,
        temperature=temperature,
        response_format={"type": "json_object"},
    )
    return response.choices[0].message.content


_RETRYABLE = (APIError, APITimeoutError, APIConnectionError, RateLimitError)

def safe_chat_json(prompt: str, system: str = "", temperature: float = 0.1, retries: int = 3, model: str | None = None) -> dict:
    for attempt in range(retries + 1):
        try:
            raw = chat_json(prompt, system=system, temperature=temperature, model=model)
        except _RETRYABLE as e:
            if attempt < retries:
                wait = 2 ** attempt * 5
                print(f"  ⚠ API error: {type(e).__name__}, retrying in {wait}s ({attempt + 1}/{retries})...")
                time.sleep(wait)
                continue
            print(f"  ⚠ API error after {retries + 1} attempts: {e}")
            return {}
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", raw, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(0))
                except json.JSONDecodeError:
                    pass
            if attempt < retries:
                print(f"  ⚠ JSON parse failed, retrying ({attempt + 1}/{retries})...")
                continue
            print(f"  ⚠ JSON parse failed after {retries + 1} attempts, returning empty dict")
            return {}


def embed(texts: list[str]) -> list[list[float]]:
    response = get_client().embeddings.create(
        model=config.AZURE_OPENAI_EMBEDDING_DEPLOYMENT,
        input=texts,
    )
    return [item.embedding for item in response.data]
