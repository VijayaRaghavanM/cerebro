import json
from pathlib import Path

import pytest

from cerebro.adapters.fandom_wikitext import parse_character
from cerebro.domain.pages import RawPage

REAL_PAGE = Path(__file__).parent / "fixtures" / "fandom" / "daniel_berkhart.json"


def real_page() -> RawPage:
    """Daniel Berkhart (Earth-616), saved from the crawl. It fills every field."""
    return RawPage(**json.loads(REAL_PAGE.read_text(encoding="utf-8")))


def wiki_page(wikitext: str) -> RawPage:
    return RawPage(
        pageid=1, title="Storm (Earth-616)", revid=1, timestamp="", wikitext=wikitext
    )


def character_page(
    template: str = "Marvel Database:Character Template", **fields: str
) -> RawPage:
    """A page that calls `template` with the given fields."""
    lines = [f"| {field} = {value}" for field, value in fields.items()]
    return wiki_page("\n".join(["{{" + template, *lines, "}}"]))


# The real page shows that the field names match the wiki's.


def test_reads_every_field_of_a_real_page() -> None:
    raw = real_page()
    record = parse_character(raw)
    assert record is not None

    assert (record.pageid, record.revid) == (raw.pageid, raw.revid)
    assert record.title == raw.title
    assert record.name == "Daniel Berkhart"
    assert record.current_alias == "Mysterio"
    assert record.reality == "Earth-616"
    assert record.origin == "Human, technology user"
    assert record.gender == "Male"
    assert record.base_of_operations == "New York City, New York"
    assert record.relatives == "Hudson Berkhart (son)"
    assert record.first_appearance == "Amazing Spider-Man Vol 1 141"
    assert record.creators == "Gerry Conway; Ross Andru"
    assert record.powers == "Illusions"

    # Lists and prose are checked for one entry or fact each, so a refreshed page
    # with a new alias or reworded text still passes.
    assert record.aliases and record.affiliation and record.abilities and record.history
    assert "Jack O'Lantern" in record.aliases
    assert "Sinister Six" in record.affiliation
    assert "enhanced speed" in record.abilities
    assert "J. Jonah Jameson" in record.history


# Each rule below is shown on the smallest page that needs it.


@pytest.mark.parametrize(
    ("wikitext", "shown"),
    [
        pytest.param(
            "{{m|{{cl|Hidden Vol 1 1}}|Shown}}",
            "Shown",
            id="link in a hidden parameter",
        ),
        pytest.param(
            "{{m|Storm (Earth-616)|}}",
            "Storm (Earth-616)",
            id="link with an empty name",
        ),
        pytest.param(
            "{{cl|Uncanny X-Men Vol 1 94}}", "Uncanny X-Men Vol 1 94", id="comic link"
        ),
        pytest.param("{{r|Uncanny X-Men Vol 1 94}}", None, id="only a citation"),
        pytest.param("Storm<ref>A<ref>B</ref></ref>", "Storm", id="nested footnotes"),
        pytest.param("[[Image:Storm.jpg|thumb]] Storm", "Storm", id="image link"),
        pytest.param(
            "[[File:A.jpg|thumb|[[File:B.jpg]] in flight]] Storm",
            "Storm",
            id="image inside a caption",
        ),
        pytest.param("''Ororo'' '''Munroe'''", "Ororo Munroe", id="italic and bold"),
        pytest.param(
            ": X-Men\n; Morlocks\n* Hellfire Club",
            "X-Men\nMorlocks\nHellfire Club",
            id="list markers",
        ),
        pytest.param(
            "X-Men\n* \n* \nMorlocks", "X-Men\n\nMorlocks", id="empty list items"
        ),
        pytest.param(
            "===Early Life===\nBorn in Harlem.\n== Later Years ==\nMoved to Kenya.",
            "### Early Life\nBorn in Harlem.\n## Later Years\nMoved to Kenya.",
            id="section headings",
        ),
        pytest.param("X-Men\n==\nMorlocks", "X-Men\n==\nMorlocks", id="bare = marks"),
    ],
)
def test_a_field_keeps_only_the_text_a_reader_sees(
    wikitext: str, shown: str | None
) -> None:
    record = parse_character(character_page(Affiliation=wikitext))

    assert record is not None
    assert record.affiliation == shown


def test_name_comes_from_the_name_field_or_the_title_without_the_reality() -> None:
    named = parse_character(character_page(Name="Ororo Munroe"))
    unnamed = parse_character(character_page())

    assert named is not None and unnamed is not None
    assert named.name == "Ororo Munroe"
    assert unnamed.name == "Storm"


@pytest.mark.parametrize(
    "template",
    [
        # Alyssa Larimore's page spells it this way.
        pytest.param("Marvel Database: Character Template", id="space after the colon"),
        pytest.param("Marvel_Database:Character_Template", id="underscores"),
    ],
)
def test_finds_the_character_template_under_another_spelling(template: str) -> None:
    assert parse_character(character_page(template)) is not None


def test_bold_that_closes_after_a_template_does_not_hide_the_page() -> None:
    # From Victor Vandoom's page: the bold opens inside {{WP}} and closes after it.
    page = character_page(Quote="{{WP|Scrooge McDuck|der '''cartoon duck}}!'''")

    assert parse_character(page) is not None


def test_pages_without_the_character_template_are_skipped() -> None:
    # Winding Way, a location page, is filed under Characters on the wiki.
    location = character_page("Marvel Database:Location Template")

    assert parse_character(location) is None
