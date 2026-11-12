import logging
import urllib.error
import urllib.parse
from email.message import Message
from typing import Any

import pytest
from pydantic import SecretStr

from cerebro.adapters.comicvine_api import DELAY, ComicVineClient
from cerebro.ports.comicvine import ComicVineUnavailable

KEY = "k3y-not-for-logs"


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


def client(api: FakeApi, sleeps: list[float]) -> ComicVineClient:
    return ComicVineClient(SecretStr(KEY), get_json=api, sleep=sleeps.append)


def reply(results: Any) -> dict[str, Any]:
    return {"status_code": 1, "error": "OK", "results": results}


def http_error(code: int) -> urllib.error.HTTPError:
    url = "https://example.test"
    return urllib.error.HTTPError(url, code, "error", Message(), None)


def test_batches_put_the_ids_and_fields_in_the_query() -> None:
    api = FakeApi(reply([{"id": 1}, {"id": 2}]))

    rows = client(api, []).character_summaries([1, 2])

    assert rows == [{"id": 1}, {"id": 2}]
    assert api.urls[0].startswith("https://comicvine.gamespot.com/api/characters/?")
    params = api.params(0)
    assert params["filter"] == "id:1|2"
    assert params["limit"] == "100"
    assert params["field_list"].startswith("id,name,real_name,aliases,")
    assert params["api_key"] == KEY


def test_marvel_characters_keep_only_id_and_name() -> None:
    characters = [{"id": 1, "name": "Storm", "api_detail_url": "https://x.test/1"}]
    api = FakeApi(reply({"characters": characters}))

    rows = client(api, []).marvel_characters()

    assert rows == [{"id": 1, "name": "Storm"}]
    assert "/publisher/4010-31/" in api.urls[0]
    assert api.params(0)["field_list"] == "characters"


def test_detail_turns_issue_credits_into_issue_ids_and_slims_links() -> None:
    detail = {
        "id": 1442,
        "name": "Storm",
        "birth": "1975",
        "issue_credits": [{"id": 10, "name": "Giant-Size X-Men"}, {"id": 11}],
        "teams": [
            {
                "id": 3,
                "name": "X-Men",
                "api_detail_url": "https://x.test/api/3",
                "site_detail_url": "https://x.test/3",
            }
        ],
        "first_appeared_in_issue": {
            "id": 10,
            "name": "Giant-Size X-Men",
            "issue_number": "1",
            "api_detail_url": "https://x.test/api/10",
        },
    }
    api = FakeApi(reply(detail))

    row = client(api, []).character_detail(1442)

    assert "/character/4005-1442/" in api.urls[0]
    assert row == {
        "id": 1442,
        "name": "Storm",
        "issue_ids": [10, 11],
        "birth": "1975",
        "teams": [{"id": 3, "name": "X-Men", "site_detail_url": "https://x.test/3"}],
        "first_appeared_in_issue": {
            "id": 10,
            "name": "Giant-Size X-Men",
            "issue_number": "1",
        },
    }
    assert list(row)[:3] == ["id", "name", "issue_ids"]


def test_detail_without_issue_credits_has_no_issue_ids() -> None:
    api = FakeApi(reply({"id": 7, "name": "Nobody", "issue_credits": None}))

    row = client(api, []).character_detail(7)

    assert row["issue_ids"] == []


def test_issues_keep_only_the_volume_id_and_name() -> None:
    volume = {"id": 5, "name": "X-Men", "api_detail_url": "https://x.test/api/5"}
    api = FakeApi(reply([{"id": 10, "issue_number": "1", "volume": volume}]))

    rows = client(api, []).issues([10])

    assert rows == [
        {"id": 10, "issue_number": "1", "volume": {"id": 5, "name": "X-Men"}}
    ]
    assert api.params(0)["filter"] == "id:10"


def test_waits_before_every_request() -> None:
    sleeps: list[float] = []
    api = FakeApi(reply([]), reply([]))
    comicvine = client(api, sleeps)

    comicvine.issues([1])
    comicvine.issues([2])

    assert sleeps == [DELAY, DELAY]


def test_retries_a_429_after_a_longer_wait_each_time() -> None:
    sleeps: list[float] = []
    api = FakeApi(http_error(429), http_error(420), reply([{"id": 1}]))

    rows = client(api, sleeps).character_summaries([1])

    assert rows == [{"id": 1}]
    assert sleeps == [DELAY, 60, DELAY, 120, DELAY]


def test_retries_after_rate_limit_status_waits_fifteen_minutes() -> None:
    sleeps: list[float] = []
    limited = {"status_code": 107, "error": "Rate limit exceeded", "results": []}
    api = FakeApi(limited, reply([{"id": 1}]))

    rows = client(api, sleeps).character_summaries([1])

    assert rows == [{"id": 1}]
    assert sleeps == [DELAY, 900, DELAY]


def test_backs_off_after_a_network_error() -> None:
    sleeps: list[float] = []
    api = FakeApi(
        urllib.error.URLError("no route"),
        ConnectionResetError("dropped"),
        http_error(500),
        reply([]),
    )

    client(api, sleeps).issues([1])

    assert sleeps == [DELAY, 10, DELAY, 20, DELAY, 40, DELAY]


def test_other_statuses_are_refused() -> None:
    bad = {"status_code": 100, "error": "Invalid API Key", "results": []}
    api = FakeApi(bad)

    with pytest.raises(ComicVineUnavailable, match="status 100 Invalid API Key"):
        client(api, []).issues([1])

    assert len(api.urls) == 1


def test_gives_up_without_leaking_the_key(caplog: pytest.LogCaptureFixture) -> None:
    api = FakeApi(*[urllib.error.URLError(f"down {KEY}")] * 6)

    with caplog.at_level(logging.DEBUG), pytest.raises(ComicVineUnavailable) as raised:
        client(api, []).character_detail(1442)

    assert "character/4005-1442" in str(raised.value)
    assert KEY not in str(raised.value)
    assert caplog.records
    assert all(KEY not in record.getMessage() for record in caplog.records)
    assert "http" not in caplog.text
