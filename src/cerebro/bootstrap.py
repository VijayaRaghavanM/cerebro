"""The only place that picks concrete classes and wires them together."""

from collections.abc import Callable, Iterator
from enum import StrEnum

from langchain_core.language_models import BaseChatModel

from cerebro.adapters.comicvine_api import ComicVineClient
from cerebro.adapters.comicvine_dump import ComicVineDump
from cerebro.adapters.fandom import FandomClient
from cerebro.adapters.fandom_records import FandomRecordParser
from cerebro.adapters.jsonl_pages import JsonlPageStore
from cerebro.adapters.langgraph_agent import LangGraphAgent
from cerebro.adapters.mistral import ministral
from cerebro.adapters.numpy_vectors import NumpyVectorStore
from cerebro.adapters.ollama import OllamaEmbedder
from cerebro.adapters.openai_chat import openai_chat
from cerebro.adapters.sqlite_chunks import SqliteChunkIndex
from cerebro.adapters.sqlite_comicvine import SqliteComicVineStore
from cerebro.adapters.sqlite_records import SqliteRecordStore
from cerebro.application import chunking, crawl, embedding, loading, matching, parse
from cerebro.application import crawl_comicvine as comicvine_crawl
from cerebro.domain.answers import Step
from cerebro.domain.pages import Category
from cerebro.settings import Settings

# The chunks share the records' file, so a search and the agent's tools read one file.
RECORDS_FILE = "records.sqlite"


OPENROUTER_URL = "https://openrouter.ai/api/v1"


class Contestant(StrEnum):
    """The models `ask` can run on. The values are what `--model` accepts."""

    MINISTRAL_14B = "ministral-14b"
    MINISTRAL_14B_OPENROUTER = "ministral-14b-openrouter"
    MINISTRAL_3B_OPENROUTER = "ministral-3b-openrouter"
    QWEN3_14B_OLLAMA = "qwen3-14b-ollama"
    GEMINI_FLASH_OPENROUTER = "gemini-3.8-flash-openrouter"


class MissingKey(Exception):
    """An API key the command needs is not set. The message is the variable's name."""


def crawl_fandom(
    category: Category,
    *,
    limit: int | None = None,
    progress: crawl.Progress | None = None,
) -> crawl.CrawlReport:
    """Crawl one Marvel Database category into DATA_DIR/raw/fandom/."""
    return crawl.crawl(
        FandomClient(), _pages(), category, limit=limit, progress=progress
    )


def crawl_comicvine(
    *,
    top: int,
    max_calls: int | None = None,
    progress: comicvine_crawl.Progress | None = None,
) -> comicvine_crawl.ComicVineCrawlReport:
    """Crawl Comic Vine's Marvel characters into DATA_DIR/raw/comicvine/."""
    key = Settings().comicvine_api_key
    if key is None:
        raise MissingKey("COMICVINE_API_KEY")

    return comicvine_crawl.crawl_comicvine(
        ComicVineClient(key),
        _comicvine_dump(),
        top=top,
        max_calls=max_calls,
        progress=progress,
    )


def parse_fandom(
    category: Category, *, progress: parse.Progress | None = None
) -> parse.ParseReport:
    """Parse one category's saved Marvel Database pages into DATA_DIR/records.sqlite."""
    return parse.parse(
        _pages(), FandomRecordParser(category), _records(), category, progress=progress
    )


def load_comicvine() -> loading.LoadReport:
    """Store Comic Vine's characters in DATA_DIR/raw/comicvine/ in the record store."""
    return loading.load_comicvine(_comicvine_dump(), _comicvine())


def match_comicvine() -> matching.MatchReport:
    """Match Comic Vine's characters in DATA_DIR/raw/comicvine/ to the stored ones."""
    return matching.match_comicvine(_records(), _comicvine_dump(), _comicvine())


def chunk_records() -> chunking.ChunkReport:
    """Cut the stored character pages into chunks in DATA_DIR/records.sqlite."""
    return chunking.chunk_records(_records(), _chunks())


def embed_chunks(progress: embedding.Progress | None = None) -> embedding.EmbedReport:
    """Embed the stored chunks on the Ollama server into DATA_DIR/embeddings/text/."""
    settings = Settings()
    if settings.ollama_base_url is None:
        raise MissingKey("OLLAMA_BASE_URL")

    embedder = OllamaEmbedder(settings.ollama_base_url)
    store = NumpyVectorStore(settings.data_dir / "embeddings" / "text")

    return embedding.embed_chunks(_chunks(), embedder, store, progress=progress)


def ask(question: str, model: Contestant = Contestant.MINISTRAL_14B) -> Iterator[Step]:
    """Answer a question from DATA_DIR/records.sqlite with the chosen model.

    Returns the agent's steps, ending with the answer. The key is checked here, not
    on the first step, so a missing key fails before any step is read.
    """
    return LangGraphAgent(chat_model(model), _records(), _chunks()).steps(question)


def chat_model(contestant: Contestant) -> BaseChatModel:
    """The contestant's model. Raises MissingKey if its key or server is not set."""
    return _CONTESTANTS[contestant](Settings())


# Each contestant's builder takes the settings and raises MissingKey for what it lacks.
def _mistral(settings: Settings) -> BaseChatModel:
    if settings.mistral_api_key is None:
        raise MissingKey("MISTRAL_API_KEY")

    return ministral(settings.mistral_api_key)


def _openrouter(
    model: str, *, pin_to: str | None = None
) -> Callable[[Settings], BaseChatModel]:
    """A builder for one OpenRouter model, optionally served only by one provider."""

    def build(settings: Settings) -> BaseChatModel:
        if settings.openrouter_api_key is None:
            raise MissingKey("OPENROUTER_API_KEY")

        # Without the pin, OpenRouter may route to a provider that quantizes the model.
        extra_body = None
        if pin_to is not None:
            extra_body = {"provider": {"order": [pin_to], "allow_fallbacks": False}}

        return openai_chat(
            OPENROUTER_URL,
            model,
            api_key=settings.openrouter_api_key,
            extra_body=extra_body,
        )

    return build


def _ollama(model: str) -> Callable[[Settings], BaseChatModel]:
    def build(settings: Settings) -> BaseChatModel:
        if settings.ollama_base_url is None:
            raise MissingKey("OLLAMA_BASE_URL")

        return openai_chat(f"{settings.ollama_base_url.rstrip('/')}/v1", model)

    return build


_CONTESTANTS: dict[Contestant, Callable[[Settings], BaseChatModel]] = {
    Contestant.MINISTRAL_14B: _mistral,
    Contestant.MINISTRAL_14B_OPENROUTER: _openrouter(
        "mistralai/ministral-14b-2512", pin_to="Mistral"
    ),
    Contestant.MINISTRAL_3B_OPENROUTER: _openrouter(
        "mistralai/ministral-3b-2512", pin_to="Mistral"
    ),
    Contestant.QWEN3_14B_OLLAMA: _ollama("qwen3:14b"),
    Contestant.GEMINI_FLASH_OPENROUTER: _openrouter("google/gemini-3.8-flash"),
}


def _pages() -> JsonlPageStore:
    return JsonlPageStore(Settings().data_dir / "raw" / "fandom")


def _comicvine_dump() -> ComicVineDump:
    return ComicVineDump(Settings().data_dir / "raw" / "comicvine")


def _records() -> SqliteRecordStore:
    return SqliteRecordStore(Settings().data_dir / RECORDS_FILE)


def _comicvine() -> SqliteComicVineStore:
    return SqliteComicVineStore(Settings().data_dir / RECORDS_FILE)


def _chunks() -> SqliteChunkIndex:
    return SqliteChunkIndex(Settings().data_dir / RECORDS_FILE)
