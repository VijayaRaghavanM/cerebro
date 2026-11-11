"""Mistral's chat model, paced to the account's rate limit."""

import time
from collections.abc import Callable

import httpx
from langchain_core.language_models import BaseChatModel
from langchain_core.rate_limiters import InMemoryRateLimiter
from langchain_mistralai import ChatMistralAI
from pydantic import SecretStr

MODEL = "ministral-14b-2512"
# The account's limit, from Mistral's x-ratelimit-limit-req-minute header on
# 2026-11-11.
REQUESTS_PER_MINUTE = 2
# Requests spaced exactly at the limit drew 429s, most likely because network
# delay put three inside one 60-second window. The margin leaves room for it.
MARGIN_SECONDS = 5
SECONDS_BETWEEN_REQUESTS = 60 / REQUESTS_PER_MINUTE + MARGIN_SECONDS
# The limit is per account, so every model in the process shares one pace.
PACE = InMemoryRateLimiter(
    requests_per_second=1 / SECONDS_BETWEEN_REQUESTS, max_bucket_size=1
)


BASE_URL = "https://api.mistral.ai/v1"
# ChatMistralAI's own default, which a client we pass in replaces.
TIMEOUT_SECONDS = 120
# The pace still draws an occasional 429, and LangChain's client does not retry
# one, so a single 429 would end the agent's run.
RETRIES = 3
# One pace interval: long enough for the window that refused us to move on.
RETRY_WAIT_SECONDS = SECONDS_BETWEEN_REQUESTS


class RetryRateLimited(httpx.BaseTransport):
    """Sends a request again after a 429, then gives up and returns that 429."""

    def __init__(
        self,
        inner: httpx.BaseTransport,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._inner = inner
        self._sleep = sleep

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        response = self._inner.handle_request(request)

        for _ in range(RETRIES):
            if response.status_code != 429:
                break
            wait = _seconds_to_wait(response)
            response.close()
            self._sleep(wait)
            response = self._inner.handle_request(request)

        return response

    def close(self) -> None:
        self._inner.close()


def _seconds_to_wait(response: httpx.Response) -> float:
    try:
        return float(response.headers["Retry-After"])
    except (KeyError, ValueError):
        return RETRY_WAIT_SECONDS


def retrying_client(
    api_key: SecretStr,
    inner: httpx.BaseTransport | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> httpx.Client:
    """The client ChatMistralAI would build, with its 429s retried.

    Given a client, ChatMistralAI adds no base URL, headers or timeout, so they
    are set here as it sets them.
    """
    return httpx.Client(
        base_url=BASE_URL,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {api_key.get_secret_value()}",
        },
        timeout=TIMEOUT_SECONDS,
        transport=RetryRateLimited(inner or httpx.HTTPTransport(), sleep),
    )


def ministral(api_key: SecretStr) -> BaseChatModel:
    """Ministral 14B at temperature 0, waiting its turn between requests."""
    return ChatMistralAI(
        model_name=MODEL,
        api_key=api_key,
        temperature=0,
        rate_limiter=PACE,
        client=retrying_client(api_key),
    )
