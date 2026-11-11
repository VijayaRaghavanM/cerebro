"""The only place that picks concrete classes and wires them together."""

from collections.abc import Callable

from cerebro.adapters.comicvine_dump import ComicVineDump
from cerebro.adapters.fandom import FandomClient
from cerebro.adapters.fandom_records import FandomRecordParser
from cerebro.adapters.jsonl_pages import JsonlPageStore
from cerebro.adapters.langgraph_agent import LangGraphAgent
from cerebro.adapters.mistral import ministral
from cerebro.adapters.numpy_vectors import NumpyVectorStore
from cerebro.adapters.ollama import OllamaEmbedder
from cerebro.adapters.sqlite_chunks import SqliteChunkIndex
from cerebro.adapters.sqlite_records import SqliteRecordStore
from cerebro.application import chunking, embedding, loading, matching
from cerebro.application.crawl import CrawlReport, Progress, crawl
from cerebro.application.embedding import EmbedReport
from cerebro.application.parse import ParseReport, parse
from cerebro.application.parse import Progress as ParseProgress
from cerebro.domain.answers import Answer
from cerebro.domain.pages import Category
from cerebro.settings import Settings

# The chunks share the records' file, so a search and the agent's tools read one file.
RECORDS_FILE = "records.sqlite"


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
    pages = JsonlPageStore(Settings().data_dir / "raw" / "fandom")

    return parse(
        pages, FandomRecordParser(category), _records(), category, progress=progress
    )


def load_comicvine() -> loading.LoadReport:
    """Store Comic Vine's characters in DATA_DIR/raw/comicvine/ in the record store."""
    comicvine = ComicVineDump(Settings().data_dir / "raw" / "comicvine")

    return loading.load_comicvine(comicvine, _records())


def match_comicvine() -> matching.MatchReport:
    """Match Comic Vine's characters in DATA_DIR/raw/comicvine/ to the stored ones."""
    comicvine = ComicVineDump(Settings().data_dir / "raw" / "comicvine")
    store = _records()

    return matching.match_comicvine(store, comicvine, store)


def chunk_records() -> chunking.ChunkReport:
    """Cut the stored character pages into chunks in DATA_DIR/records.sqlite."""
    return chunking.chunk_records(_records(), _chunks())


def embed_chunks(progress: Callable[[int, int], None] | None = None) -> EmbedReport:
    """Embed the stored chunks on the Ollama server into DATA_DIR/embeddings/text/."""
    settings = Settings()
    if settings.ollama_base_url is None:
        raise MissingKey("OLLAMA_BASE_URL")

    embedder = OllamaEmbedder(settings.ollama_base_url)
    store = NumpyVectorStore(settings.data_dir / "embeddings" / "text")

    return embedding.embed_chunks(_chunks(), embedder, store, progress=progress)


def ask(question: str) -> Answer:
    """Answer a question from DATA_DIR/records.sqlite with Mistral's model."""
    settings = Settings()
    if settings.mistral_api_key is None:
        raise MissingKey("MISTRAL_API_KEY")

    model = ministral(settings.mistral_api_key)

    return LangGraphAgent(model, _records()).answer(question)


def _records() -> SqliteRecordStore:
    return SqliteRecordStore(Settings().data_dir / RECORDS_FILE)


def _chunks() -> SqliteChunkIndex:
    return SqliteChunkIndex(Settings().data_dir / RECORDS_FILE)
