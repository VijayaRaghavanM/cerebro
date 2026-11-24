import type { ReactNode } from "react";

const SHIELD = "M12 3 4.5 6v5.5c0 4.6 3.2 8.4 7.5 9.5 4.3-1.1 7.5-4.9 7.5-9.5V6z";

const SHAPES = {
  search: (
    <>
      <circle cx="11" cy="11" r="6.5" />
      <path d="m16 16 4.5 4.5" />
    </>
  ),
  passages: (
    <>
      <path d="M4 6h16M4 10h16M4 14h7" />
      <circle cx="16.5" cy="16.5" r="3" />
      <path d="m18.7 18.7 2 2" />
    </>
  ),
  page: (
    <>
      <path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z" />
      <path d="M14 3v5h5M9 13h6M9 17h6" />
    </>
  ),
  comics: (
    <>
      <rect x="4" y="3" width="12" height="16" rx="1.5" />
      <path d="M8 21h10a2 2 0 0 0 2-2V7" />
    </>
  ),
  order: <path d="M5 5v14m0 0-2.5-2.5M5 19l2.5-2.5M11 6h9M11 12h9M11 18h9" />,
  compare: (
    <>
      <rect x="3" y="4" width="7" height="16" rx="1.5" />
      <rect x="14" y="4" width="7" height="16" rx="1.5" />
    </>
  ),
  passed: (
    <>
      <path d={SHIELD} />
      <path d="m8.5 12 2.5 2.5 4.5-5" />
    </>
  ),
  problem: (
    <>
      <path d="M10.3 4.2 2.8 17.5a2 2 0 0 0 1.7 3h15a2 2 0 0 0 1.7-3L13.7 4.2a2 2 0 0 0-3.4 0z" />
      <path d="M12 9.5v4M12 17h.01" />
    </>
  ),
  unchecked: (
    <>
      <path d={SHIELD} />
      <path d="M9 12h6" />
    </>
  ),
  tool: (
    <path d="M14.7 6.3a4 4 0 0 0-5.4 5.4L4 17l3 3 5.3-5.3a4 4 0 0 0 5.4-5.4l-2.5 2.5-2.5-2.5z" />
  ),
  chevron: <path d="m9 6 6 6-6 6" />,
  external: (
    <path d="M14 4h6v6M20 4l-9 9M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5" />
  ),
} satisfies Record<string, ReactNode>;

export type IconName = keyof typeof SHAPES;

// Decorative: every icon sits next to words that say the same thing.
export function Icon({ name }: { name: IconName }) {
  return (
    <svg
      className="icon"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {SHAPES[name]}
    </svg>
  );
}

export function Spinner() {
  return (
    <svg className="icon spinner" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <circle cx="12" cy="12" r="8" stroke="currentColor" strokeWidth="2.2" opacity="0.2" />
      <path
        d="M20 12a8 8 0 0 0-8-8"
        stroke="currentColor"
        strokeWidth="2.2"
        strokeLinecap="round"
      />
    </svg>
  );
}
