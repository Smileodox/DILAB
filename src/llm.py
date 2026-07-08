from __future__ import annotations

import itertools
import json
import logging
import random
import re
import threading
import time
from typing import TypeVar

from openai import AzureOpenAI, APIError, APITimeoutError, APIConnectionError, RateLimitError
from pydantic import BaseModel, ValidationError

from src import config

log = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)


class _ClientPool:
    """Round-robin pool of Azure OpenAI clients across multiple endpoints."""

    def __init__(self):
        self._clients: list[AzureOpenAI] = []
        self._cycle = None
        self._lock = threading.Lock()
        self._per_client_locks: list[threading.Lock] = []
        self._per_client_last_call: list[float] = []
        self._initialized = False

    def _init(self):
        if self._initialized:
            return
        endpoints = config.AZURE_ENDPOINTS
        if not endpoints:
            raise RuntimeError(
                "AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_API_KEY must be set. "
                "Copy .env.example to .env and fill in your credentials."
            )
        for ep in endpoints:
            self._clients.append(AzureOpenAI(
                azure_endpoint=ep["endpoint"],
                api_key=ep["api_key"],
                api_version=ep["api_version"],
                # Bound each attempt so an occasionally-stalled gpt-5.4 request fails fast and is
                # retried by safe_chat_json (APITimeoutError is retryable) instead of blocking the
                # whole pipeline until the SDK's 600s default — the CIB/narrative-phase stalls.
                timeout=120.0,
            ))
            self._per_client_locks.append(threading.Lock())
            self._per_client_last_call.append(0.0)
        self._cycle = itertools.cycle(range(len(self._clients)))
        self._initialized = True
        if len(self._clients) > 1:
            print(f"  LLM pool: {len(self._clients)} endpoints (round-robin)", flush=True)

    def get(self) -> tuple[AzureOpenAI, int]:
        """Get next client in round-robin order. Returns (client, index)."""
        with self._lock:
            self._init()
            idx = next(self._cycle)
        # Per-endpoint throttle
        with self._per_client_locks[idx]:
            now = time.time()
            wait = _MIN_CALL_INTERVAL - (now - self._per_client_last_call[idx])
            if wait > 0:
                time.sleep(wait)
            self._per_client_last_call[idx] = time.time()
        return self._clients[idx], idx

    def get_primary(self) -> AzureOpenAI:
        """Get the primary (first) client — used for embeddings."""
        with self._lock:
            self._init()
        return self._clients[0]


_pool = _ClientPool()
_MIN_CALL_INTERVAL = 0.5


_POOLED_MODELS = {"gpt-5.4", "gpt-5.4-mini"}


def _get_client(model: str | None):
    """Round-robin for models available on all endpoints, primary-only for others.

    Uses the EFFECTIVE model (explicit arg, else the default chat deployment) so that
    calls made without a model — manifestations/trends/merge — also round-robin whenever
    the default deployment is a pooled model. Otherwise they'd all hammer the primary
    endpoint (the gpt-4.1-mini single-endpoint 429 storm).
    """
    effective = model or config.AZURE_OPENAI_CHAT_DEPLOYMENT
    if effective in _POOLED_MODELS:
        return _pool.get()[0]
    return _pool.get_primary()


def chat(prompt: str, system: str = "", temperature: float = 0.3, model: str | None = None) -> str:
    client = _get_client(model)
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    response = client.chat.completions.create(
        model=model or config.AZURE_OPENAI_CHAT_DEPLOYMENT,
        messages=messages,
        temperature=temperature,
    )
    return response.choices[0].message.content


def chat_json(prompt: str, system: str = "", temperature: float = 0.1, model: str | None = None) -> str:
    client = _get_client(model)
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    response = client.chat.completions.create(
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
                wait = 2 ** attempt * 5 + random.uniform(0, 3)
                print(f"  API error: {type(e).__name__}, retrying in {wait:.0f}s ({attempt + 1}/{retries})...", flush=True)
                time.sleep(wait)
                continue
            print(f"  API error after {retries + 1} attempts: {e}", flush=True)
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
                print(f"  JSON parse failed, retrying ({attempt + 1}/{retries})...", flush=True)
                continue
            print(f"  JSON parse failed after {retries + 1} attempts, returning empty dict", flush=True)
            return {}


def validated_chat_json(
    prompt: str,
    response_model: type[T],
    system: str = "",
    temperature: float = 0.1,
    retries: int = 3,
    model: str | None = None,
) -> T:
    """Like safe_chat_json but validates the response against a Pydantic model.

    Retries on validation failure with an explicit schema reminder.
    Raises ValidationError if all attempts fail.
    """
    last_error: ValidationError | None = None
    for attempt in range(retries + 1):
        raw = safe_chat_json(prompt, system=system, temperature=temperature, retries=3, model=model)
        if not raw:
            if attempt < retries:
                print(f"  Empty LLM response, retrying ({attempt + 1}/{retries})...", flush=True)
                continue
            raise ValidationError.from_exception_data(
                title=response_model.__name__,
                line_errors=[],
            )
        try:
            return response_model.model_validate(raw)
        except ValidationError as e:
            last_error = e
            print(f"  Validation failed ({response_model.__name__}), retrying ({attempt + 1}/{retries})...", flush=True)
            if attempt < retries:
                prompt = (
                    prompt + "\n\nIMPORTANT: Your previous response had validation errors. "
                    f"Required schema fields: {list(response_model.model_fields.keys())}"
                )
                continue
    raise last_error  # type: ignore[misc]


def embed(texts: list[str], retries: int = 4) -> list[list[float]]:
    """Embed texts via the primary endpoint, retrying transient network/rate errors.

    Embeddings use a single deployment (not pooled across endpoints), and embed() is called deep
    inside trends/merge/scenario_gen with no other safety net — so a single transient
    APIConnectionError/RateLimitError here would otherwise crash a whole (multi-minute) run.
    Mirrors safe_chat_json's backoff; re-raises after the last attempt (embeddings can't be faked).
    """
    for attempt in range(retries + 1):
        try:
            client = _pool.get_primary()
            response = client.embeddings.create(
                model=config.AZURE_OPENAI_EMBEDDING_DEPLOYMENT,
                input=texts,
            )
            return [item.embedding for item in response.data]
        except _RETRYABLE as e:
            if attempt < retries:
                wait = 2 ** attempt * 5 + random.uniform(0, 3)
                print(f"  Embed error: {type(e).__name__}, retrying in {wait:.0f}s "
                      f"({attempt + 1}/{retries})...", flush=True)
                time.sleep(wait)
                continue
            raise
