"""Names of the Marvel Database templates the parser reads, and of their fields.

When the wiki renames a template or a field, the change goes here.
"""

CHARACTER_TEMPLATE = "Marvel Database:Character Template"

# Each Character text field and the template field it comes from. `name` is read on
# its own, because it falls back to other fields.
CHARACTER_FIELDS = {
    # Names
    "name_note": "Name2",
    "current_alias": "CurrentAlias",
    "aliases": "Aliases",
    "display_name": "Title",
    "titles": "Titles",
    "nicknames": "Nicknames",
    "codenames": "Codenames",
    "editorial_names": "EditorialNames",
    "impersonations": "Impersonations",
    # Identity
    "identity": "Identity",
    "identity_note": "Identity2",
    "reality": "Reality",
    "reality_note": "Reality2",
    "status": "Status",
    # Life
    "gender": "Gender",
    "origin": "Origin",
    "citizenship": "Citizenship",
    "occupation": "Occupation",
    "affiliation": "Affiliation",
    "base_of_operations": "BaseOfOperations",
    "marital_status": "MaritalStatus",
    "place_of_birth": "PlaceOfBirth",
    "education": "Education",
    # Appearance
    "hair": "Hair",
    "eyes": "Eyes",
    "eyeballs": "Eyeballs",
    "skin": "Skin",
    "height": "Height",
    "weight": "Weight",
    "unusual_features": "UnusualFeatures",
    "additional_attributes": "AdditionalAttributes",
    # Family and bonds
    "relatives": "Relatives",
    "parents": "Parents",
    "siblings": "Siblings",
    "children": "Children",
    "spouses": "Spouses",
    "in_laws": "InLaw",
    "grandparents": "Grandparents",
    "ancestors": "Ancestors",
    "descendants": "Descendants",
    "clones": "Clones",
    "host_of": "HostOf",
    "hosts": "Hosts",
    "pet_of": "PetOf",
    "pets": "Pets",
    # Death
    "death": "Death",
    "death_note": "Death2",
    "killed_by": "KilledBy",
    "cause_of_death": "CauseOfDeath",
    "place_of_death": "PlaceOfDeath",
    "casualty_of": "CasualtyOf",
    "sacrifice": "Sacrifice",
    "suicide": "Suicide",
    # Abilities
    "powers": "Powers",
    "abilities": "Abilities",
    "weaknesses": "Weaknesses",
    "equipment": "Equipment",
    "transportation": "Transportation",
    "weapons": "Weapons",
    # Publication
    "first_appearance": "First",
    "first_appearance_note": "First2",
    "creators": "Creators",
    # Prose
    "history": "History",
    "personality": "Personality",
    "overview": "Overview",
    "notes": "Notes",
    "trivia": "Trivia",
}

# Templates that show text, by page name, with the parameters that may hold it.
# The first one with a value wins: {{m|Page (Earth-616)|Shown name}} shows
# "Shown name", and {{m|Page (Earth-616)}} shows the page. Page names start with a
# capital, so {{cl|...}} is the "Cl" entry.
# Every other template is a citation or decoration ({{r}}, {{Citation}}) and is dropped.
TEXT_TEMPLATES = {
    "M": ("2", "1"),
    "DC": ("2", "1"),
    "Wc": ("3", "2"),  # {{wc|other wiki|Page|Shown name}}
    "Cl": ("1",),  # comic
    "Sld": ("1",),  # comic
    "Sl": ("1",),  # film or TV series
    "Ml": ("1",),  # film or TV series
    "Vl": ("1",),  # video game
    "Elt": ("1",),  # episode
    "Power": ("1",),
    "Ability": ("1",),
    "G": ("1",),  # a tag, such as {{g|Mentioned}}
}
