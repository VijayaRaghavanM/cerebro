import { AnswerText } from "./AnswerText";
import { origin } from "./citations";
import { Icon } from "./Icon";
import type { Answer, CheckOutcome } from "./session";
import type { Source } from "./stream";

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

        {answer.sources.length > 0 && <Sources sources={answer.sources} />}

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

function Sources({ sources }: { sources: Source[] }) {
  return (
    <div className="sources">
      <h4>Sources</h4>
      <ol>
        {sources.map((source, index) => {
          const { kind, site, name } = origin(source.title);

          return (
            <li key={source.url}>
              <span className="source-number">{index + 1}</span>
              <a href={source.url} target="_blank" rel="noreferrer">
                <span className="source-name">{name}</span>
                <span className={`site is-${kind}`}>{site}</span>
                <Icon name="external" />
              </a>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
