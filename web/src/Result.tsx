import { AnswerText } from "./AnswerText";
import { Icon } from "./Icon";
import type { Answer, CheckOutcome } from "./session";

const BANNERS = {
  passed: {
    icon: "passed",
    title: "Checked against the records",
    detail: "A second model found every claim in the pages Cerebro read.",
  },
  fixed: {
    icon: "passed",
    title: "Checked against the records on the second try",
    detail: "The check sent the first answer back with a problem. This one passed.",
  },
  unchecked: {
    icon: "unchecked",
    title: "Not double-checked",
    detail: "The answer check couldn't run.",
  },
} as const;

export function Result({ answer, check }: { answer: Answer; check: CheckOutcome }) {
  return (
    <section className="result" aria-labelledby="answer-title">
      {check && <CheckBanner check={check} />}

      <div className="result-body">
        <h3 id="answer-title" className="result-label">
          Answer
        </h3>
        <AnswerText text={answer.text} sources={answer.sources} />

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
      </div>
    </section>
  );
}

function CheckBanner({ check }: { check: NonNullable<CheckOutcome> }) {
  const banner = BANNERS[check];

  return (
    <p className={`check-banner is-${check}`}>
      <Icon name={banner.icon} />
      <span>
        <strong>{banner.title}.</strong> {banner.detail}
      </span>
    </p>
  );
}
