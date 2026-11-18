from cerebro.domain.answers import Answer, Source, is_comic_vine
from cerebro.domain.evaluation import GoldenQuestion, Outcome, Split
from cerebro.ports.evaluation import CitedPages


class FakePages(CitedPages):
    """A wiki page stands for itself; a Comic Vine record for the page `matches`
    pairs its url with, if any."""

    def __init__(self, matches: dict[str, str] | None = None) -> None:
        self.matches = matches or {}

    def page(self, source: Source) -> str | None:
        if not is_comic_vine(source):
            return source.title
        return self.matches.get(source.url)


PAGES = FakePages()


def golden_question(id: str, split: Split = Split.DEV) -> GoldenQuestion:
    return GoldenQuestion(
        id=id,
        split=split,
        category="identity",
        question=f"Question {id}?",
        expected_outcome=Outcome.ANSWER,
        expected_facts=("James Howlett",),
        expected_pages=("James Howlett (Earth-616)",),
        expected_tools=("search_pages", "read_page"),
        source="made up",
        source_url="https://example.test/q",
        license="CC0",
    )


# The same question as golden_question, as a line of the golden file.
def golden_line(id: str, split: str = "dev", **extra: object) -> dict[str, object]:
    return {
        "id": id,
        "split": split,
        "category": "identity",
        "question": f"Question {id}?",
        "expected_outcome": "answer",
        "expected_facts": ["James Howlett"],
        "expected_pages": ["James Howlett (Earth-616)"],
        "expected_tools": ["search_pages", "read_page"],
        "source": "made up",
        "source_url": "https://example.test/q",
        "license": "CC0",
        **extra,
    }


def answer(text: str = "James Howlett [1].") -> Answer:
    return Answer(
        text=text,
        sources=(Source("James Howlett (Earth-616)", "https://example.test/a"),),
        model_calls=3,
        tool_calls=2,
        input_tokens=1200,
        output_tokens=40,
        seconds=12.5,
    )
