import { useReducer, useState, type FormEvent } from "react";
import { Logo } from "./Logo";
import { Result } from "./Result";
import { checkOutcome, idle, reduce } from "./session";
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
        {session.answer && <Result answer={session.answer} check={checkOutcome(session.trace)} />}
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
