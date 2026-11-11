"""The only place that picks concrete classes and wires them together."""

from cerebro.adapters.comicvine_dump import ComicVineDump
from cerebro.adapters.fandom import FandomClient
from cerebro.adapters.fandom_records import FandomRecordParser
from cerebro.adapters.jsonl_pages import JsonlPageStore
from cerebro.adapters.langgraph_agent import LangGraphAgent
from cerebro.adapters.mistral import ministral
from cerebro.adapters.sqlite_records import SqliteRecordStore
from cerebro.application import chunking, loading, matching
from cerebro.application.crawl import CrawlReport, Progress, crawl
from cerebro.application.parse import ParseReport, parse
from cerebro.application.parse import Progress as ParseProgress
from cerebro.domain.answers import Answer
from cerebro.domain.pages import Category
from cerebro.settings import Settings


class MissingKey(Exception):
    """An API key the command needs is not set. The message is the variable's name."""


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


def load_comicvine() -> loading.LoadReport:
    """Store Comic Vine's characters in DATA_DIR/raw/comicvine/ in the record store."""
    data_dir = Settings().data_dir
    store = SqliteRecordStore(data_dir / "records.sqlite")
    comicvine = ComicVineDump(data_dir / "raw" / "comicvine")

    return loading.load_comicvine(comicvine, store)


def match_comicvine() -> matching.MatchReport:
    """Match Comic Vine's characters in DATA_DIR/raw/comicvine/ to the stored ones."""
    data_dir = Settings().data_dir
    store = SqliteRecordStore(data_dir / "records.sqlite")
    comicvine = ComicVineDump(data_dir / "raw" / "comicvine")

    return matching.match_comicvine(store, comicvine, store)


def chunk_records() -> chunking.ChunkReport:
    """Cut the stored character pages into chunks in DATA_DIR/records.sqlite."""
    store = SqliteRecordStore(Settings().data_dir / "records.sqlite")

    return chunking.chunk_records(store, store)


def ask(question: str) -> Answer:
    """Answer a question from DATA_DIR/records.sqlite with Mistral's model."""
    settings = Settings()
    if settings.mistral_api_key is None:
        raise MissingKey("MISTRAL_API_KEY")

    store = SqliteRecordStore(settings.data_dir / "records.sqlite")
    model = ministral(settings.mistral_api_key)

    return LangGraphAgent(model, store).answer(question)
