import { origin } from "./citations";
import { Icon, Spinner } from "./Icon";
import { isCheck, type Session, type Step } from "./session";
import { describeCheck, describeTool, waitingOnTool, type CheckView } from "./steps";

export function Timeline({ session }: { session: Session }) {
  const { trace } = session;
  const asking = session.status === "asking";
  const waiting = waitingOnTool(session);
  const tools = trace.filter((step) => !isCheck(step)).length;

  return (
    <section className="steps" aria-labelledby="steps-title" aria-busy={asking}>
      <div className="steps-head">
        <h3 id="steps-title">Steps</h3>
        {tools > 0 && <span>{tools === 1 ? "1 tool call" : `${tools} tool calls`}</span>}
      </div>

      <ol className="timeline">
        {trace.map((step, index) => {
          if (isCheck(step)) {
            return <CheckRow key={index} step={step} view={describeCheck(trace, index)} />;
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
            <span key={title} className={`record is-${origin(title).kind}`}>
              {title}
            </span>
          ))}
        </span>
      )}
    </span>
  );

  return (
    <li className={running ? "step is-running" : "step"}>
      <span className="step-icon">{running ? <Spinner /> : <Icon name={view.icon} />}</span>

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

function CheckRow({ step, view }: { step: Step; view: CheckView }) {
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
