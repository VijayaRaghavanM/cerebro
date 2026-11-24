import { Icon, Spinner, type IconName } from "./Icon";
import type { Session, Step } from "./session";
import { describeCheck, describeTool, waitingOnTool } from "./steps";

const ICONS: Record<string, IconName> = {
  search_pages: "search",
  search_text: "passages",
  read_page: "page",
  find_appearances: "comics",
  reading_order: "order",
  compare_characters: "compare",
};

export function Timeline({ session }: { session: Session }) {
  const { trace } = session;
  const asking = session.status === "asking";
  const waiting = waitingOnTool(session);
  const tools = trace.filter((step) => step.tool !== "check_answer").length;

  return (
    <section className="steps" aria-labelledby="steps-title" aria-busy={asking}>
      <div className="steps-head">
        <h3 id="steps-title">Steps</h3>
        <span>{tools === 1 ? "1 tool call" : `${tools} tool calls`}</span>
      </div>

      <ol className="timeline">
        {trace.map((step, index) => {
          if (step.tool === "check_answer") {
            const afterRetry = trace.slice(0, index).some((s) => s.tool === "check_answer");
            return <CheckRow key={index} step={step} afterRetry={afterRetry} />;
          }

          const running = waiting && index === trace.length - 1;
          return <ToolRow key={index} step={step} running={running} />;
        })}

        {asking && !waiting && (
          <li className="step is-running">
            <span className="step-icon">
              <Spinner />
            </span>
            <div className="step-body">
              <span className="step-title">Working out the next step</span>
            </div>
          </li>
        )}
      </ol>
    </section>
  );
}

function ToolRow({ step, running }: { step: Step; running: boolean }) {
  const view = describeTool(step, running);
  const argument = view.quoted ? `“${step.argument}”` : step.argument;

  const head = (
    <span className="step-head">
      <span className="step-title">
        {view.action} <span className="step-argument">{argument}</span>
      </span>
      {view.finding && <span className="step-finding">{view.finding}</span>}
      {view.records.length > 0 && (
        <span className="records">
          {view.records.map((title) => (
            <span key={title} className="record">
              {title}
            </span>
          ))}
        </span>
      )}
    </span>
  );

  return (
    <li className={running ? "step is-running" : "step"}>
      <span className="step-icon">
        {running ? <Spinner /> : <Icon name={ICONS[step.tool] ?? "tool"} />}
      </span>

      {step.reply === null ? (
        <div className="step-body">{head}</div>
      ) : (
        <details className="step-body">
          <summary>
            {head}
            <span className="chevron">
              <Icon name="chevron" />
            </span>
          </summary>
          <div className="output">
            <p className="output-head">
              What <code>{step.tool}</code> returned, {step.reply.length.toLocaleString()}{" "}
              characters
            </p>
            <pre>{step.reply}</pre>
          </div>
        </details>
      )}
    </li>
  );
}

function CheckRow({ step, afterRetry }: { step: Step; afterRetry: boolean }) {
  const view = describeCheck(step, afterRetry);

  return (
    <li className={`step is-${view.tone}`}>
      <span className="step-icon">
        <Icon name={view.tone} />
      </span>
      <div className="step-body">
        <span className="step-head">
          <span className="step-title">{view.title}</span>
          <span className="step-finding">{view.finding}</span>
        </span>
        {step.reply && <p className="check-note">{step.reply}</p>}
        {view.next && <p className="check-next">{view.next}</p>}
      </div>
    </li>
  );
}
