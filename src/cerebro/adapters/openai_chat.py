"""A chat model on any endpoint that speaks the OpenAI chat-completions protocol."""

from collections.abc import Mapping
from typing import Any

import httpx
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

# The client refuses to build without a key, and a local server ignores it.
NO_KEY = SecretStr("not-needed")


def openai_chat(
    base_url: str,
    model: str,
    *,
    api_key: SecretStr | None = None,
    extra_body: Mapping[str, Any] | None = None,
    transport: httpx.BaseTransport | None = None,
) -> ChatOpenAI:
    """A model at temperature 0, sending through `transport` if given.

    `extra_body` adds fields the protocol lacks.
    """
    client = httpx.Client(transport=transport) if transport else None

    return ChatOpenAI(
        base_url=base_url,
        model=model,
        api_key=api_key or NO_KEY,
        temperature=0,
        extra_body=extra_body,
        http_client=client,
    )
