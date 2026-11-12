"""A run's scores as a table to read."""

from cerebro.domain.scoring import Summary

COLUMNS = (
    "Category",
    "Questions",
    "Solved",
    "Fact recall",
    "Citation recall",
    "Citation precision",
    "Tool selection",
    "Refusals right",
    "Mean seconds",
    "Mean tokens",
    "Cost",
    "Cost per solved",
)


def render_report(summaries: list[Summary]) -> str:
    """A Markdown table with a row per summary."""
    header = "| " + " | ".join(COLUMNS) + " |"
    divider = "|" + " --- |" * len(COLUMNS)
    rows = ["| " + " | ".join(_cells(summary)) + " |" for summary in summaries]

    return "\n".join([header, divider, *rows]) + "\n"


def overall_line(summary: Summary) -> str:
    """The totals in one line."""
    return (
        f"{summary.solved} of {summary.questions} solved, "
        f"fact recall {_percent(summary.facts_found, summary.facts_expected)}, "
        f"cost {_dollars(summary.cost)}"
    )


def _cells(summary: Summary) -> list[str]:
    return [
        summary.name,
        str(summary.questions),
        str(summary.solved),
        _percent(summary.facts_found, summary.facts_expected),
        _percent(summary.pages_cited, summary.pages_expected),
        _percent(summary.pages_cited, summary.cited_total),
        _percent(summary.tools_used, summary.tools_expected),
        _percent(summary.refusals_right, summary.questions),
        f"{summary.seconds / summary.questions:.1f}",
        f"{summary.tokens / summary.questions:.0f}",
        _dollars(summary.cost),
        _dollars(summary.cost / summary.solved) if summary.solved else "-",
    ]


def _percent(part: int, whole: int) -> str:
    # Nothing was expected, so there is nothing to recall.
    if whole == 0:
        return "-"

    return f"{part / whole:.0%}"


def _dollars(amount: float) -> str:
    return f"${amount:.4f}"
