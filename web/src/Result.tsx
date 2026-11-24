import { useState } from "react";
import { AnswerText } from "./AnswerText";
import { origin } from "./citations";
import { Icon } from "./Icon";
import type { Answer, CheckOutcome } from "./session";
import { REFUSAL, type Source } from "./stream";

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
  // The citation being pointed at, so that its source stands out in the list.
  const [cited, setCited] = useState<number | null>(null);
  const refused = answer.text === REFUSAL;

  return (
    <section className={refused ? "result is-refusal" : "result"} aria-labelledby="answer-title">
      {check && <CheckBanner check={check} />}

      <div className="result-body">
        <h3 id="answer-title" className="result-label">
          {refused ? "No answer" : "Answer"}
        </h3>
        <AnswerText text={answer.text} sources={answer.sources} onCite={setCited} />
        {refused && (
          <p className="refusal-note">
            Cerebro answers only from what its tools return, and gives no answer when that doesn't
            settle the question.
          </p>
        )}

        {answer.sources.length > 0 && <Sources sources={answer.sources} cited={cited} />}

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

function Sources({ sources, cited }: { sources: Source[]; cited: number | null }) {
  return (
    <div className="sources">
      <h4>Sources</h4>
      <ol>
        {sources.map((source, index) => {
          const { kind, site, name } = origin(source.title);

          return (
            <li key={source.url} className={index + 1 === cited ? "is-cited" : undefined}>
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
