"""Turns Marvel Database wikitext into records.

A character page is one call of the character template. Its fields hold wikitext:
links, footnotes, citations and the wiki's own link templates. The parser keeps the
text a reader would see and drops the rest.
"""

import re

import mwparserfromhell
from mwparserfromhell.nodes import Template
from mwparserfromhell.wikicode import Wikicode

from cerebro.domain.pages import RawPage
from cerebro.domain.records import Character

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

# An image link's text is its layout options and caption ("thumb|left|..."), not prose.
IMAGE_PREFIXES = ("file:", "image:")

LIST_MARKER = re.compile(r"^[*#:;]+\s*")
BOLD_OR_ITALIC = re.compile(r"'{2,}")
REALITY_SUFFIX = re.compile(r"\s*\([^()]*\)$")


def parse_character(page: RawPage) -> Character | None:
    """The character on the page, or None if the page has no character template."""
    template = _find_template(page.wikitext, CHARACTER_TEMPLATE)
    if template is None:
        return None

    return Character(
        pageid=page.pageid,
        title=page.title,
        revid=page.revid,
        name=_field_text(template, "Name") or REALITY_SUFFIX.sub("", page.title),
        current_alias=_field_text(template, "CurrentAlias"),
        aliases=_field_text(template, "Aliases"),
        reality=_field_text(template, "Reality"),
        origin=_field_text(template, "Origin"),
        gender=_field_text(template, "Gender"),
        affiliation=_field_text(template, "Affiliation"),
        base_of_operations=_field_text(template, "BaseOfOperations"),
        relatives=_field_text(template, "Relatives"),
        first_appearance=_field_text(template, "First"),
        creators=_field_text(template, "Creators"),
        powers=_field_text(template, "Powers"),
        abilities=_field_text(template, "Abilities"),
        history=_field_text(template, "History"),
    )


def _find_template(wikitext: str, name: str) -> Template | None:
    """The first top-level call of the named template, or None."""
    # Bold and italic markup that opens inside a template and closes after it, as in
    # {{WP|Scrooge McDuck|der '''cartoon duck}}!''', makes the parser lose the whole
    # page. Read '' and ''' as plain text instead; _tidy() removes them.
    code = mwparserfromhell.parse(wikitext, skip_style_tags=True)

    wanted = _normalise(name)
    for template in code.filter_templates(recursive=False):
        if _normalise(str(template.name)) == wanted:
            return template
    return None


def _normalise(name: str) -> str:
    """A template name the way MediaWiki compares it.

    Underscores and runs of spaces count as one space, spaces around the namespace
    colon don't count, and the first letter is case-blind.
    """
    name = re.sub(r"[\s_]+", " ", name).strip()
    name = re.sub(r"\s*:\s*", ":", name)
    return name[:1].upper() + name[1:]


def _field_text(template: Template, field: str) -> str | None:
    """The field as plain text, or None if the field is missing or empty.

    Cleaning edits the template in place. That's safe because each page is parsed
    into its own tree, which nothing else reads.
    """
    if not template.has(field):
        return None

    value = template.get(field).value
    _drop_footnotes(value)
    _show_link_templates(value)
    _drop_image_links(value)

    return _tidy(value.strip_code())


def _drop_footnotes(value: Wikicode) -> None:
    # strip_code keeps the text inside <ref> tags, so remove the tags first.
    # Innermost first, so a nested footnote goes before the one around it.
    for tag in reversed(value.filter_tags()):
        if str(tag.tag).strip().lower() == "ref":
            value.remove(tag)


def _show_link_templates(value: Wikicode) -> None:
    # Innermost first, so a template inside another is resolved before its parent
    # is replaced or dropped.
    for template in reversed(value.filter_templates()):
        shown = _shown_text(template)
        if shown is not None:
            value.replace(template, shown)


def _shown_text(template: Template) -> Wikicode | None:
    """The text a link template shows, or None for any other template."""
    params = LINK_TEMPLATES.get(_normalise(str(template.name)), ())
    for param in params:
        if template.has(param, ignore_empty=True):
            return template.get(param).value
    return None


def _drop_image_links(value: Wikicode) -> None:
    # Innermost first, so an image inside another image's caption goes before the
    # image around it.
    for link in reversed(value.filter_wikilinks()):
        if str(link.title).strip().lower().startswith(IMAGE_PREFIXES):
            value.remove(link)


def _tidy(text: str) -> str | None:
    """Trimmed plain text, or None if nothing is left.

    List markers and bold or italic marks go, and blank lines collapse to one.
    """
    text = BOLD_OR_ITALIC.sub("", text)
    lines = [LIST_MARKER.sub("", line.strip()) for line in text.splitlines()]
    text = re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()
    return text or None
