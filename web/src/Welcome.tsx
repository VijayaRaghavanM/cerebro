import { Icon, type IconName } from "./Icon";

// Questions written for the evaluation set, which the agent answered with citations in
// the golden run.
export const EXAMPLES = [
  "Who penciled the comic in which Thanos first appeared?",
  "Who created Iron Fist, and do the wiki and Comic Vine agree?",
  "Who has more comic appearances on Comic Vine, Spider-Man or Wolverine?",
  "Who wrote the comic in which Hope Summers first appeared?",
];

const HOW: { icon: IconName; title: string; text: string }[] = [
  { icon: "search", title: "Searches", text: "Finds pages by their names or by what they say." },
  {
    icon: "page",
    title: "Reads",
    text: "Reads wiki pages and the Comic Vine records matched to them.",
  },
  {
    icon: "passed",
    title: "Cites",
    text: "Links each claim to its record, and says so when the records don't hold the answer.",
  },
];

export function Welcome({ onPick }: { onPick: (question: string) => void }) {
  return (
    <section className="welcome" aria-labelledby="examples-title">
      <h2 id="examples-title">Try a question</h2>
      <ul className="examples">
        {EXAMPLES.map((example) => (
          <li key={example}>
            <button type="button" onClick={() => onPick(example)}>
              {example}
            </button>
          </li>
        ))}
      </ul>

      <ul className="how" aria-label="How Cerebro answers">
        {HOW.map((item) => (
          <li key={item.title}>
            <Icon name={item.icon} />
            <h3>{item.title}</h3>
            <p>{item.text}</p>
          </li>
        ))}
      </ul>
    </section>
  );
}
