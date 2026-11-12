"""Client for the Comic Vine API."""

import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Sequence
from typing import Any

from pydantic import SecretStr

from cerebro.domain.comicvine import RawRecord
from cerebro.ports.comicvine import ComicVineAPI, ComicVineUnavailable

COMICVINE_API = "https://comicvine.gamespot.com/api"
MARVEL_PUBLISHER = "4010-31"

# Comic Vine asks every client to name itself.
USER_AGENT = "cerebro/0.1 (+https://github.com/VijayaRaghavanM/cerebro)"

# Comic Vine allows about 200 calls an hour per resource. One call every 18.5 seconds
# makes about 195, just under it.
DELAY = 18.5
ATTEMPTS = 6
BATCH_LIMIT = 100  # most records the API returns in one request
OVERLOADED = (420, 429)  # HTTP codes Comic Vine answers with when it is overloaded
OVERLOADED_WAIT = 60  # seconds, times the attempt number
RATE_LIMITED = 107  # the status_code in the JSON when the hourly limit is hit
RATE_LIMIT_WAIT = 15 * 60  # seconds
SUCCESS = 1

SUMMARY_FIELDS = (
    "id,name,real_name,aliases,count_of_issue_appearances,"
    "first_appeared_in_issue,site_detail_url"
)
# Everything useful from a character's detail record. Left out: the description
# (long HTML) and images.
DETAIL_FIELDS = (
    "id,name,real_name,aliases,birth,gender,origin,deck,count_of_issue_appearances,"
    "first_appeared_in_issue,issues_died_in,creators,powers,teams,team_friends,"
    "team_enemies,character_friends,character_enemies,story_arc_credits,"
    "volume_credits,movies,date_last_updated,site_detail_url,issue_credits"
)
ISSUE_FIELDS = "id,name,issue_number,cover_date,store_date,volume,site_detail_url"
LINK_KEYS = ("id", "name", "issue_number", "site_detail_url")

log = logging.getLogger(__name__)

JsonGetter = Callable[[str], dict[str, Any]]


def _urllib_get_json(url: str) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=60) as response:
        data: dict[str, Any] = json.load(response)
    return data


class ComicVineClient(ComicVineAPI):
    """Reads Marvel characters and issues from the Comic Vine API.

    Waits DELAY seconds before every request and backs off when Comic Vine fails or
    limits the rate. `get_json` and `sleep` can be swapped so tests run without
    network or waiting. The key rides in each request's URL, so nothing here puts a
    URL in a log line or an error.
    """

    batch_limit = BATCH_LIMIT

    def __init__(
        self,
        api_key: SecretStr,
        get_json: JsonGetter = _urllib_get_json,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._api_key = api_key
        self._get_json = get_json
        self._sleep = sleep

    def marvel_characters(self) -> list[RawRecord]:
        data = self._get(f"publisher/{MARVEL_PUBLISHER}", {"field_list": "characters"})

        return [
            {"id": character["id"], "name": character["name"]}
            for character in data["results"]["characters"]
        ]

    def character_summaries(self, ids: Sequence[int]) -> list[RawRecord]:
        params = {"field_list": SUMMARY_FIELDS, **_batch_params(ids)}
        data = self._get("characters", params)

        results: list[RawRecord] = data["results"]
        return results

    def character_detail(self, character_id: int) -> RawRecord:
        data = self._get(
            f"character/4005-{character_id}", {"field_list": DETAIL_FIELDS}
        )

        result: RawRecord = data["results"]
        credits = result.pop("issue_credits", None) or []

        # The id and name come first, then the issues, then the rest.
        record: RawRecord = {
            "id": result["id"],
            "name": result["name"],
            "issue_ids": [credit["id"] for credit in credits],
        }
        for key, value in result.items():
            if isinstance(value, list):
                record[key] = [_slim(item) for item in value]
            else:
                record[key] = _slim(value)
        return record

    def issues(self, ids: Sequence[int]) -> list[RawRecord]:
        params = {"field_list": ISSUE_FIELDS, **_batch_params(ids)}
        data = self._get("issues", params)

        issues: list[RawRecord] = data["results"]
        for issue in issues:
            volume = issue.get("volume") or {}
            issue["volume"] = {"id": volume.get("id"), "name": volume.get("name")}
        return issues

    def _get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        query = {
            **params,
            "api_key": self._api_key.get_secret_value(),
            "format": "json",
        }
        url = f"{COMICVINE_API}/{path}/?{urllib.parse.urlencode(query)}"

        for attempt in range(ATTEMPTS):
            self._sleep(DELAY)

            try:
                data = self._get_json(url)
            # OSError covers HTTP errors, timeouts and dropped connections alike.
            except (OSError, json.JSONDecodeError) as err:
                wait = _error_wait(err, attempt)
                log.warning("%s on %s, retrying in %ds", type(err).__name__, path, wait)
                self._sleep(wait)
                continue

            status = data.get("status_code")
            if status == SUCCESS:
                return data

            if status == RATE_LIMITED:
                log.warning(
                    "rate limited on %s, retrying in %ds", path, RATE_LIMIT_WAIT
                )
                self._sleep(RATE_LIMIT_WAIT)
                continue

            raise ComicVineUnavailable(f"{path}: status {status} {data.get('error')}")

        raise ComicVineUnavailable(f"Comic Vine failed {ATTEMPTS} times on {path}")


def _batch_params(ids: Sequence[int]) -> dict[str, Any]:
    return {"filter": "id:" + "|".join(map(str, ids)), "limit": BATCH_LIMIT}


def _error_wait(err: Exception, attempt: int) -> int:
    """Seconds to wait before retrying: longer when Comic Vine says it is overloaded."""
    if isinstance(err, urllib.error.HTTPError) and err.code in OVERLOADED:
        return OVERLOADED_WAIT * (attempt + 1)
    return 10 * (1 << attempt)  # doubles each attempt


def _slim(value: Any) -> Any:
    """A linked record cut to its id, name, issue number and page url, no API url."""
    if isinstance(value, dict):
        return {key: value[key] for key in LINK_KEYS if key in value}
    return value
