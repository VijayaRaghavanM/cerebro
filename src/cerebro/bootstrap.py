"""The only place that picks concrete classes and wires them together."""

from cerebro.adapters.comicvine_dump import ComicVineDump
from cerebro.adapters.fandom import FandomClient
from cerebro.adapters.fandom_records import FandomRecordParser
from cerebro.adapters.jsonl_pages import JsonlPageStore
from cerebro.adapters.sqlite_records import SqliteRecordStore
from cerebro.application import matching
from cerebro.application.crawl import CrawlReport, Progress, crawl
from cerebro.application.parse import ParseReport, parse
from cerebro.application.parse import Progress as ParseProgress
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


def parse_fandom(
    category: Category, *, progress: ParseProgress | None = None
) -> ParseReport:
    """Parse one category's saved Marvel Database pages into DATA_DIR/records.sqlite."""
    data_dir = Settings().data_dir
    pages = JsonlPageStore(data_dir / "raw" / "fandom")
    store = SqliteRecordStore(data_dir / "records.sqlite")

    return parse(
        pages, FandomRecordParser(category), store, category, progress=progress
    )


def match_comicvine() -> matching.MatchReport:
    """Match Comic Vine's characters in DATA_DIR/raw/comicvine/ to the stored ones."""
    data_dir = Settings().data_dir
    store = SqliteRecordStore(data_dir / "records.sqlite")
    comicvine = ComicVineDump(data_dir / "raw" / "comicvine")

    return matching.match_comicvine(store, comicvine, store)
