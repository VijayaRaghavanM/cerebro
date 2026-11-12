<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="assets/logo-dark.svg">
    <img src="assets/logo-light.svg" alt="Cerebro logo" width="128">
  </picture>
</p>

# Cerebro

A research agent that answers questions about Marvel characters, teams and comics, with citations, plus the evaluation suite that measures how often it is right.

The agent searches a local copy of the Marvel Database wiki and Comic Vine, calls tools to look things up, and cites the record behind every claim. The evaluation suite runs a fixed set of questions, each checked against the records, against several models and reports correctness, grounding, refusals, latency and cost per solved question.

Status: early. The data pipeline runs, and the agent answers questions with citations, in the CLI or on a local chat page that shows each tool call as it happens. The evaluation suite answers the golden questions with a chosen model, has a second model judge the answers, and scores them. Results of the first full evaluation, four models in five runs, are in [RESULTS.md](RESULTS.md).

## Development

Requires [uv](https://docs.astral.sh/uv/).

```sh
uv sync                          # create .venv and install the pinned dependencies
uv run pytest                    # run the tests
uv run pytest -m live            # check API keys against the real services
uv run ruff check                # lint
uv run ruff format               # format
uv run cerebro crawl fandom      # download raw wiki pages; safe to rerun
uv run cerebro crawl comicvine   # download Comic Vine's Marvel characters; safe to rerun (needs COMICVINE_API_KEY)
uv run cerebro parse fandom      # turn them into records in data/records.sqlite
uv run cerebro chunk             # cut the parsed character pages into chunks for search
uv run cerebro embed             # embed every chunk; safe to resume (needs OLLAMA_BASE_URL)
uv run cerebro load comicvine    # store Comic Vine's characters next to them
uv run cerebro match comicvine   # match Comic Vine's characters to the parsed ones
uv run cerebro ask "..."         # answer a question, with citations (needs MISTRAL_API_KEY)
```

CI runs these checks and replays a recorded evaluation on every push, so a tool that changes what the model sees fails it.

To evaluate a model, answer the golden questions in `evals/golden.jsonl`, judge the answers, then score them. Each run keeps its results in `runs/<run>/`. `eval run --help` lists the models: the `-openrouter` ones need `OPENROUTER_API_KEY`, `ministral-14b` needs `MISTRAL_API_KEY`, and `qwen3-14b-ollama` needs `OLLAMA_BASE_URL`, which also adds vector search to the keyword search.

```sh
uv run cerebro eval run --model ministral-14b-openrouter --run m14   # answer the questions; safe to rerun
uv run cerebro eval judge m14        # have the judge rule on each answer (needs CEREBRAS_API_KEY)
uv run cerebro eval score m14        # write scores.json and report.md
uv run cerebro eval replay m14       # rerun it offline from the saved model exchanges
uv run cerebro eval agreement m14    # check the judge against labels in runs/m14/labels.jsonl
uv run cerebro eval compare m14 m3   # put runs side by side, as Markdown
```

To use the chat page, start the API and then the page, which needs Node 22 (`nvm use` reads it from `web/.nvmrc`):

```sh
uv run cerebro serve             # the question API, on port 8000
cd web && nvm use && npm install && npm run dev
```

Open the address Vite prints. Vite sends `/ask` to the API.

## Data and credits

- Character, team and comic pages, including comic creators and appearances, come from the [Marvel Database](https://marvel.fandom.com) on Fandom, licensed under [CC BY-SA](https://creativecommons.org/licenses/by-sa/3.0/). Text derived from it keeps that license.
- Issue dates and per-character issue lists come from the [Comic Vine API](https://comicvine.gamespot.com/api/) under its terms for non-commercial use. It is not redistributed here. `cerebro crawl comicvine` fetches it with your own API key.

- The evaluation questions in `evals/golden.jsonl` include questions people asked on [Science Fiction & Fantasy Stack Exchange](https://scifi.stackexchange.com) (CC BY-SA 4.0), in [Natural Questions](https://ai.google.com/research/NaturalQuestions) (CC BY-SA 3.0) and in [WebQuestions](https://nlp.stanford.edu/software/sempre/) (CC BY 4.0). Each line names its source, link and license; questions marked `cerebro` were written for this project.

This is a non-commercial fan project. It is not affiliated with or endorsed by Marvel, Fandom or Comic Vine.

## License

Code is MIT licensed. See [LICENSE](LICENSE).
