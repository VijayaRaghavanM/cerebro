from cerebro.domain.answers import Answer, Source
from cerebro.domain.evaluation import GoldenQuestion, Outcome, Split


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
