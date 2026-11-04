"""The only place that picks concrete classes and wires them together."""

from cerebro.adapters.fandom import FandomClient
from cerebro.adapters.jsonl_pages import JsonlPageStore
from cerebro.application.crawl import CrawlReport, Progress, crawl
from cerebro.domain.pages import Category
from cerebro.settings import Settings


def crawl_fandom(
    category: Category,
    *,
    limit: int | None = None,
    progress: Progress | None = None,
) -> CrawlReport:
    """Crawl one Marvel Database category into DATA_DIR/raw/fandom/."""
    store = JsonlPageStore(Settings().data_dir / "raw" / "fandom")

    return crawl(FandomClient(), store, category, limit=limit, progress=progress)
