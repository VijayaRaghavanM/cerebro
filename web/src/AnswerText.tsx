import { useMemo, type ComponentProps } from "react";
import Markdown, { type Components } from "react-markdown";
import { linkCitations, origin } from "./citations";
import type { Source } from "./stream";

// The text linkCitations gives a citation's link.
const MARKER = /^\[(\d+)\]$/;

// Called with a citation's number while it is pointed at or focused, then null.
type OnCite = (number: number | null) => void;

// react-markdown escapes raw HTML, which matters because answers quote wiki text.
export function AnswerText(props: { text: string; sources: Source[]; onCite?: OnCite }) {
  const { text, sources, onCite } = props;

  // Kept across renders: a new renderer each time would make React replace every
  // link once a citation lights up its source, and the link would lose focus.
  const components = useMemo<Components>(
    () => ({
      a: ({ node, ...link }) => {
        const marker = String(link.children).match(MARKER);
        const number = marker ? Number(marker[1]) : 0;
        const source = sources[number - 1];
        if (!source) return <a {...link} target="_blank" rel="noreferrer" />;

        return <Citation link={link} number={number} source={source} onCite={onCite} />;
      },
    }),
    [sources, onCite],
  );

  return (
    <div className="answer">
      <Markdown components={components}>{linkCitations(text, sources)}</Markdown>
    </div>
  );
}

type CitationProps = {
  link: ComponentProps<"a">;
  number: number;
  source: Source;
  onCite?: OnCite;
};

function Citation({ link, number, source, onCite }: CitationProps) {
  const { site, name } = origin(source.title);

  return (
    <a
      {...link}
      className="cite"
      target="_blank"
      rel="noreferrer"
      title={`${site}: ${name}`}
      aria-label={`Source ${number}: ${name}, ${site}`}
      onMouseEnter={() => onCite?.(number)}
      onMouseLeave={() => onCite?.(null)}
      onFocus={() => onCite?.(number)}
      onBlur={() => onCite?.(null)}
    />
  );
}
