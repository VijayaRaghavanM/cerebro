import Markdown from "react-markdown";
import { linkCitations } from "./citations";
import type { Source } from "./stream";

// react-markdown escapes raw HTML, which matters because answers quote wiki text.
export function AnswerText({ text, sources }: { text: string; sources: Source[] }) {
  return (
    <div className="answer">
      <Markdown
        components={{
          a: ({ node, ...props }) => <a {...props} target="_blank" rel="noreferrer" />,
        }}
      >
        {linkCitations(text, sources)}
      </Markdown>
    </div>
  );
}
