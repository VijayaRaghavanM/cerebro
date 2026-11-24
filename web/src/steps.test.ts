import { describe, expect, it } from "vitest";
import { idle, type Session, type Step } from "./session";
import { describeCheck, describeTool, progress, waitingOnTool } from "./steps";

function step(tool: string, argument: string, reply: string | null = null): Step {
  return { tool, argument, reply };
}

const read = step(
  "read_page",
  "Daniel Rand (Earth-616)",
  "Daniel Rand (Earth-616) (character)\nname: Daniel Thomas Rand\n\n" +
    "Sources: [1] Daniel Rand (Earth-616), [2] Comic Vine: Iron Fist",
);

describe("describeTool", () => {
  it("words a step by its tool, in the present while it runs", () => {
    const search = step("search_pages", "Sunspot");

    expect(describeTool(search, true)).toMatchObject({ action: "Searching page names for" });
    expect(describeTool(search, false)).toMatchObject({ action: "Searched page names for" });
  });

  it("quotes the words of a search but not a title", () => {
    expect(describeTool(step("search_text", "living gold"), false).quoted).toBe(true);
    expect(describeTool(step("read_page", "Thanos (Earth-616)"), false).quoted).toBe(false);
  });

  it("falls back to the tool's own name for a tool it does not know", () => {
    expect(describeTool(step("new_tool", "x"), false).action).toBe("new_tool");
  });

  it("counts the pages a name search found and names the first", () => {
    const reply = '1. "Roberto Da Costa (Earth-616)": character\n2. "Sunspot Vol 1 1": comic';
    const one = '1. "Roberto Da Costa (Earth-616)": character';

    expect(describeTool(step("search_pages", "Sunspot", reply), false).finding).toBe(
      "Found 2 pages, starting with Roberto Da Costa (Earth-616)",
    );
    expect(describeTool(step("search_pages", "Sunspot", one), false).finding).toBe(
      "Found 1 page: Roberto Da Costa (Earth-616)",
    );
  });

  it("keeps a reply's first line when it is not a list, such as a miss", () => {
    const miss = step("search_pages", "Logan", 'No pages match "Logan".');

    expect(describeTool(miss, false).finding).toBe('No pages match "Logan".');
  });

  it("drops the colon that ends a list's heading", () => {
    const reply = "Thanos is in 518 comics; the first 20 by cover date:\nIron Man Vol 1 55";

    expect(describeTool(step("find_appearances", "Thanos", reply), false).finding).toBe(
      "Thanos is in 518 comics; the first 20 by cover date",
    );
  });

  it("names the kind of page read and the other records it may cite", () => {
    expect(describeTool(read, false)).toMatchObject({
      finding: "Character page",
      records: ["Comic Vine: Iron Fist"],
    });
  });

  it("lists each cited record once, keeping commas inside a title", () => {
    const reply =
      "Passage one\n\nPassage two\n\n" +
      "Sources: [1] Peter Parker, The Spectacular Spider-Man Vol 1 1, [2] Hulk, [1] Hulk";

    expect(describeTool(step("search_text", "gamma bomb", reply), false)).toMatchObject({
      finding: "Found passages on 2 pages",
      records: ["Peter Parker, The Spectacular Spider-Man Vol 1 1", "Hulk"],
    });
  });

  it("leaves two compared pages to their records", () => {
    const reply = "A (character)\n\nB (character)\n\nSources: [1] A, [2] B";

    expect(describeTool(step("compare_characters", "A, B", reply), false)).toMatchObject({
      finding: null,
      records: ["A", "B"],
    });
  });
});

describe("describeCheck", () => {
  it("passes an answer the check found backed", () => {
    expect(describeCheck([step("check_answer", "answers")], 0)).toMatchObject({
      tone: "passed",
      next: null,
    });
  });

  it("sends a problem back for one more try, then withholds the answer", () => {
    const unsupported = step("check_answer", "unsupported", "No source names the penciler.");
    const offTarget = step("check_answer", "off_target", "It names another reality's version.");

    expect(describeCheck([read, unsupported], 1)).toMatchObject({
      tone: "problem",
      next: "Sent back to try once more",
    });
    expect(describeCheck([unsupported, read, offTarget], 2)).toMatchObject({
      tone: "problem",
      next: "The answer was withheld",
    });
  });

  it("says when the check could not run", () => {
    expect(describeCheck([step("check_answer", "unchecked")], 0)).toMatchObject({
      title: "Tried to check the answer",
      tone: "unchecked",
    });
  });
});

describe("waitingOnTool", () => {
  const asking: Session = { ...idle, status: "asking" };

  it("waits on the latest tool until its reply comes", () => {
    expect(waitingOnTool({ ...asking, trace: [step("read_page", "A")] })).toBe(true);
    expect(waitingOnTool({ ...asking, trace: [read] })).toBe(false);
  });

  it("never waits on a check, which comes with its verdict", () => {
    expect(waitingOnTool({ ...asking, trace: [read, step("check_answer", "answers")] })).toBe(
      false,
    );
  });

  it("stops waiting once the run has ended", () => {
    const failed: Session = { ...idle, status: "failed", trace: [step("read_page", "A")] };

    expect(waitingOnTool(failed)).toBe(false);
  });
});

describe("progress", () => {
  const asking: Session = { ...idle, status: "asking" };
  const answer = {
    text: "Yes [1].",
    sources: [],
    model_calls: 1,
    tool_calls: 1,
    input_tokens: 1,
    output_tokens: 1,
    seconds: 1,
  };

  it("says which tool is at work, then what it found", () => {
    expect(progress({ ...asking, trace: [step("read_page", "Thanos (Earth-616)")] })).toBe(
      "Reading Thanos (Earth-616)",
    );
    expect(progress({ ...asking, trace: [read] })).toBe(
      "Read Daniel Rand (Earth-616). Character page",
    );
  });

  it("says what a check found and what happens next", () => {
    const problem = step("check_answer", "unsupported", "No source names the penciler.");

    expect(progress({ ...asking, trace: [read, problem] })).toBe(
      "Checked the answer. Found a claim the records don't back. Sent back to try once more",
    );
  });

  it("says when the answer is ready, or that there is none", () => {
    const refusal = { ...answer, text: "I couldn't find that in the records." };

    expect(progress({ ...idle, status: "done", answer })).toBe("Answer ready");
    expect(progress({ ...idle, status: "done", answer: refusal })).toBe("No answer in the records");
  });

  it("stays quiet before a question and after a failure", () => {
    expect(progress(idle)).toBe("");
    expect(progress({ ...idle, status: "failed", trace: [read] })).toBe("");
  });
});
