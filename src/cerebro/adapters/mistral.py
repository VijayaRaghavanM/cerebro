"""Mistral's chat model, paced to the account's rate limit."""

from langchain_core.language_models import BaseChatModel
from langchain_core.rate_limiters import InMemoryRateLimiter
from langchain_mistralai import ChatMistralAI
from pydantic import SecretStr

MODEL = "ministral-14b-2512"
# The account's limit, from Mistral's x-ratelimit-limit-req-minute header on
# 2026-11-11. Pacing keeps requests at that rate.
REQUESTS_PER_MINUTE = 2
# The limit is per account, so every model in the process shares one pace.
PACE = InMemoryRateLimiter(
    requests_per_second=REQUESTS_PER_MINUTE / 60, max_bucket_size=1
)


def ministral(api_key: SecretStr) -> BaseChatModel:
    """Ministral 14B at temperature 0, waiting its turn between requests."""
    return ChatMistralAI(
        model_name=MODEL, api_key=api_key, temperature=0, rate_limiter=PACE
    )
