"""What a run scores on each golden question, and the totals."""

from dataclasses import dataclass

from cerebro.domain.evaluation import Outcome


@dataclass(frozen=True)
class Price:
    """What a model charges, in dollars per million tokens."""

    input: float
    output: float


@dataclass(frozen=True)
class Score:
    """How one result measures against its golden question. Each pair is the
    count that passed and the count that could have.
    """

    question_id: str
    category: str
    expected: Outcome
    observed: Outcome
    facts_found: int
    facts_expected: int
    pages_cited: int  # the cited pages that are expected ones
    pages_expected: int
    cited_total: int  # pages cited; Comic Vine sources are in neither count
    tools_used: int  # expected tools the agent called
    tools_expected: int
    in_order: bool  # the expected tools it called came in the expected order
    seconds: float
    input_tokens: int
    output_tokens: int
    cost: float  # dollars
    solved: bool


@dataclass(frozen=True)
class Summary:
    """The scores of one category, or of all of them, added up."""

    name: str
    questions: int
    solved: int
    facts_found: int
    facts_expected: int
    pages_cited: int
    pages_expected: int
    cited_total: int
    tools_used: int
    tools_expected: int
    refusals_right: int  # questions where refusing, or not, was what was expected
    seconds: float
    tokens: int  # input and output
    cost: float
