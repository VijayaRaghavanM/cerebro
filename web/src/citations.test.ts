import { describe, expect, it } from "vitest";
import { linkCitations } from "./citations";

const sources = [
  { title: "A", url: "https://wiki/A" },
  { title: "B", url: "https://wiki/Avengers_(Earth-616)" },
];

describe("linkCitations", () => {
  it("turns [n] into a link to the nth source, URL in angle brackets", () => {
    expect(linkCitations("One [1].", sources)).toBe("One [\\[1\\]](<https://wiki/A>).");
  });

  it("links several citations", () => {
    expect(linkCitations("[1] and [2]", sources)).toBe(
      "[\\[1\\]](<https://wiki/A>) and [\\[2\\]](<https://wiki/Avengers_(Earth-616)>)",
    );
  });

  it("leaves [?] and numbers without a source as they are", () => {
    expect(linkCitations("Odd [?] and [3] and [0].", sources)).toBe("Odd [?] and [3] and [0].");
  });
});
