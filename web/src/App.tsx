import { useReducer, useState, type FormEvent } from "react";
import { AnswerText } from "./AnswerText";
import { Logo } from "./Logo";
import { idle, reduce, type Answer } from "./session";
import { Timeline } from "./Timeline";
import { ask } from "./stream";

export function App() {
  const [session, dispatch] = useReducer(reduce, idle);
  const [question, setQuestion] = useState("");
  const running = session.status === "asking";

  async function submit(event: FormEvent) {
    event.preventDefault();
    dispatch({ type: "asked", question });

    try {
      for await (const agentEvent of ask(question)) {
        dispatch({ type: "event", event: agentEvent });
      }
      dispatch({ type: "ended" });
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      dispatch({ type: "failed", message });
    }
  }

  return (
    <div className="page">
      <header className="masthead">
        <Logo />
        <div>
          <h1>Cerebro</h1>
          <p>Answers about Marvel characters, teams and comics, with a citation for every claim</p>
        </div>
      </header>

      <main>
        <form className="ask" onSubmit={submit}>
          <input
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            maxLength={500}
            required
            placeholder="Ask about a Marvel character, team or comic"
            aria-label="Question"
          />
          <button disabled={running}>Ask</button>
        </form>

        {session.question && <h2 className="question">{session.question}</h2>}
        {session.status !== "idle" && <Timeline session={session} />}
        {session.answer && <Result answer={session.answer} unchecked={session.unchecked} />}
        {session.error && (
          <p className="error" role="alert">
            {session.error}
          </p>
        )}
      </main>

      <footer className="credits">
        <p>
          Pages from the <a href="https://marvel.fandom.com">Marvel Database</a> on Fandom (CC
          BY-SA) and records from <a href="https://comicvine.gamespot.com">Comic Vine</a>. A
          non-commercial fan project, not affiliated with Marvel.
        </p>
      </footer>
    </div>
  );
}

function Result({ answer, unchecked }: { answer: Answer; unchecked: boolean }) {
  return (
    <section className="result">
      <AnswerText text={answer.text} sources={answer.sources} />
      {unchecked && <p className="unchecked">Not double-checked: the answer check couldn't run.</p>}

      <ol className="sources">
        {answer.sources.map((source) => (
          <li key={source.url}>
            <a href={source.url} target="_blank" rel="noreferrer">
              {source.title}
            </a>
          </li>
        ))}
      </ol>

      <p className="cost">
        {answer.model_calls} model calls, {answer.tool_calls} tool calls,{" "}
        {answer.input_tokens.toLocaleString()} tokens in, {answer.output_tokens.toLocaleString()}{" "}
        out, {Math.round(answer.seconds)} s
      </p>
    </section>
  );
}
