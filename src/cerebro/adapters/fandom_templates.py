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

COMIC_TEMPLATE = "Marvel Database:Comic Template"

# Each Comic text field and the template field it comes from.
COMIC_FIELDS = {
    # Dates; month and year are the cover date
    "release_date": "ReleaseDate",
    "month": "Month",
    "year": "Year",
    # Publication
    "editor_in_chief": "Editor-in-Chief",
    "pages": "Pages",
    "original_price": "OriginalPrice",
    "rating": "Rating",
    "isbn": "ISBN",
    "issn": "ISSN",
    "upc": "UPC",
    "legacy_number": "LegacyNumber",
    "canceled": "Canceled",
    "previous_issue": "PreviousIssue",
    "next_issue": "NextIssue",
    # Prose
    "solicit": "Solicit",
    "notes": "Notes",
    "trivia": "Trivia",
    "accolades": "Accolades",
}

# The numbered fields each Comic list comes from: Event1, Event2, ...
EVENT_FIELDS = r"Event(\d+)"
STORY_ARC_FIELDS = r"StoryArc(\d+)"
STORYLINE_FIELDS = r"Storyline(\d+)"
TIE_IN_FIELDS = r"Tie-in(\d+)"

# The fields naming a cover's artists, numbered by cover and then by artist:
# Image2_Artist1 is the second cover's first artist.
COVER_ARTIST_FIELDS = r"Image(\d+)_Artist(\d+)"

# Each Story text field and the template field it comes from, numbered by story:
# StoryTitle2 is the second story's title.
STORY_FIELDS = {
    "title": "StoryTitle",
    "synopsis": "Synopsis",
    "appearing": "Appearing",
    "reprint_of": "ReprintOf",
    "reprint_of_story": "ReprintOfStory",
}

# Each Credits field and the template fields it comes from, numbered by story and
# then by person: Writer2_1 is the second story's first writer.
STORY_CREDITS = {
    "writers": "Writer",
    "pencilers": "Penciler",
    "inkers": "Inker",
    "colorists": "Colorist",
    "letterers": "Letterer",
    "editors": "Editor",
    "adapted_from": "AdaptedFrom",
}

# Translators, numbered like credits, and the credit the wiki lists them under.
TRANSLATION_CREDITS = {"Translator": "writers", "TranslatorLetterer": "letterers"}

# The section labels the template fills a new story's cast list with. A cast list with
# nothing but these, empty list items and blank lines is empty.
CAST_LIST_LABELS = (
    "Featured Characters",
    "Supporting Characters",
    "Antagonists",
    "Other Characters",
    "Races and Species",
    "Realities",
    "Locations",
    "Items",
    "Vehicles",
)

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

# Templates that always show the same text, by page name.
FIXED_TEXT_TEMPLATES = {
    "Omega Level Mutant": "Omega Level mutant",
}

# Appearance templates, by page name, with the tag the wiki writes in parentheses
# after the page in their first parameter: {{Mentioned|[[Storm (Earth-616)|Storm]]}}
# shows "Storm (Mentioned)", and an empty tag shows the page alone. A story's cast
# list is made of them; a first appearance or death note uses them without a page.
APPEARANCE_TAGS = {
    "A": "",
    "Apn": "",  # also links the previous and next appearance, which aren't text
    "Minor": "",
    "Mentioned": "Mentioned",
    "Referenced": "Referenced",
    "Named": "Named only",
    "Narration": "Mentioned in narration or thoughts",
    "Invoked": "Invoked",
    "Topical Reference": "Topical Reference",
    "Cameo": "Cameo",
    "Unnamed": "Unnamed",
    "Voice": "Voice only",
    "Shadow": "Shadow only",
    # First and last appearances
    "1st": "First appearance",
    "1stFull": "First full appearance",
    "1stChron": "First appearance chronologically",
    "1st Real Name": "Name revealed",
    "1st Unnamed": "First appearance; unnamed",
    "1st Dies": "First appearance; dies",
    "1st Destruction": "First appearance; destruction",
    "1st Vision": "First appearance; vision or hallucination",
    "1st Dream": "First appearance; dream",
    "1st Illusion": "First appearance; illusion or holographic simulation",
    "1st Photo": "First appearance; photo",
    "1st Corpse": "First appearance; corpse, skeleton or other remains",
    "1st Variant": "First appearance in this reality",
    "Final": "Final appearance",
    # Flashbacks and recaps; Fb and Flashonly redirect to FlashOnly
    "FlashOnly": "Only in flashback",
    "Fb": "Only in flashback",
    "Flashonly": "Only in flashback",
    "Flashback": "Main story and flashback",
    "FlashforwardOnly": "Only in flashforward",
    "Flashforward": "Main story and flashforward",
    "Flashback and Flashforward": "Main story, flashback, flashforward",
    "ChronoFB": "Appears in flashback",
    "Chronology": "See chronology",
    "RecapOnly": "Only in recap",
    "Recap": "Main story and recap",
    "Memory": "In a memory",
    # Deaths, endings and changes; Dies redirects to Death
    "Death": "Death",
    "Dies": "Death",
    "Dead": "Dead",
    "Deceased": "Deceased",
    "ApDeath": "Apparent death",
    "Corpse": "Corpse, skeleton or other remains",
    "Tombstone": "Tombstone",
    "Ghost": "Ghost, soul or spirit",
    "Resurrection": "Resurrection",
    "Origin": "Origin revealed",
    "Destruction": "Destruction",
    "Destroyed": "Destroyed",
    "Defunct": "Defunct",
    "Disbands": "Disbands",
    "Joins": "Joins",
    "Leaves": "Leaves",
    "Rejoins": "Rejoins",
    # Not there in person; Screen redirects to OnScreen, Bts to BTS
    "Vision": "Vision or hallucination",
    "Dream": "Dream",
    "Illusion": "Illusion or holographic simulation",
    "Hologram": "As a hologram",
    "Imagination": "Imagination",
    "OnScreen": "Appears on screen",
    "Screen": "Appears on screen",
    "OnScreenOnly": "Only on screen as a static image or video record",
    "Photo": "Photo",
    "Drawing": "Drawing",
    "Poster": "Poster",
    "Statue": "Statue",
    "Toy": "Toy",
    "Map": "Map",
    "BTS": "Behind the scenes",
    "Bts": "Behind the scenes",
}

# Appearance templates whose tag names someone, from their last parameter, with the
# page in a first parameter before it: {{PossessedBy|[[Jean Grey (Earth-616)|Jean
# Grey]]|Phoenix Force}} shows "Jean Grey (Possessed by Phoenix Force)". G, the
# general tag template, adds no words: {{g|Mentioned}} shows "(Mentioned)".
NAMING_TAGS = {
    "G": "",
    "Green": "",  # G redirects to it
    "1stas": "First appearance as",
    "PossessedBy": "Possessed by",
    "Impersonates": "Impersonates",
    "Controlled": "Controlled by",
}

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
