"""A run's scores as a table to read."""

from collections.abc import Sequence

from cerebro.domain.scoring import Summary

COLUMNS = (
    "Category",
    "Questions",
    "Solved",
    "Fact recall",
    "Judge correct",
    "Citation recall",
    "Citation precision",
    "Tool selection",
    "Refusals right",
    "Mean seconds",
    "Mean tokens",
    "Cost",
    "Cost per solved",
)


# Nobody has yet compared the judge's rulings with answers labelled by hand.
PROVISIONAL = (
    "Judge scores (Judge correct, and Solved where the judge ruled) are "
    "provisional until checked against labels."
)


def render_report(summaries: list[Summary]) -> str:
    """A Markdown table with a row per summary. When the judge ruled on any answer,
    a line above it says its scores are provisional.
    """
    table = render_table(COLUMNS, [_cells(summary) for summary in summaries])

    if not any(summary.judged for summary in summaries):
        return table

    return f"{PROVISIONAL}\n\n{table}"


def render_table(header: Sequence[str], rows: Sequence[Sequence[str]]) -> str:
    """A Markdown table, ending in a newline."""
    divider = "|" + " --- |" * len(header)
    head, *body = ["| " + " | ".join(cells) + " |" for cells in [header, *rows]]

    return "\n".join([head, divider, *body]) + "\n"


def overall_line(summary: Summary) -> str:
    """The totals in one line."""
    return (
        f"{summary.solved} of {summary.questions} solved, "
        f"fact recall {percent(summary.facts_found, summary.facts_expected)}, "
        f"cost {dollars(summary.cost)}"
    )


def _cells(summary: Summary) -> list[str]:
    return [
        summary.name,
        str(summary.questions),
        str(summary.solved),
        percent(summary.facts_found, summary.facts_expected),
        percent(summary.judge_correct, summary.judged),
        percent(summary.pages_cited, summary.pages_expected),
        percent(summary.pages_cited, summary.cited_total),
        percent(summary.tools_used, summary.tools_expected),
        percent(summary.refusals_right, summary.questions),
        f"{summary.seconds / summary.questions:.1f}",
        f"{summary.tokens / summary.questions:.0f}",
        dollars(summary.cost),
        dollars(summary.cost / summary.solved) if summary.solved else "-",
    ]


def percent(part: int, whole: int) -> str:
    # Nothing was expected, so there is nothing to recall.
    if whole == 0:
        return "-"

    return f"{part / whole:.0%}"


def dollars(amount: float) -> str:
    return f"${amount:.4f}"
