"""Put several scored runs side by side in one Markdown report."""

from collections.abc import Mapping

from cerebro.application.agreement import check_agreement
from cerebro.application.report import dollars, percent, render_table
from cerebro.application.scoring import score_results, summarise
from cerebro.domain.evaluation import GoldenQuestion
from cerebro.domain.scoring import Price, Summary
from cerebro.ports.evaluation import RunStore

OVERALL = (
    "Run",
    "Model",
    "Questions",
    "Solved",
    "Judge correct",
    "Fact recall",
    "Citation recall",
    "Citation precision",
    "Refusals right",
    "Mean seconds",
    "Mean tokens",
    "Cost",
    "Cost per solved",
)


class RunEmpty(Exception):
    """A run has no results to compare. The message is its name."""


def compare_runs(
    questions: list[GoldenQuestion],
    stores: Mapping[str, RunStore],
    prices: Mapping[str, Price],
) -> str:
    """Markdown comparing runs, each scored as `score_run` scores it: a table with
    a row per run, a table of the questions solved in each category, and a line per
    run that has hand labels saying how well the judge agrees with them.

    `stores` is keyed by run name, in the order the runs are shown. Raises RunEmpty
    if a run has no results that are still golden questions.
    """
    summaries: dict[str, list[Summary]] = {}
    models: dict[str, str] = {}
    for name, store in stores.items():
        scores = score_results(questions, store, prices)
        if not scores:
            raise RunEmpty(name)

        summaries[name] = summarise(scores)
        models[name] = next(iter(store.results())).model

    overall = render_table(
        OVERALL,
        [_row(name, models[name], runs[-1]) for name, runs in summaries.items()],
    )
    categories = render_table(
        ["Category", *summaries],
        _category_rows(summaries),
    )
    sections = [overall, categories]

    agreement = [_agreement_line(name, store) for name, store in stores.items()]
    labelled = [line for line in agreement if line is not None]
    if labelled:
        sections.append("\n".join(labelled) + "\n")

    return "\n".join(sections)


def _row(name: str, model: str, overall: Summary) -> list[str]:
    return [
        name,
        model,
        str(overall.questions),
        f"{overall.solved} ({percent(overall.solved, overall.questions)})",
        percent(overall.judge_correct, overall.judged),
        percent(overall.facts_found, overall.facts_expected),
        percent(overall.pages_cited, overall.pages_expected),
        percent(overall.pages_cited, overall.cited_total),
        percent(overall.refusals_right, overall.questions),
        f"{overall.seconds / overall.questions:.1f}",
        f"{overall.tokens / overall.questions:.0f}",
        dollars(overall.cost),
        dollars(overall.cost / overall.solved) if overall.solved else "-",
    ]


def _category_rows(summaries: Mapping[str, list[Summary]]) -> list[list[str]]:
    # Each run's last summary is its overall one, which is not a category.
    solved: dict[str, dict[str, Summary]] = {}
    for run, run_summaries in summaries.items():
        for summary in run_summaries[:-1]:
            solved.setdefault(summary.name, {})[run] = summary

    return [
        [category, *[_solved_in(by_run.get(run)) for run in summaries]]
        for category, by_run in solved.items()
    ]


def _solved_in(summary: Summary | None) -> str:
    # A run that was not asked any question in the category has no cell for it.
    if summary is None:
        return "-"

    return f"{summary.solved} of {summary.questions}"


def _agreement_line(name: str, store: RunStore) -> str | None:
    report = check_agreement(store)
    if report.compared == 0:
        return None

    if report.kappa is None:
        kappa = "kappa undefined"
    else:
        kappa = f"kappa {report.kappa:.2f}"

    return (
        f"{name}: judge agrees with labels on {report.agreement:.0%}, {kappa}, "
        f"{report.compared} compared"
    )
