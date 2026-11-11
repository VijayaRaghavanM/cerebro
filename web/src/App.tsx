import { useReducer, useState, type FormEvent } from "react";
import { splitCitations } from "./citations";
import { idle, reduce, type Answer, type Step } from "./session";
import { ask } from "./stream";

export function App() {
  const [session, dispatch] = useReducer(reduce, idle);
  const [question, setQuestion] = useState("");
  const running = session.status === "asking";

  async function submit(event: FormEvent) {
    event.preventDefault();
    dispatch({ type: "asked" });

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
    <main>
      <h1>Cerebro</h1>
      <p>
        Answers questions about Marvel characters, teams and comics from the Marvel Database,
        with citations.
      </p>

      <form onSubmit={submit}>
        <input
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          maxLength={500}
          required
          aria-label="Question"
        />
        <button disabled={running}>Ask</button>
      </form>

      <Trace steps={session.trace} />
      {running && <p>Working...</p>}
      {session.answer && <Result answer={session.answer} />}
      {session.error && <p role="alert">{session.error}</p>}
    </main>
  );
}

function Trace({ steps }: { steps: Step[] }) {
  return (
    <ul className="trace">
      {steps.map((step, index) => (
        <li key={index}>
          {step.label}
          {step.reply && <span>{step.reply}</span>}
        </li>
      ))}
    </ul>
  );
}

function Result({ answer }: { answer: Answer }) {
  const parts = splitCitations(answer.text, answer.sources);

  return (
    <section>
      <p className="answer">
        {parts.map((part, index) =>
          part.kind === "citation" ? (
            <a key={index} href={part.url} target="_blank" rel="noreferrer">
              {part.label}
            </a>
          ) : (
            part.text
          ),
        )}
      </p>

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
