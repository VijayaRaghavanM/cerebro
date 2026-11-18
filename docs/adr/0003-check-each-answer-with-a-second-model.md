# 3. Check each answer with a second model

- **Date:** 2026-11-18
- **Status:** accepted

## Decision

Before an answer is shown, Gemini 3.8 Flash reads the question, every tool call and reply, and the answer. It returns one verdict:

- **answers:** every claim the answer depends on is in the tool output, and the output is about what the question asks.
- **off_target:** the claims are in the tool output, but it is about something else, such as another reality's version or a different comic.
- **unsupported:** a claim the answer depends on is missing from the tool output, or the output contradicts it.

The agent's reply is checked only when it is an answer; refusals, clarifying questions and replies that ran out of tool calls go out as they are. A problem gets one more try, with the checker's note on what is missing. A second problem turns the answer into "I couldn't find that in the records."

The check is optional. Without `GEMINI_API_KEY` it is off. When it can't run, the answer goes out unchecked, and the trace says so. That happens when Gemini doesn't reply within 20 seconds, when it returns an error a retry won't fix, or after three failed checks in a row, which rest the check for five minutes.

## Reasoning

- **Wrong answers came with citations.** In the first evaluation, 22 of Ministral 14B's 93 answers were wrong. An answer without a citation already becomes a refusal, so every one of them cited a page; the citation alone doesn't show the page says what the answer claims.
- **Gemini caught every wrong answer in a test.** On 20 recorded answers, 8 of them wrong, Gemini 3.8 Flash flagged all 8 and also flagged 2 of the 12 right ones. Ministral 14B checking its own answers caught 5 of the 8, and qwen3 14B caught 6.
- **One more try, then refuse.** When the first check found an unsupported claim, the retry fixed the answer 7 times out of 19, and 11 ended in a refusal. Off-target answers were fixed once out of 8, and the other 7 ended in a refusal. A refusal costs less than a wrong answer that looks right.
- **It judges against the evidence, not memory.** The checker is told not to use its own knowledge of Marvel comics, so it checks what the agent read, the same rule the answer has to meet.
- **An outage lets answers through, marked.** Refusing whenever the check can't run would turn every Gemini outage into a wall of "I couldn't find that". The trace marks unchecked answers, so an evaluation counts them.
- **Cost.** A check takes about 4 seconds. With the check on, answers on OpenRouter took 10.3 seconds on average, against 4.2 without it in the first evaluation; the tools also changed in between. Gemini's free tier covers the checks.
- **Rejected: a backup checker.** It would be a second service to run, and the best of the other models tried caught 6 of the 8 wrong answers.
- **Weak spot.** The checker sees only what the agent found. If the agent reads the wrong page carefully and the question doesn't say which one it means, the answer passes. It also flags some right answers, which then cost a retry or become refusals.
