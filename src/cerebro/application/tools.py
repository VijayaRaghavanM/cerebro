"""The agent's tools: search pages by name, search their text, read one, list the
comics a page appears in, put a character's comics in reading order, and compare
two characters or teams."""

import re
from dataclasses import dataclass, fields
from typing import TYPE_CHECKING

from cerebro.domain.answers import Source, comic_vine_source
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
# Twenty-five issues keep a reading order short.
ORDER_LIMIT = 25
# One read stays within a few thousand tokens.
FIELD_LIMIT = 1500
PAGE_LIMIT = 12000
CUT = " [cut]"
# A reality or disambiguation tag at the end of a title, as in "Galactus (Earth-616)".
TRAILING_TAG = re.compile(r"\s*\([^()]*\)$")
# A comparison puts two pages in one reply, so each field is one short line.
COMPARE_FIELD_LIMIT = 200

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
# The fields that settle most comparisons: age, size, rank, origin.
CHARACTER_COMPARE_FIELDS = (
    "name",
    "current_alias",
    "reality",
    "identity",
    "first_appearance",
    "status",
)
TEAM_COMPARE_FIELDS = (
    "name",
    "reality",
    "leaders",
    "current_members",
    "first_appearance",
)
COMPARE_FIELDS: dict[type, tuple[str, ...]] = {
    Character: CHARACTER_COMPARE_FIELDS,
    Team: TEAM_COMPARE_FIELDS,
}


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
        # No cast-list count: asked for Comic Vine's appearances, the model quoted it
        # and never read a page.
        lines.append(f'{number}. "{hit.title}": {kind}')

    note = _name_note(lookup, name)
    if note:
        lines.insert(0, note)

    # A search result is not evidence, so it cites nothing.
    return ToolResult("\n".join(lines), ())


def _name_note(lookup: RecordLookup, name: str) -> str:
    """Who the wiki's links mean by this name, among main-reality pages. With no
    majority holder the name is ambiguous (Wikipedia's primary-topic rule), and the
    note asks the model to ask which one."""
    uses = {
        t: n for t, n in lookup.name_uses(name).items() if t.endswith("(Earth-616)")
    }
    if len(uses) < 2:
        return ""

    total = sum(uses.values())
    ranked = sorted(uses.items(), key=lambda item: -item[1])[:4]
    shares = [f"{title} ({count / total:.0%})" for title, count in ranked]
    holder, count = ranked[0]
    if count / total > 0.5:
        # A main holder needs no note when its title holds the name, as the search
        # ranks it first. When it does not, the model reads a page that does: asked
        # "Who is Destiny?", it read "Destiny (Overspace)" over Irene Adler.
        if name.strip().lower() in TRAILING_TAG.sub("", holder).lower():
            return ""
        return (
            f'MAIN MEANING: the wiki\'s links mean "{holder}" by "{name}" '
            f"({count / total:.0%} of them). Read that page unless the question asks "
            "for another one."
        )
    return (
        f'AMBIGUOUS NAME: several Earth-616 characters go by "{name}" in the wiki\'s '
        f"links: {', '.join(shares)}. Unless the question says which one, ask the "
        "user which they mean."
    )


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
            sources.append(comic_vine_source(character))

    return ToolResult(text, tuple(sources))


def compare_characters(lookup: RecordLookup, first: str, second: str) -> ToolResult:
    blocks = []
    sources = []
    for title in (first, second):
        record = lookup.record(title)
        if record is None:
            return ToolResult(f'No page is titled "{title}". Search for it first.', ())

        names = COMPARE_FIELDS.get(type(record))
        if names is None:
            return ToolResult(f'"{title}" is a comic; read it with read_page.', ())

        lines = [f"{title} ({READ_KINDS[type(record)]})"]
        lines += _brief(record, names)
        sources.append(Source(title, lookup.url(title)))

        if isinstance(record, Character):
            # A limit of 0 asks for the total alone.
            casts = lookup.appearances(title, 0).total
            lines.append(f"wiki comics' cast lists (in person): {casts:,}")

            character = lookup.comicvine(record.pageid)
            if character is not None:
                lines += _comicvine_brief(character)
                sources.append(comic_vine_source(character))

        blocks.append("\n".join(lines))

    return ToolResult("\n\n".join(blocks), tuple(sources))


def find_appearances(lookup: RecordLookup, title: str) -> ToolResult:
    appearances = lookup.appearances(title, APPEARANCE_LIMIT)
    if not appearances.total:
        return ToolResult(f'No comic\'s cast list names "{title}".', ())

    shown = len(appearances.first)
    lines = [
        # Whose count it is, so it is not taken for Comic Vine's.
        f"{title} appears in person in {appearances.total:,} comics' cast lists on"
        f" the wiki (not Comic Vine's count); the first {shown} by cover date:"
    ]
    for comic in appearances.first:
        lines.append(f"{comic.title} ({comic.date or 'no date'})")

    return ToolResult("\n".join(lines), (Source(title, lookup.url(title)),))


def reading_order(lookup: RecordLookup, title: str) -> ToolResult:
    record = lookup.record(title)
    if record is None:
        return ToolResult(f'No page is titled "{title}". Search for it first.', ())

    character = (
        lookup.comicvine(record.pageid) if isinstance(record, Character) else None
    )
    if character is None or character.detail is None or not character.detail.issues:
        # The wiki's cast lists are already in publication order.
        result = find_appearances(lookup, title)
        if not result.sources:
            return result

        note = "Comic Vine has no issue list for this page, so the order comes from"
        return ToolResult(
            f"{note} the wiki's cast lists.\n{result.text}", result.sources
        )

    issues = sorted(character.detail.issues, key=_publication_order)
    shown = issues[:ORDER_LIMIT]
    lines = [
        f"{title} is in {len(issues):,} issues on Comic Vine;"
        f" the first {len(shown)} by cover date:"
    ]
    lines += [_show(issue) for issue in shown]

    sources = (
        Source(title, lookup.url(title)),
        comic_vine_source(character),
    )
    return ToolResult("\n".join(lines), sources)


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


def _line(name: str, value: object, limit: int = FIELD_LIMIT) -> str:
    return f"{name.replace('_', ' ')}: {_cut(_show(value), limit)}"


def _brief(item: "DataclassInstance", names: tuple[str, ...]) -> list[str]:
    """Short lines for the named fields that have something in them."""
    lines = []
    for name in names:
        value = getattr(item, name)
        if value:
            lines.append(_line(name, value, COMPARE_FIELD_LIMIT))

    return lines


def _comicvine_brief(character: ComicVineCharacter) -> list[str]:
    lines = []
    if character.real_name:
        lines.append(_line("comic vine real name", character.real_name))
    lines.append(f"comic vine appearances: {character.appearances:,}")
    if character.detail is not None and character.detail.powers:
        # The total, so a list cut short is never counted by hand.
        powers = character.detail.powers
        label = f"comic vine powers ({len(powers)} listed)"
        lines.append(_line(label, powers, COMPARE_FIELD_LIMIT))

    return lines


def _show(value: object) -> str:
    if isinstance(value, tuple):
        return ", ".join(_show(item) for item in value)
    if isinstance(value, ComicVineIssue):
        dated = f" ({value.cover_date})" if value.cover_date else ""
        return f"{value.series} #{value.number}{dated}"
    return str(value)


def _publication_order(issue: ComicVineIssue) -> tuple[bool, str, str, int, str]:
    """Dated issues first by cover date, then by series and issue number; Comic Vine's
    own order is not publication order.
    """
    # Plain numbers sort as numbers ("10" after "9"); "1/2" or "Annual 1" as text.
    number = int(issue.number) if issue.number.isdigit() else -1
    return (
        issue.cover_date is None,
        issue.cover_date or "",
        issue.series,
        number,
        issue.number,
    )


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
        for field in fields(character.detail):
            value = getattr(character.detail, field.name)
            if field.name == "issues" or not value:
                continue

            # A list says how many items it holds, so a cut list is never counted by
            # hand.
            label = field.name
            if isinstance(value, tuple) and len(value) > 1:
                label += f" ({len(value)} listed)"
            lines.append(_line(label, value))

    return "\n".join(lines)


def _cut(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text

    return text[:limit] + CUT
