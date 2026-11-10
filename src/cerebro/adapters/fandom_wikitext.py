"""Turns Marvel Database wikitext into records.

A character or team page is one call of its template. Its fields hold wikitext:
links, footnotes, citations and the wiki's own link templates. The parser keeps the
text a reader would see, writes section headings as Markdown, and drops the rest.
The categories the page is filed under are kept apart from the text, and so are the
pages its fields link to.
"""

import re

import mwparserfromhell
from mwparserfromhell.nodes import Node, Template, Text, Wikilink
from mwparserfromhell.wikicode import Wikicode

from cerebro.adapters.fandom_templates import (
    CATEGORY_TEMPLATES,
    CHARACTER_FIELDS,
    CHARACTER_TEMPLATE,
    FIXED_TEXT_TEMPLATES,
    MEMBER_OF_TEMPLATE,
    NAVIGATION_TEMPLATE,
    PAGE_LINK_TEMPLATES,
    QUOTE_TEMPLATE,
    TAG_TEMPLATE,
    TEAM_FIELDS,
    TEAM_TEMPLATE,
    TEXT_TEMPLATES,
)
from cerebro.domain.pages import RawPage
from cerebro.domain.records import Character, Link, Team

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

    # Before the fields are cleaned, which removes the category links, power templates
    # and links inside them.
    categories = _categories(code)
    links = _links(template, CHARACTER_FIELDS, page.title)

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
        links=links,
        **texts,
    )


def parse_team(page: RawPage) -> Team | None:
    """The team on the page, or None if the page has no team template."""
    code = _parse(page.wikitext)
    template = _find_template(code, TEAM_TEMPLATE)
    if template is None:
        return None

    # Before the fields are cleaned, which removes the category links, power templates
    # and links inside them.
    categories = _categories(code)
    links = _links(template, TEAM_FIELDS, page.title)

    texts = {field: _field_text(template, wiki) for field, wiki in TEAM_FIELDS.items()}
    name = (
        _field_text(template, "Name")
        or _field_text(template, "OfficialName")
        or REALITY_SUFFIX.sub("", page.title)
    )

    return Team(
        pageid=page.pageid,
        title=page.title,
        revid=page.revid,
        name=name,
        categories=categories,
        links=links,
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
    """A template or namespaced page name the way MediaWiki compares it.

    The rules of a page title apply, and spaces around the namespace colon (the first
    one) don't count either.
    """
    return re.sub(r"\s*:\s*", ":", _page_title(name), count=1)


def _page_title(name: str) -> str:
    """A page title the way MediaWiki compares it.

    Underscores and runs of spaces count as one space, and the first letter is
    case-blind. A colon is part of the title: "Hulk: Gray Vol 1 1" keeps its space.
    """
    name = re.sub(r"[\s_]+", " ", name).strip()
    return name[:1].upper() + name[1:]


def _categories(code: Wikicode) -> tuple[str, ...]:
    """Every category the page is filed under, once each, in page order."""
    names = []
    for node in code.filter():
        name = _category(node)
        if name:
            names.append(name)
    return tuple(dict.fromkeys(names))


def _category(node: Node) -> str | None:
    """The category a link or a template files the page under, or None."""
    if isinstance(node, Wikilink):
        # The title is the category; a sort key after the | only orders its listing.
        title = _normalise(str(node.title))
    elif (
        isinstance(node, Template) and _normalise(str(node.name)) in CATEGORY_TEMPLATES
    ):
        # Named as a category link would be, so a power and a link to its category
        # come out the same.
        title = _normalise(f"Category:{_param(node, '1') or ''}")
    else:
        return None

    if not title.lower().startswith("category:"):
        return None
    return title[len("category:") :]


def _links(
    template: Template, fields: dict[str, str], page_title: str
) -> tuple[Link, ...]:
    """Every link in the name and the text fields, in field and page order, once each.

    `fields` maps each record field to its template field, as `CHARACTER_FIELDS` does.
    """
    links = [
        link
        for field, wiki in {"name": "Name", **fields}.items()
        for link in _field_links(template, field, wiki, page_title)
    ]
    return tuple(dict.fromkeys(links))


def _field_links(
    template: Template, field: str, wiki: str, page_title: str
) -> list[Link]:
    """The links in one field, in page order."""
    if not template.has(wiki):
        return []

    value = template.get(wiki).value
    # As in _clean, footnotes go first: a link in a footnote isn't in the text.
    _drop_footnotes(value)
    links = [_link(node, field, page_title) for node in value.filter()]
    return [link for link in links if link]


def _link(node: Node, field: str, page_title: str) -> Link | None:
    """The link a node makes to a page, or None if it makes none."""
    if isinstance(node, Wikilink) and _shows_text(node):
        target = str(node.title)
    elif (
        isinstance(node, Template) and _normalise(str(node.name)) in PAGE_LINK_TEMPLATES
    ):
        target = _param(node, "1") or ""
        if _normalise(str(node.name)) == MEMBER_OF_TEMPLATE:
            target = _in_reality(target, page_title)
    else:
        return None

    # A leading colon only makes a category link visible, and a # only picks a
    # section. A target holding a template, such as {{PAGENAME}}, is this page.
    title = _page_title(target.lstrip(":").split("#", 1)[0])
    if not title or "{{" in title:
        return None

    text = _clean(_parse(str(node))) or title
    return Link(field, title, text)


def _in_reality(team: str, page_title: str) -> str:
    """The team in the page's own reality if it names none, as {{m}} links it."""
    reality = REALITY_SUFFIX.search(page_title)
    if not team or reality is None or REALITY_SUFFIX.search(team):
        return team

    return f"{team} {reality.group().strip()}"


def _field_text(template: Template, field: str) -> str | None:
    """The field as plain text, or None if the field is missing or empty.

    Cleaning edits the template in place, so read anything else from the page first.
    """
    if not template.has(field):
        return None

    return _clean(template.get(field).value)


def _clean(value: Wikicode) -> str | None:
    """The text a reader sees in the wikitext, or None if there is none.

    Cleaning edits the wikitext in place.
    """
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

    for template in reversed(value.filter_templates()):
        if _is_footnote(template):
            value.remove(template)


def _is_footnote(template: Template) -> bool:
    """Whether a link template is called as a footnote.

    The wiki turns {{DC|Superman|ref=true}}, or a call with a refname, into a footnote.
    """
    as_ref = template.has("ref") and str(template.get("ref").value).strip() == "true"
    return as_ref or template.has("refname", ignore_empty=True)


def _show_text_templates(value: Wikicode) -> None:
    # Innermost first, so a template inside another is resolved before its parent
    # is replaced or dropped.
    for template in reversed(value.filter_templates()):
        shown = _shown_text(template)
        if shown is not None:
            value.replace(template, shown)


def _shown_text(template: Template) -> Wikicode | str | None:
    """The text a template shows, or None for one whose text the parser drops."""
    name = _normalise(str(template.name))
    if name in FIXED_TEXT_TEMPLATES:
        return FIXED_TEXT_TEMPLATES[name]
    if name == TAG_TEMPLATE:
        tag = _param(template, "1")
        return f"({tag})" if tag else None
    if name == NAVIGATION_TEMPLATE:
        return _navigation_text(template)
    if name == QUOTE_TEMPLATE:
        return _quote_text(template)

    for param in TEXT_TEMPLATES.get(name, ()):
        if template.has(param, ignore_empty=True):
            shown = template.get(param).value
            issue_range = _issue_range(template)
            return f"{shown}{issue_range}" if issue_range else shown
    return None


def _navigation_text(template: Template) -> Wikicode | None:
    """A box such as "Former Powers": its title as a heading over its body."""
    if not template.has("body"):
        return None
    box = template.get("body").value
    title = _param(template, "title")

    # Plain text nodes, so the parser can't read the heading as a heading of its own:
    # it stays text for _tidy to write as Markdown, like headings written in a field.
    # The newlines put the box on lines of its own when it follows other text.
    box.insert(0, Text(f"\n=== {title} ===\n" if title else "\n"))
    box.append(Text("\n"))
    return box


def _quote_text(template: Template) -> str | None:
    """A quote and its speaker. The source issue is a citation, so it's dropped."""
    quote = _param(template, "1")
    speaker = _param(template, "2")
    if quote is None:
        return None

    return f'{speaker}: "{quote}"' if speaker else f'"{quote}"'


def _issue_range(template: Template) -> str:
    """What a comic link's range adds: " to 23" for to=23, " and 18" for and=18."""
    issue_range = ""
    if end := _param(template, "to"):
        issue_range += f" to {end}"
    if also := _param(template, "and"):
        issue_range += f" and {also}"
    return issue_range


def _param(template: Template, name: str) -> str | None:
    """A parameter's trimmed text, or None if it's missing or empty."""
    if not template.has(name, ignore_empty=True):
        return None
    return str(template.get(name).value).strip()


def _drop_non_text_links(value: Wikicode) -> None:
    # Innermost first, so an image inside another image's caption goes before the
    # image around it.
    for link in reversed(value.filter_wikilinks()):
        if not _shows_text(link):
            value.remove(link)


def _shows_text(link: Wikilink) -> bool:
    """Whether a link is part of the text, unlike an image or a category link."""
    return not _normalise(str(link.title)).lower().startswith(NON_TEXT_LINKS)


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
