"""Records parsed from raw wiki pages: the facts the agent answers from and cites."""

from dataclasses import dataclass


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
