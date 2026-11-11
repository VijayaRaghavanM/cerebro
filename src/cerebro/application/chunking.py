"""Cut a character page into chunks a search can rank and an answer can cite."""

import re
from collections.abc import Iterator
from dataclasses import dataclass, fields

from cerebro.domain.chunks import Chunk
from cerebro.domain.records import Character
from cerebro.ports.chunks import ChunkStore
from cerebro.ports.records import RecordReader

# The prose fields, in the order a page reads them.
PROSE_FIELDS = (
    "overview",
    "history",
    "personality",
    "powers",
    "abilities",
    "weaknesses",
    "equipment",
    "transportation",
    "weapons",
    "notes",
    "trivia",
)

# Fields that identify the page or list its links; a search gains nothing from them.
PAGE_FURNITURE = ("pageid", "revid", "title", "categories", "links")

# A chunk's size goal. The plan's figure: big enough to hold one idea whole,
# small enough that several fit in a model's prompt.
TARGET_TOKENS = 450

# A common rule of thumb for English, so no tokenizer is needed.
CHARS_PER_TOKEN = 4

HEADING = re.compile(r"^#+\s+(?P<text>.+?)\s*$")
PARAGRAPH_BREAK = re.compile(r"\n\s*\n")
SENTENCE_END = re.compile(r"(?<=[.!?]) +(?=[A-Z\"'])")


@dataclass(frozen=True)
class ChunkReport:
    pages: int
    chunks: int


def chunk_records(records: RecordReader, store: ChunkStore) -> ChunkReport:
    """Replace the stored chunks with the stored characters' chunks.

    Chunks stream through one at a time, so they are never held in memory whole.
    """
    # Asked for here, not inside the stream, so missing records fail before the
    # store opens anything to write.
    characters = records.characters()
    pages = chunks = 0

    def stream() -> Iterator[Chunk]:
        nonlocal pages, chunks
        for character in characters:
            pages += 1
            for chunk in chunk_character(character):
                chunks += 1
                yield chunk

    store.replace_chunks(stream())

    return ChunkReport(pages=pages, chunks=chunks)


def chunk_character(character: Character) -> list[Chunk]:
    """The page's chunks in page order: its profile, then each prose section."""
    sections = [("Profile", _pack(_profile_lines(character), "\n"))]
    for field in PROSE_FIELDS:
        text = getattr(character, field)
        if text:
            sections.extend(_field_sections(field, text))

    chunks: list[Chunk] = []
    for name, texts in sections:
        for text in texts:
            number = len(chunks)
            chunks.append(
                Chunk(
                    id=f"{character.pageid}:{character.revid}:{number}",
                    pageid=character.pageid,
                    revid=character.revid,
                    number=number,
                    title=character.title,
                    section=name,
                    text=text,
                )
            )
    return chunks


# Sections


def _profile_lines(character: Character) -> list[str]:
    """One `field name: value` line per fact the page states."""
    lines = []
    for field in fields(character):
        name = field.name
        if name in PAGE_FURNITURE or name in PROSE_FIELDS or name.endswith("_note"):
            continue

        value = getattr(character, name)
        if value:
            lines.append(f"{name.replace('_', ' ')}: {value}")
    return lines


def _field_sections(field: str, text: str) -> list[tuple[str, list[str]]]:
    """A prose field split at its headings, each part packed into chunk texts.

    Text before the first heading belongs to the field's own section.
    """
    name = field.capitalize()
    bodies: list[tuple[str, list[str]]] = [(name, [])]
    for line in text.splitlines():
        heading = HEADING.match(line)
        if heading:
            bodies.append((f"{name} > {heading['text']}", []))
        else:
            bodies[-1][1].append(line)

    sections = []
    for section, lines in bodies:
        paragraphs = PARAGRAPH_BREAK.split("\n".join(lines))
        units = [unit for paragraph in paragraphs for unit in _fit(paragraph.strip())]
        if units:
            sections.append((section, _pack(units, "\n\n")))
    return sections


# Packing


def _tokens(text: str) -> float:
    return len(text) / CHARS_PER_TOKEN


def _fit(paragraph: str) -> list[str]:
    """The paragraph whole, or pieces of it cut at sentence ends if it is too long."""
    if not paragraph:
        return []
    if _tokens(paragraph) <= TARGET_TOKENS:
        return [paragraph]

    # A single sentence over the target stays whole: cutting it mid-sentence
    # would leave halves that mean little alone.
    return _pack(SENTENCE_END.split(paragraph), " ")


def _pack(units: list[str], separator: str) -> list[str]:
    """Join neighbouring units while the result stays within the target."""
    packed: list[str] = []
    for unit in units:
        if packed and _tokens(packed[-1] + separator + unit) <= TARGET_TOKENS:
            packed[-1] += separator + unit
        else:
            packed.append(unit)
    return packed
