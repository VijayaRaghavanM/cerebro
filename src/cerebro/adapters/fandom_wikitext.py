"""Turns Marvel Database wikitext into records.

A character page is one call of the character template. Its fields hold wikitext:
links, footnotes, citations and the wiki's own link templates. The parser keeps the
text a reader would see, writes section headings as Markdown, and drops the rest.
The page's category links are kept apart from the text.
"""

import re

import mwparserfromhell
from mwparserfromhell.nodes import Template
from mwparserfromhell.wikicode import Wikicode

from cerebro.adapters.fandom_templates import (
    CHARACTER_FIELDS,
    CHARACTER_TEMPLATE,
    TEXT_TEMPLATES,
)
from cerebro.domain.pages import RawPage
from cerebro.domain.records import Character

# Links that aren't prose: an image link's text is its layout options and caption
# ("thumb|left|..."), and a category link shows nothing. A leading colon, as in
# [[:Category:Black Skin|black]], makes a link visible, so those keep their text.
# Namespace names are case-blind: [[FIle:...]] is still an image.
NON_TEXT_LINKS = ("file:", "image:", "category:")

LIST_MARKER = re.compile(r"^[*#:;]+\s*")
BOLD_OR_ITALIC = re.compile(r"'{2,}")
# The parser doesn't see headings inside a template field, so they arrive as text.
# A heading needs some text: a line of only = marks is left alone.
HEADING = re.compile(r"^(=+)\s*([^=\s].*?)\s*=+$", re.MULTILINE)
REALITY_SUFFIX = re.compile(r"\s*\([^()]*\)$")


def parse_character(page: RawPage) -> Character | None:
    """The character on the page, or None if the page has no character template."""
    code = _parse(page.wikitext)
    template = _find_template(code, CHARACTER_TEMPLATE)
    if template is None:
        return None

    # Before the fields are cleaned, which removes the category links inside them.
    categories = _categories(code)

    texts = {
        field: _field_text(template, wiki) for field, wiki in CHARACTER_FIELDS.items()
    }
    name = (
        _field_text(template, "Name")
        or _field_text(template, "RealName")
        or REALITY_SUFFIX.sub("", page.title)
    )

    return Character(
        pageid=page.pageid,
        title=page.title,
        revid=page.revid,
        name=name,
        categories=categories,
        **texts,
    )


def _parse(wikitext: str) -> Wikicode:
    # Bold and italic markup that opens inside a template and closes after it, as in
    # {{WP|Scrooge McDuck|der '''cartoon duck}}!''', makes the parser lose the whole
    # page. Read '' and ''' as plain text instead; _tidy() removes them.
    return mwparserfromhell.parse(wikitext, skip_style_tags=True)


def _find_template(code: Wikicode, name: str) -> Template | None:
    """The first top-level call of the named template, or None."""
    wanted = _normalise(name)
    for template in code.filter_templates(recursive=False):
        if _normalise(str(template.name)) == wanted:
            return template
    return None


def _normalise(name: str) -> str:
    """A template or page name the way MediaWiki compares it.

    Underscores and runs of spaces count as one space, spaces around the namespace
    colon (the first one) don't count, and the first letter is case-blind.
    """
    name = re.sub(r"[\s_]+", " ", name).strip()
    name = re.sub(r"\s*:\s*", ":", name, count=1)
    return name[:1].upper() + name[1:]


def _categories(code: Wikicode) -> tuple[str, ...]:
    """Every category the page links to, once each, in page order."""
    names = []
    for link in code.filter_wikilinks():
        # The title is the category; a sort key after the | only orders its listing.
        title = _normalise(str(link.title))
        if title.lower().startswith("category:"):
            names.append(title[len("category:") :])
    return tuple(dict.fromkeys(names))


def _field_text(template: Template, field: str) -> str | None:
    """The field as plain text, or None if the field is missing or empty.

    Cleaning edits the template in place, so read anything else from the page first.
    """
    if not template.has(field):
        return None

    value = template.get(field).value
    _drop_footnotes(value)
    _show_text_templates(value)
    _drop_non_text_links(value)

    return _tidy(value.strip_code())


def _drop_footnotes(value: Wikicode) -> None:
    # strip_code keeps the text inside <ref> tags, so remove the tags first.
    # Innermost first, so a nested footnote goes before the one around it.
    for tag in reversed(value.filter_tags()):
        if str(tag.tag).strip().lower() == "ref":
            value.remove(tag)


def _show_text_templates(value: Wikicode) -> None:
    # Innermost first, so a template inside another is resolved before its parent
    # is replaced or dropped.
    for template in reversed(value.filter_templates()):
        shown = _shown_text(template)
        if shown is not None:
            value.replace(template, shown)


def _shown_text(template: Template) -> Wikicode | None:
    """The text a template from TEXT_TEMPLATES shows, or None for any other template."""
    params = TEXT_TEMPLATES.get(_normalise(str(template.name)), ())
    for param in params:
        if template.has(param, ignore_empty=True):
            return template.get(param).value
    return None


def _drop_non_text_links(value: Wikicode) -> None:
    # Innermost first, so an image inside another image's caption goes before the
    # image around it.
    for link in reversed(value.filter_wikilinks()):
        if _normalise(str(link.title)).lower().startswith(NON_TEXT_LINKS):
            value.remove(link)


def _tidy(text: str) -> str | None:
    """Trimmed plain text, or None if nothing is left.

    List markers and bold or italic marks go, headings become Markdown headings, and
    blank lines collapse to one.
    """
    text = BOLD_OR_ITALIC.sub("", text)
    lines = [LIST_MARKER.sub("", line.strip()) for line in text.splitlines()]

    # After the list markers, because # also starts a numbered list in wikitext.
    text = HEADING.sub(_markdown_heading, "\n".join(lines))
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text or None


def _markdown_heading(heading: re.Match[str]) -> str:
    """`===Early Life===` as `### Early Life`, at the same level."""
    marks, title = heading.groups()
    return "#" * len(marks) + " " + title
