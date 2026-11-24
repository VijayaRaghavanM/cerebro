import { AnswerText } from "./AnswerText";
import type { Answer } from "./session";

export function Result({ answer, unchecked }: { answer: Answer; unchecked: boolean }) {
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
