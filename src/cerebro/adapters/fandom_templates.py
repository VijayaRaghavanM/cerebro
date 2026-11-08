"""Names of the Marvel Database templates the parser reads, and of their fields.

When the wiki renames a template or a field, the change goes here.
"""

CHARACTER_TEMPLATE = "Marvel Database:Character Template"

# Link templates by page name, with the parameters that may hold the text they show.
# The first one with a value wins: {{m|Page (Earth-616)|Shown name}} shows
# "Shown name", and {{m|Page (Earth-616)}} shows the page. Page names start with a
# capital, so {{cl|...}} is the "Cl" entry.
# Every other template is a citation or decoration ({{r}}, {{Citation}}) and is dropped.
LINK_TEMPLATES = {
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
    "G": ("1",),  # glossary term
}
