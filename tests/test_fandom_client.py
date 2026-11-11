import urllib.error
import urllib.parse
from typing import Any

import pytest

from cerebro.adapters.fandom import DELAY, FandomClient
from cerebro.domain.pages import Category, PageRef, RawPage
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


def members(*pages: tuple[int, str]) -> dict[str, Any]:
    """One listing response, from (page id, title) pairs."""
    items = [{"pageid": pageid, "title": title} for pageid, title in pages]
    return {"query": {"categorymembers": items}}


def test_lists_titles_across_continuation_pages() -> None:
    more = {"cmcontinue": "page|2", "continue": "-||"}
    api = FakeApi(
        {**members((1, "Storm")), "continue": more},
        members((2, "Wolverine")),
    )

    refs = list(client(api, []).category_titles(Category.CHARACTERS))

    assert [ref.title for ref in refs] == ["Storm", "Wolverine"]
    assert api.params(0)["cmtitle"] == "Category:Characters"
    assert api.params(1)["cmcontinue"] == "page|2"


def test_teams_list_both_wiki_categories_in_order() -> None:
    api = FakeApi(
        members((1, "X-Men")),
        members((2, "Avengers"), (3, "Hydra")),
    )

    refs = list(client(api, []).category_titles(Category.TEAMS))

    assert [ref.title for ref in refs] == ["X-Men", "Avengers", "Hydra"]
    assert api.params(0)["cmtitle"] == "Category:Teams"
    assert api.params(1)["cmtitle"] == "Category:Organizations"


def test_a_page_in_both_wiki_categories_is_listed_once() -> None:
    api = FakeApi(
        members((1, "X-Men"), (2, "Avengers")),
        members((2, "Avengers"), (3, "Hydra")),
    )

    refs = list(client(api, []).category_titles(Category.TEAMS))

    assert [ref.pageid for ref in refs] == [1, 2, 3]


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
    api = FakeApi(members((1, "Storm")))

    list(client(api, sleeps).category_titles(Category.CHARACTERS))

    assert sleeps == [DELAY]


def test_retries_after_a_network_error() -> None:
    sleeps: list[float] = []
    api = FakeApi(urllib.error.URLError("connection reset"), members((1, "Storm")))

    refs = list(client(api, sleeps).category_titles(Category.CHARACTERS))

    assert refs == [PageRef(pageid=1, title="Storm")]
    assert len(api.urls) == 2


def test_backs_off_when_the_wiki_reports_maxlag() -> None:
    sleeps: list[float] = []
    lagging = {"error": {"code": "maxlag", "info": "Waiting for a database server"}}
    api = FakeApi(lagging, members((1, "Storm")))

    refs = list(client(api, sleeps).category_titles(Category.CHARACTERS))

    assert refs == [PageRef(pageid=1, title="Storm")]
    assert max(sleeps) > DELAY


def test_gives_up_after_repeated_failures() -> None:
    api = FakeApi(*[urllib.error.URLError("down")] * 6)

    with pytest.raises(WikiUnavailable):
        list(client(api, []).category_titles(Category.CHARACTERS))
