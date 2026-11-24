// The mark from assets/logo-light.svg, drawn in the page's colours so that it
// follows the light and dark themes.
export function Logo() {
  return (
    <svg className="logo" viewBox="0 0 256 256" aria-hidden="true">
      <g fill="none" stroke="currentColor" strokeLinecap="round">
        <path strokeWidth="14" d="M 196.6 68.6 A 96 96 0 1 0 196.6 187.4" />
        <path strokeWidth="10" opacity=".75" d="M 174.3 87.0 A 68 68 0 1 0 174.3 169.0" />
        <path strokeWidth="7" opacity=".5" d="M 153.2 101.7 A 42 42 0 1 0 153.2 154.3" />
        <g strokeWidth="3" opacity=".55">
          <line x1="128" y1="128" x2="176" y2="128" />
          <line x1="176" y1="128" x2="214" y2="104" />
          <line x1="176" y1="128" x2="214" y2="152" />
        </g>
      </g>
      <g fill="currentColor">
        <circle cx="128" cy="128" r="9" />
        <circle cx="214" cy="104" r="7" />
        <circle cx="214" cy="152" r="7" />
      </g>
      <circle cx="176" cy="128" r="17" fill="none" stroke="var(--brand)" strokeWidth="3" opacity=".45" />
      <circle cx="176" cy="128" r="10" fill="var(--brand)" />
    </svg>
  );
}
