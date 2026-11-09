import json
from dataclasses import asdict
from pathlib import Path

import pytest

from cerebro.adapters.fandom_wikitext import parse_character
from cerebro.domain.pages import RawPage

REAL_PAGE = Path(__file__).parent / "fixtures" / "fandom" / "daniel_berkhart.json"

# Every template field a character record reads. RealName is left out: it only
# stands in for a missing Name.
WIKI_FIELDS = """
    Name Name2 CurrentAlias Aliases Title Titles Nicknames Codenames EditorialNames
    Impersonations Identity Identity2 Reality Reality2 Status Gender Origin Citizenship
    Occupation Affiliation BaseOfOperations MaritalStatus PlaceOfBirth Education Hair
    Eyes Eyeballs Skin Height Weight UnusualFeatures AdditionalAttributes Relatives
    Parents Siblings Children Spouses InLaw Grandparents Ancestors Descendants Clones
    HostOf Hosts PetOf Pets Death Death2 KilledBy CauseOfDeath PlaceOfDeath CasualtyOf
    Sacrifice Suicide Powers Abilities Weaknesses Equipment Transportation Weapons First
    First2 Creators History Personality Overview Notes Trivia
""".split()


def real_page() -> RawPage:
    """Daniel Berkhart (Earth-616), saved from the crawl. It fills 33 of the fields."""
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


# The real page shows that the field names match the wiki's, and that no two fields
# are swapped.


def test_reads_every_field_of_a_real_page() -> None:
    raw = real_page()
    record = parse_character(raw)
    assert record is not None

    assert (record.pageid, record.revid) == (raw.pageid, raw.revid)
    assert record.title == raw.title
    assert record.name == "Daniel Berkhart"
    assert record.current_alias == "Mysterio"
    assert record.nicknames == "Misty the Wizard of Oz"
    assert record.identity == "Secret"
    assert record.reality == "Earth-616"
    assert record.gender == "Male"
    assert record.origin == "Human, technology user"
    assert record.citizenship == "American"
    assert record.occupation == "Criminal"
    assert record.base_of_operations == "New York City, New York"
    assert record.marital_status == "Single"
    assert record.place_of_birth == "United States"
    assert record.hair == "Brown; Balding"
    assert record.eyes == "Blue"
    assert record.height == "5'10\""
    assert record.weight == "160 lbs"
    assert record.relatives == "Hudson Berkhart (son)"
    assert record.death == "Venom Vol 2 11"
    assert record.death_note == "(mentioned)"
    assert record.killed_by == "Jack O'Lantern (Crime-Master) (Earth-616)"
    assert record.powers == "Illusions"
    assert record.first_appearance == "Amazing Spider-Man Vol 1 141"
    assert record.creators == "Gerry Conway; Ross Andru"

    # Lists and prose are checked for one entry or fact each, so a refreshed page
    # with a new alias or reworded text still passes.
    assert (
        record.aliases
        and record.affiliation
        and record.education
        and record.unusual_features
        and record.cause_of_death
        and record.abilities
        and record.equipment
        and record.first_appearance_note
        and record.history
        and record.trivia
    )
    assert "Jack O'Lantern" in record.aliases
    assert "Sinister Six" in record.affiliation
    assert "acting" in record.education
    assert "goatee" in record.unusual_features
    assert "Crime-Master" in record.cause_of_death
    assert "enhanced speed" in record.abilities
    assert "Gas Gloves" in record.equipment
    assert "Spectacular Spider-Man Vol 1 241" in record.first_appearance_note
    assert "J. Jonah Jameson" in record.history
    assert "DeMatteis" in record.trivia


def test_every_template_field_lands_in_exactly_one_record_field() -> None:
    # Each field holds its own name, so a misspelt, dropped or doubled field shows.
    record = parse_character(character_page(**{field: field for field in WIKI_FIELDS}))
    assert record is not None

    texts = [
        value
        for key, value in asdict(record).items()
        if isinstance(value, str) and key != "title"
    ]
    assert sorted(texts) == sorted(WIKI_FIELDS)


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
        pytest.param(
            "Storm{{DC|Superman|ref=true}}{{DC|Krypton|refname=k}}",
            "Storm",
            id="link used as a footnote",
        ),
        pytest.param("{{DC|Superman|ref=yes}}", "Superman", id="ref other than true"),
        pytest.param("[[Image:Storm.jpg|thumb]] Storm", "Storm", id="image link"),
        # Elizabeth Brant (Earth-19529) writes it this way.
        pytest.param("[[FIle:Betty.png|thumb]] Betty", "Betty", id="odd capitals"),
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


def test_collects_the_categories_and_keeps_them_out_of_the_text() -> None:
    lines = [
        "{{Marvel Database:Character Template",
        "| Reality = Earth-616[[Category:Characters Displaced to Earth-616]]",
        "| Affiliation = [[:Category:Black Skin|black]]",
        "}}",
        "[[Category:Time Travelers]]",
        "[[Category:Shared Identities: Successors|Storm]]",
        "[[Category:Time_Travelers]]",
        "[[CATEGORY:Armor Users]]",
    ]
    record = parse_character(wiki_page("\n".join(lines)))

    assert record is not None
    assert record.categories == (
        "Characters Displaced to Earth-616",
        "Time Travelers",
        "Shared Identities: Successors",
        "Armor Users",
    )
    assert record.reality == "Earth-616"
    # The leading colon makes it a visible link to the category, not a category.
    assert record.affiliation == "black"


def test_name_comes_from_name_then_real_name_then_the_title() -> None:
    named = parse_character(character_page(Name="Ororo Munroe", RealName="Ororo"))
    real_named = parse_character(character_page(RealName="Ororo Munroe"))
    unnamed = parse_character(character_page())

    assert named is not None and real_named is not None and unnamed is not None
    assert named.name == "Ororo Munroe"
    assert real_named.name == "Ororo Munroe"
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
