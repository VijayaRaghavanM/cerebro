"""Client for the Marvel Database, a MediaWiki wiki hosted on Fandom."""

import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Iterator, Sequence
from typing import Any

from cerebro.domain.pages import Category, PageRef, RawPage
from cerebro.ports.wiki import WikiSource, WikiUnavailable

FANDOM_API = "https://marvel.fandom.com/api.php"
# The wiki files organizations such as the Avengers and Hydra in a category of their
# own, on a template with the team template's fields, so teams come from both.
CATEGORY_TITLES = {
    Category.CHARACTERS: ("Category:Characters",),
    Category.TEAMS: ("Category:Teams", "Category:Organizations"),
    Category.COMICS: ("Category:Comics",),
}

# MediaWiki asks every client to name itself and give a way to reach its owner.
USER_AGENT = "cerebro/0.1 (+https://github.com/VijayaRaghavanM/cerebro)"

DELAY = 1.0  # seconds to wait before every request
ATTEMPTS = 6

log = logging.getLogger(__name__)

JsonGetter = Callable[[str], dict[str, Any]]


def _urllib_get_json(url: str) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=60) as response:
        data: dict[str, Any] = json.load(response)
    return data


class FandomClient(WikiSource):
    """Reads category titles and page content from the Marvel Database API.

    Waits DELAY seconds before every request and backs off when the wiki lags.
    `get_json` and `sleep` can be swapped so tests run without network or waiting.
    """

    batch_limit = 50  # most pages the API returns content for in one request

    def __init__(
        self,
        get_json: JsonGetter = _urllib_get_json,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._get_json = get_json
        self._sleep = sleep

    def category_titles(self, category: Category) -> Iterator[PageRef]:
        # A page can sit in more than one of the wiki categories. Yield it once.
        seen: set[int] = set()
        for wiki_category in CATEGORY_TITLES[category]:
            for ref in self._list_wiki_category(wiki_category):
                if ref.pageid not in seen:
                    seen.add(ref.pageid)
                    yield ref

    def _list_wiki_category(self, wiki_category: str) -> Iterator[PageRef]:
        # "cm" parameters belong to the categorymembers module: main articles only
        # (namespace 0), no subcategories or files, 500 per response (the non-bot max).
        # https://www.mediawiki.org/wiki/API:Categorymembers
        params = {
            "action": "query",
            "list": "categorymembers",
            "cmtitle": wiki_category,
            "cmnamespace": "0",
            "cmtype": "page",
            "cmlimit": "500",
        }

        # Up to 500 members per response, plus a "continue" token while more remain.
        cont: dict[str, str] = {}
        while True:
            data = self._get({**params, **cont})

            for member in data["query"]["categorymembers"]:
                yield PageRef(pageid=member["pageid"], title=member["title"])

            if "continue" not in data:
                return
            cont = data["continue"]

    def fetch(self, pageids: Sequence[int]) -> list[RawPage]:
        """The latest revision of each page. Pass at most `batch_limit` ids."""
        # "rv" parameters belong to the revisions module: revision id, timestamp and
        # wikitext of the main content slot (pages can also hold other slots).
        # https://www.mediawiki.org/wiki/API:Revisions
        params = {
            "action": "query",
            "prop": "revisions",
            "rvprop": "ids|timestamp|content",
            "rvslots": "main",
            "pageids": "|".join(map(str, pageids)),
        }

        # When the content is too large for one response, the API sends the
        # remaining pages in follow-ups, again marked with a "continue" token.
        pages: dict[int, RawPage] = {}
        cont: dict[str, str] = {}
        while True:
            data = self._get({**params, **cont})

            for item in data["query"]["pages"]:
                page = _to_raw_page(item)
                if page is not None:
                    pages.setdefault(page.pageid, page)

            if "continue" not in data:
                return list(pages.values())
            cont = data["continue"]

    def _get(self, params: dict[str, str]) -> dict[str, Any]:
        query = {**params, "format": "json", "formatversion": "2", "maxlag": "5"}
        url = f"{FANDOM_API}?{urllib.parse.urlencode(query)}"

        for attempt in range(ATTEMPTS):
            self._sleep(DELAY)

            try:
                data = self._get_json(url)
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as err:
                wait = 5 * 2**attempt
                log.warning("request failed (%s), retrying in %ds", err, wait)
                self._sleep(wait)
                continue

            # maxlag=5 asks the wiki to refuse requests while its database copies
            # are more than 5 seconds behind. Wait longer each time, then retry.
            if data.get("error", {}).get("code") == "maxlag":
                self._sleep(10 * (attempt + 1))
                continue

            return data

        raise WikiUnavailable(f"Marvel Database API failed {ATTEMPTS} times in a row")


def _to_raw_page(item: dict[str, Any]) -> RawPage | None:
    """One page from a revisions response, or None if the page no longer exists."""
    revisions = item.get("revisions")
    if not revisions:
        return None

    revision = revisions[0]
    return RawPage(
        pageid=item["pageid"],
        title=item["title"],
        revid=revision["revid"],
        timestamp=revision["timestamp"],
        wikitext=revision["slots"]["main"]["content"],
    )
