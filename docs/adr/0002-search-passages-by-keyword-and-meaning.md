# 2. Search passages by keyword and meaning together

- **Date:** 2026-11-16
- **Status:** accepted

## Decision

`search_text` fuses two rankings of the same passages: BM25 over the passage text (SQLite FTS5) and `nomic-embed-text` vectors, the top 100 of each, by reciprocal rank fusion (each list adds `1 / (60 + rank)`). Then passages from main-reality (Earth-616) character pages come first, taking turns with comic passages, unless the query names a reality. Without `OLLAMA_BASE_URL` the search is keyword alone.

Name search (`search_pages`) is a separate tool and is not part of this decision.

## Reasoning

- **Keywords miss what a question describes without naming.** On the 87 golden questions whose expected page has passages, the expected page was in the top 5 for 25% of them with BM25, 38% with vectors and 43% fused (fused minus BM25: +17 points, 95% interval +8 to +28). In the top 20: 47% with BM25, 71% fused. "Is the Hulk technically a mutant?" finds Bruce Banner first when fused; BM25 doesn't have him in its top 20.
- **Vectors alone mix up realities.** On 300 test queries with the character's names taken out, vectors found the right page in the top 20 for 20 points fewer queries than BM25, often picking the same character from another Earth. Fused, the search kept BM25's level on those queries.
- **It holds up end to end.** With the same model and questions, scored under the same rules, the agent solved 74 of 122 with fused search and 69 with keyword search in the first evaluation, and 86 against 82 after the reliability round.
- **Main reality first.** Alternate realities copy a character's text almost word for word, so a plain ranking serves them as often as the main page. On 2,763 keyword queries (921 characters, three topics each), the right passage was in the top 5 for 75% with main-reality passages first, against 46% without.
- **Comics take turns.** With comic passages in the search, all 8 questions of a small test batch found the comic they asked about in the top 5, against none before. A comic's synopsis can repeat a name many times, though, and in one merged list it pushed character pages out: 27 of 60 earlier questions found their expected page in the top 5, against 31 before comics. Taking turns brought that back to 29.
- **The fusion constant is not tuned.** 60 is the value from the original paper (Cormack and others, 2009).
- **Rejected: prefixes written by a language model.** Prefixing every passage with its page and section gained about 4 points of BM25 recall when names were missing and nothing for vectors, at the cost of a model call per passage. A templated prefix gained nothing.
- **Cost.** Search needs an embedding server, and the vectors (about 1 GB) load once per process. A replay needs neither: the run's query vectors are recorded with it.
- **Weak spot.** A passage near the top of only one list scores about half as much as one in both, so fusion can drop a page that one list alone ranked well: Peter Parker's page was 14th with BM25 and 9th with vectors, but missed the fused top 20.
