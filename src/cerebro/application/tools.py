"""The agent's tools: search pages by name, search their text, read one, and list the
comics a page appears in."""

from dataclasses import dataclass, fields
from typing import TYPE_CHECKING

from cerebro.domain.answers import Source
from cerebro.domain.comicvine import ComicVineCharacter, ComicVineIssue
from cerebro.domain.pages import Category
from cerebro.domain.records import Character, Comic, Team
from cerebro.ports.chunks import ChunkSearch
from cerebro.ports.records import RecordLookup

if TYPE_CHECKING:
    from _typeshed import DataclassInstance

# A search lists few enough pages for the model to read them all.
SEARCH_LIMIT = 10
# Five passages keep a reply near 2,500 tokens.
TEXT_LIMIT = 5
# Twenty comics keep a reply short.
APPEARANCE_LIMIT = 20
# One read stays within a few thousand tokens.
FIELD_LIMIT = 1500
PAGE_LIMIT = 12000
CUT = " [cut]"

SEARCH_KINDS = {
    Category.CHARACTERS: "character",
    Category.TEAMS: "team",
    Category.COMICS: "comic",
}
READ_KINDS: dict[type, str] = {Character: "character", Team: "team", Comic: "comic"}
# Shown in the header, or read in a block of their own.
NOT_FIELDS = {"pageid", "revid", "title", "categories", "links", "stories"}
# A story's cast comes before its synopsis; its other fields are not for the model.
STORY_FIELDS = ("appearing", "synopsis")


@dataclass(frozen=True)
class ToolResult:
    """What the model reads, and the pages it may cite for it."""

    text: str
    sources: tuple[Source, ...]


def search_pages(lookup: RecordLookup, name: str) -> ToolResult:
    hits = lookup.find(name, SEARCH_LIMIT)
    if not hits:
        return ToolResult(f'No pages match "{name}".', ())

    lines = []
    for number, hit in enumerate(hits, start=1):
        kind = SEARCH_KINDS[hit.category]
        # Quoted, so the model passes the exact title on: titles can contain colons.
        line = f'{number}. "{hit.title}": {kind}'
        if hit.category != Category.COMICS:
            line += f", in {hit.appearances:,} comics' cast lists"
        lines.append(line)

    # A search result is not evidence, so it cites nothing.
    return ToolResult("\n".join(lines), ())


def read_page(lookup: RecordLookup, title: str) -> ToolResult:
    record = lookup.record(title)
    if record is None:
        return ToolResult(f'No page is titled "{title}". Search for it first.', ())

    blocks = ["\n".join([f"{title} ({READ_KINDS[type(record)]})", *_lines(record)])]
    if isinstance(record, Comic):
        blocks += _stories(record)
    # Only the page's own text is cut to the page limit, so the Comic Vine block
    # always reaches the model whenever its source is listed.
    text = _cut("\n\n".join(blocks), PAGE_LIMIT)
    sources = [Source(title, lookup.url(title))]

    if isinstance(record, Character):
        character = lookup.comicvine(record.pageid)
        if character is not None:
            text += "\n\n" + _comicvine_block(character)
            sources.append(Source(f"Comic Vine: {character.name}", character.url))

    return ToolResult(text, tuple(sources))


def find_appearances(lookup: RecordLookup, title: str) -> ToolResult:
    appearances = lookup.appearances(title, APPEARANCE_LIMIT)
    if not appearances.total:
        return ToolResult(f'No comic\'s cast list names "{title}".', ())

    shown = len(appearances.first)
    lines = [
        f"{title} appears in {appearances.total:,} comics' cast lists;"
        f" the first {shown} by cover date:"
    ]
    for comic in appearances.first:
        lines.append(f"{comic.title} ({comic.date or 'no date'})")

    return ToolResult("\n".join(lines), (Source(title, lookup.url(title)),))


def search_text(chunks: ChunkSearch, lookup: RecordLookup, query: str) -> ToolResult:
    hits = chunks.search(query, TEXT_LIMIT)
    if not hits:
        return ToolResult(f'No passages match "{query}".', ())

    passages = []
    sources: dict[Source, None] = {}
    for hit in hits:
        chunk = hit.chunk
        passages.append(f"{chunk.title}, {chunk.section}\n{chunk.text}")
        # Each page is cited once, however many of its passages were found.
        sources[Source(chunk.title, lookup.url(chunk.title))] = None

    return ToolResult("\n\n".join(passages), tuple(sources))


def _lines(item: "DataclassInstance", skip: set[str] = NOT_FIELDS) -> list[str]:
    """One `field: value` line for each field with something in it."""
    lines = []
    for field in fields(item):
        value = getattr(item, field.name)
        if field.name in skip or not value:
            continue

        lines.append(_line(field.name, value))

    return lines


def _line(name: str, value: object) -> str:
    return f"{name.replace('_', ' ')}: {_cut(_show(value), FIELD_LIMIT)}"


def _show(value: object) -> str:
    if isinstance(value, tuple):
        return ", ".join(_show(item) for item in value)
    if isinstance(value, ComicVineIssue):
        dated = f" ({value.cover_date})" if value.cover_date else ""
        return f"{value.series} #{value.number}{dated}"
    return str(value)


def _stories(comic: Comic) -> list[str]:
    blocks = []
    for story in comic.stories:
        lines = _lines(story.credits, skip=set())
        for name in STORY_FIELDS:
            if value := getattr(story, name):
                lines.append(_line(name, value))

        heading = f"Story {story.number}"
        if story.title:
            heading += f": {story.title}"
        blocks.append("\n".join([heading, *lines]))

    return blocks


def _comicvine_block(character: ComicVineCharacter) -> str:
    lines = ["Comic Vine:", f"name: {character.name}"]
    if character.real_name:
        lines.append(f"real name: {character.real_name}")
    lines.append(f"appearances: {character.appearances}")
    if character.detail is not None:
        lines += _lines(character.detail, skip={"issues"})

    return "\n".join(lines)


def _cut(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text

    return text[:limit] + CUT
