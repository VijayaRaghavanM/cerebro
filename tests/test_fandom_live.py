"""Live check against the Marvel Database API. Run with: uv run pytest -m live"""

import pytest

from cerebro.adapters.fandom import FandomClient

AMAZING_FANTASY_15 = 6011


@pytest.mark.live
def test_fetches_a_known_comic_page() -> None:
    pages = FandomClient().fetch([AMAZING_FANTASY_15])

    assert [page.title for page in pages] == ["Amazing Fantasy Vol 1 15"]
    assert "Marvel Database:Comic Template" in pages[0].wikitext
