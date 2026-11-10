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

TEAM_TEMPLATE = "Marvel Database:Team Template"

# Each Team text field and the template field it comes from. `name` is read on its
# own, because it falls back to other fields.
TEAM_FIELDS = {
    # Names
    "name_note": "Name2",
    "display_name": "Title",
    "editorial_names": "EditorialNames",
    "aliases": "Aliases",
    # Members
    "leaders": "Leaders",
    "current_members": "CurrentMembers",
    "former_members": "FormerMembers",
    # Identity
    "identity": "Identity",
    "identity_note": "Identity2",
    "affiliation": "Affiliation",
    "allies": "Allies",
    "enemies": "Enemies",
    # Origin and status
    "origin": "Origin",
    "status": "Status",
    "reality": "Reality",
    "reality_note": "Reality2",
    "base_of_operations": "BaseOfOperations",
    "place_of_formation": "PlaceOfFormation",
    "place_of_dissolution": "PlaceOfDissolution",
    # Paraphernalia
    "equipment": "Equipment",
    "weapons": "Weapons",
    "transportation": "Transportation",
    # Publication
    "creators": "Creators",
    "first_appearance": "First",
    "first_appearance_note": "First2",
    "last_appearance": "Last",
    "last_appearance_note": "Last2",
    "death": "Death",
    "death_note": "Death2",
    "destruction": "Destruction",
    "destruction_note": "Destruction2",
    # Prose
    "overview": "Overview",
    "history": "History",
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
    # Links to other wikis, for characters from licensed and crossover comics
    "Doctor Who": ("2", "1"),
    "Image Wiki": ("2", "1"),
    "Lovecraft": ("2", "1"),
    "Star Wars": ("2", "1"),
    "Star Trek": ("2", "1"),
    "WP": ("2", "1"),  # redirects to Wikipedia
    "Wikipedia": ("2", "1"),
    "Appendix": ("2", "1"),
    "Cl": ("2", "1"),  # comic
    "C": ("2", "1"),  # comic, redirects to Cl
    "Sld": ("2", "1"),  # comic
    "Cid": ("1",),  # comic, which the wiki shows as its date and story title
    "Sl": ("2", "1"),  # film or TV series
    "Ml": ("2", "1"),  # film or TV series
    "Vl": ("2", "1"),  # video game
    "Elt": ("2", "1"),  # episode
    "El": ("2", "1"),  # episode
    "Power": ("2", "1"),
    "Ability": ("2", "1"),
    "Weakness": ("2", "1"),
    "Speaker": ("2", "1"),  # a language
    "CategoryLink": ("2", "1"),
    "MessageBox": ("1", "Message"),
}

# Templates that always show the same text, by page name. Most are appearance tags,
# which the wiki writes in parentheses after a first appearance or a death.
FIXED_TEXT_TEMPLATES = {
    "Mentioned": "(Mentioned)",
    "Referenced": "(Referenced)",
    "1stFull": "(First full appearance)",
    "FlashOnly": "(Only in flashback)",
    "OnScreenOnly": "(Only on screen as a static image or video record)",
    "BTS": "(Behind the scenes)",
    "Corpse": "(Corpse, skeleton or other remains)",
    "Tombstone": "(Tombstone)",
    "Dream": "(Dream)",
    "Vision": "(Vision or hallucination)",
    "Photo": "(Photo)",
    "Drawing": "(Drawing)",
    "Omega Level Mutant": "Omega Level mutant",
}

# The general tag template, which names its own tag: {{g|Chronologically}} shows
# "(Chronologically)".
TAG_TEMPLATE = "G"

# A collapsible box, such as "Former Powers": {{Navigation|title=...|body=...}}.
NAVIGATION_TEMPLATE = "Navigation"

# A quote, its speaker and the issue it comes from: {{Quote|...|Venom|Venom Vol 1 1}}.
QUOTE_TEMPLATE = "Quote"

# Templates that link to a page on this wiki, named in their first parameter:
# {{cl|Uncanny X-Men Vol 1 94}} links to that comic.
PAGE_LINK_TEMPLATES = {"M", "Cl", "C", "Sld", "Sl", "Ml", "Vl", "Elt", "El"}

# The "Member of" template, which links to a team in the page's own reality when it
# names none: {{m|X-Men}} on Storm (Earth-616) links to X-Men (Earth-616).
MEMBER_OF_TEMPLATE = "M"

# Templates that file the page under the category named in their first parameter:
# {{Power|Flight|flying}} shows "flying" and files the page under Flight.
CATEGORY_TEMPLATES = {"Power", "Ability"}
