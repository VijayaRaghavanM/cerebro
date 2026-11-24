import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { Failure } from "./Failure";

describe("Failure", () => {
  it("alerts with the server's message and offers to ask again", () => {
    const message = "The model provider is rate limiting requests; try again in a minute.";
    const html = renderToStaticMarkup(<Failure message={message} onRetry={() => {}} />);

    expect(html).toContain('role="alert"');
    expect(html).toContain(message);
    expect(html).toContain(">Try again</button>");
  });
});
