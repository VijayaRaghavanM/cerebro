"""Records parsed from raw wiki pages: the facts the agent answers from and cites."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Link:
    """A link in a record's text: the field it's in, the page it points to, and the
    text the reader sees, such as Link("affiliation", "X-Men (Earth-616)", "X-Men").
    """

    field: str
    title: str  # the linked page's title, as in a record's own `title`
    text: str


@dataclass(frozen=True)
class Character:
    """One character page.

    Each text field is plain text, or None if it's empty. Where the wiki splits a field
    into sections, the headings are Markdown: `### Early Life`. A `_note` field
    qualifies the field before it: `death_note` can be `(Off-Panel)`.

    `categories` holds the categories the page is filed under: those written on it,
    such as `Time Travelers`, and those its powers and abilities name, such as
    `Flight`. It is a tuple because each entry is its own tag; list fields such as
    `aliases` keep the wiki's own layout, usually one entry per line.

    `links` holds the links in the text fields, once per field, page and text, so
    the pages a field names can be followed to their own records.
    """

    pageid: int
    title: str
    revid: int  # with pageid, names the exact revision an answer cites

    # Names
    name: str
    name_note: str | None
    current_alias: str | None
    aliases: str | None
    display_name: str | None  # the name as the page heads its infobox
    titles: str | None  # ranks and honorifics, such as "Commander"
    nicknames: str | None
    codenames: str | None
    editorial_names: str | None
    impersonations: str | None

    # Identity
    identity: str | None
    identity_note: str | None
    reality: str | None
    reality_note: str | None
    status: str | None

    # Life
    gender: str | None
    origin: str | None
    citizenship: str | None
    occupation: str | None
    affiliation: str | None
    base_of_operations: str | None
    marital_status: str | None
    place_of_birth: str | None
    education: str | None

    # Appearance
    hair: str | None
    eyes: str | None
    eyeballs: str | None
    skin: str | None
    height: str | None
    weight: str | None
    unusual_features: str | None
    additional_attributes: str | None

    # Family and bonds
    relatives: str | None
    parents: str | None
    siblings: str | None
    children: str | None
    spouses: str | None
    in_laws: str | None
    grandparents: str | None
    ancestors: str | None
    descendants: str | None
    clones: str | None
    host_of: str | None
    hosts: str | None
    pet_of: str | None
    pets: str | None

    # Death
    death: str | None  # the issue they died in
    death_note: str | None
    killed_by: str | None
    cause_of_death: str | None
    place_of_death: str | None
    casualty_of: str | None  # the event they died in
    sacrifice: str | None
    suicide: str | None

    # Abilities
    powers: str | None
    abilities: str | None
    weaknesses: str | None
    equipment: str | None
    transportation: str | None
    weapons: str | None

    # Publication
    first_appearance: str | None
    first_appearance_note: str | None
    creators: str | None

    # Prose
    history: str | None
    personality: str | None
    overview: str | None
    notes: str | None
    trivia: str | None

    categories: tuple[str, ...]
    links: tuple[Link, ...]


@dataclass(frozen=True)
class Team:
    """One team page.

    Text fields, `_note` fields, `categories` and `links` work as they do in
    `Character`.
    """

    pageid: int
    title: str
    revid: int

    # Names
    name: str
    name_note: str | None
    display_name: str | None  # the name as the page heads its infobox
    editorial_names: str | None
    aliases: str | None

    # Members
    leaders: str | None
    current_members: str | None
    former_members: str | None

    # Identity
    identity: str | None
    identity_note: str | None
    affiliation: str | None
    allies: str | None
    enemies: str | None

    # Origin and status
    origin: str | None
    status: str | None
    reality: str | None
    reality_note: str | None
    base_of_operations: str | None
    place_of_formation: str | None
    place_of_dissolution: str | None

    # Paraphernalia
    equipment: str | None
    weapons: str | None
    transportation: str | None

    # Publication
    creators: str | None
    first_appearance: str | None
    first_appearance_note: str | None
    last_appearance: str | None
    last_appearance_note: str | None
    death: str | None  # the issue the team ended in, shown as its last appearance
    death_note: str | None
    destruction: str | None  # the same, under the name item and place pages use
    destruction_note: str | None

    # Prose
    overview: str | None
    history: str | None
    notes: str | None
    trivia: str | None

    categories: tuple[str, ...]
    links: tuple[Link, ...]
