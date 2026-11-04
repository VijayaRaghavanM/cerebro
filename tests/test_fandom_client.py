import urllib.error
import urllib.parse
from typing import Any

import pytest

from cerebro.adapters.fandom import DELAY, FandomClient
from cerebro.domain.pages import PageRef, RawPage
from cerebro.ports.wiki import WikiUnavailable


class FakeApi:
    """Answers each request with the next scripted response or raises it."""

    def __init__(self, *responses: dict[str, Any] | Exception) -> None:
        self.responses = list(responses)
        self.urls: list[str] = []

    def __call__(self, url: str) -> dict[str, Any]:
        self.urls.append(url)
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response

    def params(self, index: int) -> dict[str, str]:
        query = urllib.parse.urlsplit(self.urls[index]).query
        return dict(urllib.parse.parse_qsl(query))


def client(api: FakeApi, sleeps: list[float]) -> FandomClient:
    return FandomClient(get_json=api, sleep=sleeps.append)


def members(*titles: str) -> dict[str, Any]:
    items = [{"pageid": i, "title": t} for i, t in enumerate(titles, 1)]
    return {"query": {"categorymembers": items}}


def test_lists_titles_across_continuation_pages() -> None:
    more = {"cmcontinue": "page|2", "continue": "-||"}
    api = FakeApi({**members("Storm"), "continue": more}, members("Wolverine"))

    refs = list(client(api, []).category_titles("Category:Characters"))

    assert [ref.title for ref in refs] == ["Storm", "Wolverine"]
    assert api.params(1)["cmcontinue"] == "page|2"


def test_fetch_returns_pages_and_leaves_out_missing_ones() -> None:
    revision = {
        "revid": 11231268,
        "timestamp": "2026-10-21T10:43:04Z",
        "slots": {"main": {"content": "{{Marvel Database:Comic Template}}"}},
    }
    pages = [
        {"pageid": 6011, "title": "Amazing Fantasy Vol 1 15", "revisions": [revision]},
        {"pageid": 9999, "title": "Deleted Page", "missing": True},
    ]
    api = FakeApi({"query": {"pages": pages}})

    result = client(api, []).fetch([6011, 9999])

    assert result == [
        RawPage(
            pageid=6011,
            title="Amazing Fantasy Vol 1 15",
            revid=11231268,
            timestamp="2026-10-21T10:43:04Z",
            wikitext="{{Marvel Database:Comic Template}}",
        )
    ]


def test_waits_before_every_request() -> None:
    sleeps: list[float] = []
    api = FakeApi(members("Storm"))

    list(client(api, sleeps).category_titles("Category:Characters"))

    assert sleeps == [DELAY]


def test_retries_after_a_network_error() -> None:
    sleeps: list[float] = []
    api = FakeApi(urllib.error.URLError("connection reset"), members("Storm"))

    refs = list(client(api, sleeps).category_titles("Category:Characters"))

    assert refs == [PageRef(pageid=1, title="Storm")]
    assert len(api.urls) == 2


def test_backs_off_when_the_wiki_reports_maxlag() -> None:
    sleeps: list[float] = []
    lagging = {"error": {"code": "maxlag", "info": "Waiting for a database server"}}
    api = FakeApi(lagging, members("Storm"))

    refs = list(client(api, sleeps).category_titles("Category:Characters"))

    assert refs == [PageRef(pageid=1, title="Storm")]
    assert max(sleeps) > DELAY


def test_gives_up_after_repeated_failures() -> None:
    api = FakeApi(*[urllib.error.URLError("down")] * 6)

    with pytest.raises(WikiUnavailable):
        list(client(api, []).category_titles("Category:Characters"))
