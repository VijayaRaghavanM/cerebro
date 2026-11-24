import { Icon } from "./Icon";

export function Failure({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className="failure" role="alert">
      <Icon name="problem" />
      <div className="failure-text">
        <p className="failure-title">Couldn't get an answer</p>
        <p>{message}</p>
      </div>
      <button type="button" onClick={onRetry}>
        Try again
      </button>
    </div>
  );
}
