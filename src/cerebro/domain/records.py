"""Records parsed from raw wiki pages: the facts the agent answers from and cites."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Character:
    """One character page.

    Each text field is plain text, or None if it's empty. Where the wiki splits a field
    into sections, the headings are Markdown: `### Early Life`.

    `categories` holds the categories written on the page, such as `Time Travelers`.
    It is a tuple because each entry is its own tag; list fields such as `aliases`
    keep the wiki's own layout, usually one entry per line.
    """

    pageid: int
    title: str
    revid: int  # with pageid, names the exact revision an answer cites
    name: str
    current_alias: str | None
    aliases: str | None
    reality: str | None
    origin: str | None
    gender: str | None
    affiliation: str | None
    base_of_operations: str | None
    relatives: str | None
    first_appearance: str | None
    creators: str | None
    powers: str | None
    abilities: str | None
    history: str | None
    categories: tuple[str, ...]
