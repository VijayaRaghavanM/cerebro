import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { AnswerText } from "./AnswerText";

const sources = [{ title: "Avengers", url: "https://wiki/Avengers_(Earth-616)" }];

function render(text: string) {
  return renderToStaticMarkup(<AnswerText text={text} sources={sources} />);
}

describe("AnswerText", () => {
  it("renders bold as strong", () => {
    expect(render("Made by **Chris Claremont**.")).toContain("<strong>Chris Claremont</strong>");
  });

  it("renders a citation as one new-tab link to the whole URL", () => {
    const html = render("Founded in 1963 [1].");

    expect(html.match(/<a /g)).toHaveLength(1);
    expect(html).toContain('href="https://wiki/Avengers_(Earth-616)"');
    expect(html).toContain('target="_blank"');
    expect(html).toContain('rel="noreferrer"');
    expect(html).toContain(">[1]</a>");
  });

  it("does not link [?]", () => {
    expect(render("Unsure [?].")).not.toContain("<a ");
  });

  it("does not render raw HTML as an element", () => {
    expect(render("<img src=x onerror=alert(1)>")).not.toContain("<img");
  });
});
