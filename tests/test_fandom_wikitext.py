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

# One call of each template that shows text, and the text the wiki shows for it. Like
# WIKI_FIELDS, the list is kept apart from the parser's tables, so a dropped or
# mistyped row shows.
TEXT_TEMPLATE_CALLS = [
    ("{{m|X-Men (Earth-616)|X-Men}}", "X-Men"),
    ("{{DC|Kent Nelson (New Earth)|Doctor Fate}}", "Doctor Fate"),
    (
        "{{wc|heykidscomics|Amazing Man Comics Vol 1 5|Amazing Man #5}}",
        "Amazing Man #5",
    ),
    ("{{Doctor Who|Robot (TV story)|Robot}}", "Robot"),
    ("{{Image Wiki|Spawn (Al Simmons)|Spawn}}", "Spawn"),
    ("{{lovecraft|Azathoth|the Blind Idiot God}}", "the Blind Idiot God"),
    ("{{Star Wars|Anakin Skywalker|Darth Vader}}", "Darth Vader"),
    ("{{Star Trek|James T. Kirk|Captain Kirk}}", "Captain Kirk"),
    ("{{WP|Harlem, New York|Harlem}}", "Harlem"),
    ("{{Wikipedia|New York City|New York}}", "New York"),
    ("{{Appendix|Appendix/earthavataars.htm|Eurth Hawkeye}}", "Eurth Hawkeye"),
    ("{{cl|Tarzan Vol 1 15|Tarzan #15}}", "Tarzan #15"),
    ("{{c|Hulk: Gray Vol 1 1|Hulk: Gray #1}}", "Hulk: Gray #1"),
    ("{{sld|She-Hulk Vol 2 25|She-Hulk #25}}", "She-Hulk #25"),
    ("{{Cid|Renew Your Vows Vol 1 5}}", "Renew Your Vows Vol 1 5"),
    ("{{sl|Kull the Conqueror Vol 1 4|previous issue}}", "previous issue"),
    ("{{ml|X2 (film)|X2}}", "X2"),
    ("{{vl|Spider-Man (2018 video game)|Spider-Man}}", "Spider-Man"),
    ("{{elt|Big Hero 6: The Series Season 1 15|Fan Friction}}", "Fan Friction"),
    (
        "{{el|X-Men: The Animated Series Season 1 1|Night of the Sentinels}}",
        "Night of the Sentinels",
    ),
    ("{{Power|Weather Manipulation}}", "Weather Manipulation"),
    ("{{Ability|Martial Arts}}", "Martial Arts"),
    ("{{Weakness|Claustrophobia|claustrophobic}}", "claustrophobic"),
    ("{{Speaker|English}}", "English"),
    ("{{CategoryLink|Mutants|mutant}}", "mutant"),
    ("{{MessageBox|Message=Gabriel's memories}}", "Gabriel's memories"),
    ("{{Mentioned}}", "(Mentioned)"),
    ("{{Referenced}}", "(Referenced)"),
    ("{{1stFull}}", "(First full appearance)"),
    ("{{FlashOnly}}", "(Only in flashback)"),
    ("{{OnScreenOnly}}", "(Only on screen as a static image or video record)"),
    ("{{BTS}}", "(Behind the scenes)"),
    ("{{Corpse}}", "(Corpse, skeleton or other remains)"),
    ("{{Tombstone}}", "(Tombstone)"),
    ("{{Dream}}", "(Dream)"),
    ("{{Vision}}", "(Vision or hallucination)"),
    ("{{Photo}}", "(Photo)"),
    ("{{Drawing}}", "(Drawing)"),
    ("{{Omega Level Mutant|type=krakoan|X-Men: Red Vol 2 16}}", "Omega Level mutant"),
    ("{{g|Chronologically}}", "(Chronologically)"),
]


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


def test_every_text_template_shows_its_text() -> None:
    calls = [call for call, _ in TEXT_TEMPLATE_CALLS]
    shown = [text for _, text in TEXT_TEMPLATE_CALLS]

    record = parse_character(character_page(Affiliation="\n".join(calls)))

    assert record is not None
    assert record.affiliation == "\n".join(shown)


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
        pytest.param(
            "Flight {{Navigation|title=''Former Powers''|body=* [[Mind|Telepathy]]}}",
            "Flight\n### Former Powers\nTelepathy",
            id="navigation box",
        ),
        pytest.param(
            "{{Navigation|body=Telepathy}}", "Telepathy", id="navigation box, no title"
        ),
        pytest.param(
            "{{Navigation|title=Former Powers}}", None, id="navigation box, no body"
        ),
        pytest.param(
            "{{Quote|We are Venom.|Venom|Venom Vol 1 1}}",
            'Venom: "We are Venom."',
            id="quote",
        ),
        pytest.param(
            "{{Quote|We are Venom.}}", '"We are Venom."', id="quote, no speaker"
        ),
        pytest.param("{{Quote}}", None, id="empty quote"),
        pytest.param("{{g}}", None, id="empty tag"),
        pytest.param(
            "{{cl|Tarzan Vol 1 15|to=23}}, {{cl|Conan the Barbarian Vol 1 17|and=18}}",
            "Tarzan Vol 1 15 to 23, Conan the Barbarian Vol 1 17 and 18",
            id="issue ranges",
        ),
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
