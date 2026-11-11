"""Match Comic Vine characters to Fandom character pages by the issues they share."""

import re
from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import dataclass

from cerebro.domain.comicvine import CharacterMatch, ComicVineCharacter, ComicVineIssue
from cerebro.domain.records import Character, Comic
from cerebro.ports.comicvine import ComicVineSource, MatchStore
from cerebro.ports.records import RecordReader

# A Fandom comic page title: "Amazing Fantasy Vol 1 15" is series, volume and number.
COMIC_TITLE = re.compile(r"(?P<series>.+?) Vol \d+ (?P<number>\S+)")
# A nickname inside a Fandom name, as in 'Katherine Anne "Kitty" Pryde'.
NICKNAME = re.compile(r'(?P<first>[^"]*)"(?P<nick>[^"]+)"(?P<last>.*)')

# An issue compared across the two sources: series, number and cover year.
type IssueKey = tuple[str, str, str]


@dataclass(frozen=True)
class MatchReport:
    comicvine: int  # Comic Vine characters read
    with_issues: int  # of those, the ones with detail, which carries the issue list
    matched: int
    pages_claimed_twice: int  # Fandom pages matched by more than one of them


def match_comicvine(
    records: RecordReader, comicvine: ComicVineSource, store: MatchStore
) -> MatchReport:
    """Match Comic Vine's characters to the stored ones; replace the stored matches."""
    characters = list(comicvine.characters())
    matches = match_characters(records.characters(), records.comics(), characters)
    store.replace_matches(matches)

    claims = Counter(match.pageid for match in matches)
    return MatchReport(
        comicvine=len(characters),
        with_issues=sum(character.detail is not None for character in characters),
        matched=len(matches),
        pages_claimed_twice=sum(count > 1 for count in claims.values()),
    )


def match_characters(
    fandom: Iterable[Character],
    comics: Iterable[Comic],
    comicvine: Iterable[ComicVineCharacter],
) -> list[CharacterMatch]:
    """The Fandom page each Comic Vine character with an issue list is, where clear.

    The candidates are the character pages in the cast lists of the character's issues
    that share a name word with it. A whole shared name ranks first, then the overlap
    of issues; a tie at the top matches nothing.
    """
    page_ids: dict[str, int] = {}
    page_names: dict[int, _Names] = {}
    for page in fandom:
        page_ids[page.title] = page.pageid
        page_names[page.pageid] = _Names.of(_fandom_names(page))
    casts = _Casts(comics, page_ids)

    matches = []
    for character in comicvine:
        match = _match(character, page_names, casts)
        if match is not None:
            matches.append(match)
    return matches


@dataclass(frozen=True)
class _Names:
    """A character's names compared loosely, whole and word by word."""

    whole: frozenset[str]
    words: frozenset[str]

    @classmethod
    def of(cls, names: Iterable[str]) -> "_Names":
        whole = frozenset(_key(name) for name in names) - {""}
        return cls(whole, frozenset(word for name in whole for word in name.split()))


class _Casts:
    """Fandom's cast lists: which character pages appear in each comic."""

    def __init__(self, comics: Iterable[Comic], page_ids: dict[str, int]) -> None:
        self.appearances: Counter[int] = Counter()  # comics each page appears in
        self._by_issue: dict[IssueKey, list[frozenset[int]]] = defaultdict(list)

        for comic in comics:
            cast = frozenset(
                page_ids[link.title]
                for story in comic.stories
                for link in story.links
                if link.field == "appearing" and link.title in page_ids
            )
            self.appearances.update(cast)
            key = _comic_key(comic)
            if key is not None:
                self._by_issue[key].append(cast)

    def in_issue(self, issue: IssueKey) -> frozenset[int] | None:
        """The cast of the one comic that is this issue; None if no comic or several."""
        found = self._by_issue.get(issue, [])
        return found[0] if len(found) == 1 else None


def _match(
    character: ComicVineCharacter, page_names: dict[int, _Names], casts: _Casts
) -> CharacterMatch | None:
    if character.detail is None:
        return None

    names = _Names.of([character.name, character.real_name or "", *character.aliases])
    keys = {key for issue in character.detail.issues if (key := _comicvine_key(issue))}
    found = [cast for key in keys if (cast := casts.in_issue(key)) is not None]
    shared = Counter(
        page for cast in found for page in cast if names.words & page_names[page].words
    )
    if not shared:
        return None

    overlap = {
        page: count / (len(found) + casts.appearances[page] - count)
        for page, count in shared.items()
    }
    rank = {
        page: (bool(names.whole & page_names[page].whole), overlap[page])
        for page in shared
    }
    best = max(rank, key=rank.__getitem__)
    if list(rank.values()).count(rank[best]) > 1:
        return None  # the issues and names can't tell the top pages apart
    return CharacterMatch(best, character.id, overlap[best])


def _fandom_names(page: Character) -> list[str]:
    """Every name the Fandom page gives the character."""
    return [
        *_nickname_forms(page.name),
        page.current_alias or "",
        page.title,  # its reality is a parenthetical, which `_key` drops
        *re.split(r"[\n,;]", page.aliases or ""),
    ]


def _nickname_forms(name: str) -> list[str]:
    """'Katherine Anne "Kitty" Pryde' as "Katherine Anne Pryde" and "Kitty Pryde"."""
    match = NICKNAME.fullmatch(name)
    if match is None:
        return [name]

    surname = match["last"].split()[-1:]
    return [f"{match['first']} {match['last']}", " ".join([match["nick"], *surname])]


def _comic_key(comic: Comic) -> IssueKey | None:
    match = COMIC_TITLE.fullmatch(comic.title)
    if match is None or not comic.year:
        return None
    return _issue_key(match["series"], match["number"], comic.year.strip()[:4])


def _comicvine_key(issue: ComicVineIssue) -> IssueKey | None:
    if issue.cover_date is None:
        return None
    return _issue_key(issue.series, issue.number, issue.cover_date[:4])


def _issue_key(series: str, number: str, year: str) -> IssueKey:
    # Comic Vine says "The Incredible Hulk" where Fandom says "Incredible Hulk".
    return _key(series).removeprefix("the "), number, year


def _key(name: str) -> str:
    """A name compared loosely: no case, punctuation or parenthetical."""
    name = re.sub(r"\([^)]*\)", " ", name).replace("&", " and ").replace("'", "")
    return " ".join(re.sub(r"[^a-z0-9]+", " ", name.lower()).split())
