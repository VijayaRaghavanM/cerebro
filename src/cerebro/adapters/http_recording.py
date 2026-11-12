"""Keep a model's HTTP exchanges, and serve them back with no network."""

import json
import operator
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx

from cerebro.domain.evaluation import Exchange

# What the transport hands on is decoded and re-sized, so these would be wrong.
BODY_HEADERS = {"content-encoding", "content-length", "transfer-encoding"}


class RecordingTransport(httpx.BaseTransport):
    """Passes requests on and keeps each request body and the reply's status and
    body, never a header, so no key is kept.

    The caller gets the reply's headers back: a Retry-After above this transport
    still counts.
    """

    def __init__(
        self,
        inner: httpx.BaseTransport | None = None,
        exchanges: list[Exchange] | None = None,
    ) -> None:
        self.inner = inner or httpx.HTTPTransport()
        self.exchanges = [] if exchanges is None else exchanges

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        response = self.inner.handle_request(request)

        raw = response.read()
        # A reply that is not JSON, such as a proxy's HTML error page, is kept as
        # "text" where a JSON one is kept as "body".
        try:
            kept = {"body": json.loads(raw)}
        except ValueError:
            kept = {"text": raw.decode("utf-8", errors="replace")}
        self.exchanges.append(
            {
                "request": json.loads(request.content),
                "response": {"status": response.status_code, **kept},
            }
        )

        headers = [
            (name, value)
            for name, value in response.headers.multi_items()
            if name.lower() not in BODY_HEADERS
        ]
        return httpx.Response(response.status_code, headers=headers, content=raw)

    def save(self, path: Path, last_only: bool = False) -> None:
        exchanges = self.exchanges[-1:] if last_only else self.exchanges
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(exchanges, indent=2) + "\n", encoding="utf-8")


class ReplayMismatch(Exception):
    """A request the recording cannot answer: it differs, or none is left.

    Not an httpx error, because model libraries retry those, with waits, and a
    replay would only fail the same way again.
    """


class ReplayTransport(httpx.BaseTransport):
    """Answers each request with the next recorded reply, in order.

    A request that differs from the recorded one fails, because the code that
    sent it has changed and the recording no longer shows what it would get.
    `same` says whether a sent body matches the recorded one; by default the
    two must be equal.
    """

    def __init__(
        self,
        exchanges: list[Exchange],
        same: Callable[[Any, Any], bool] = operator.eq,
    ) -> None:
        self._exchanges = exchanges
        self._same = same
        self._served = 0

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        if self._served == len(self._exchanges):
            raise ReplayMismatch(
                f"more requests than the {len(self._exchanges)} recorded exchanges"
            )

        exchange = self._exchanges[self._served]
        if not self._same(json.loads(request.content), exchange["request"]):
            raise ReplayMismatch(
                f"request {self._served + 1} differs from the recorded one"
            )

        # Counted only after a match, so a retried request meets the same exchange.
        self._served += 1
        reply = exchange["response"]
        if "text" in reply:
            return httpx.Response(reply["status"], text=reply["text"])
        return httpx.Response(reply["status"], json=reply["body"])
