const PATHS = {
  home: (
    <path
      strokeLinecap="round"
      strokeLinejoin="round"
      d="M3 9.75L12 3l9 6.75V21a.75.75 0 01-.75.75H15.75a.75.75 0 01-.75-.75v-4.5h-6V21a.75.75 0 01-.75.75H3.75A.75.75 0 013 21V9.75z"
    />
  ),
  races: (
    <>
      <path strokeLinecap="round" strokeLinejoin="round" d="M3 6h18M3 12h18M3 18h12" />
      <circle cx="19" cy="18" r="2.5" />
      <path strokeLinecap="round" d="M19 15.5V12" />
    </>
  ),
  picks: (
    <>
      <rect x="5" y="2" width="14" height="20" rx="2" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4M9 7h6M9 17h4" />
    </>
  ),
  simulator: (
    <>
      <polyline points="3 17 9 11 13 15 21 7" />
      <path strokeLinecap="round" d="M21 7v5M21 7h-5" />
    </>
  ),
  profile: (
    <>
      <circle cx="12" cy="8" r="4" />
      <path strokeLinecap="round" d="M4 20c0-4 3.6-7 8-7s8 3 8 7" />
    </>
  ),
  search: (
    <>
      <circle cx="10.5" cy="10.5" r="6.5" />
      <line x1="15.5" y1="15.5" x2="21" y2="21" strokeLinecap="round" />
    </>
  ),
  settings: (
    <>
      <circle cx="12" cy="12" r="3" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 010 2.83 2 2 0 01-2.83 0l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-2 2 2 2 0 01-2-2v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83 0 2 2 0 010-2.83l.06-.06A1.65 1.65 0 004.68 15a1.65 1.65 0 00-1.51-1H3a2 2 0 01-2-2 2 2 0 012-2h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 010-2.83 2 2 0 012.83 0l.06.06A1.65 1.65 0 009 4.68a1.65 1.65 0 001-1.51V3a2 2 0 012-2 2 2 0 012 2v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 0 2 2 0 010 2.83l-.06.06A1.65 1.65 0 0019.4 9a1.65 1.65 0 001.51 1H21a2 2 0 012 2 2 2 0 01-2 2h-.09a1.65 1.65 0 00-1.51 1z" />
    </>
  ),
  learn: (
    <>
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 3L2 8l10 5 10-5-10-5z" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M2 8v8M22 8v4" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M6 10.5v5a6 6 0 0012 0v-5" />
    </>
  ),
  robot: (
    <>
      <rect x="3" y="8" width="18" height="13" rx="3" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 8V5M9 5h6" />
      <circle cx="8.5" cy="14" r="1.5" fill="currentColor" stroke="none" />
      <circle cx="15.5" cy="14" r="1.5" fill="currentColor" stroke="none" />
      <path strokeLinecap="round" d="M9 18h6" />
    </>
  ),
  lightbulb: (
    <>
      <path strokeLinecap="round" strokeLinejoin="round" d="M9 18h6M12 2a7 7 0 016 7c0 2.8-1.6 5.1-4 6.4V17H10v-1.6C7.6 14.1 6 11.8 6 9a7 7 0 016-7z" />
    </>
  ),
  clock: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path strokeLinecap="round" d="M12 7v5l3 3" />
    </>
  ),
  target: (
    <>
      <circle cx="12" cy="12" r="9" />
      <circle cx="12" cy="12" r="4" />
      <circle cx="12" cy="12" r="1" fill="currentColor" stroke="none" />
    </>
  ),
  lightning: (
    <path strokeLinecap="round" strokeLinejoin="round" d="M13 2L4.5 13.5H12L11 22l8.5-11.5H12L13 2z" />
  ),
  chart: (
    <>
      <polyline strokeLinecap="round" strokeLinejoin="round" points="3 17 9 11 13 15 21 7" />
      <path strokeLinecap="round" d="M21 7v5M21 7h-5" />
    </>
  ),
  clipboard: (
    <>
      <rect x="5" y="4" width="14" height="17" rx="2" />
      <path strokeLinecap="round" d="M9 4V3h6v1" />
      <path strokeLinecap="round" d="M9 12h6M9 16h4" />
    </>
  ),
  'chevron-right': (
    <polyline points="9 18 15 12 9 6" strokeLinecap="round" strokeLinejoin="round" />
  ),
  'chevron-left': (
    <polyline points="15 18 9 12 15 6" strokeLinecap="round" strokeLinejoin="round" />
  ),
  'chevron-down': (
    <polyline points="6 9 12 15 18 9" strokeLinecap="round" strokeLinejoin="round" />
  ),
  check: (
    <polyline points="20 6 9 17 4 12" strokeLinecap="round" strokeLinejoin="round" />
  ),
  close: (
    <>
      <line x1="18" y1="6" x2="6" y2="18" strokeLinecap="round" />
      <line x1="6" y1="6" x2="18" y2="18" strokeLinecap="round" />
    </>
  ),
  bell: (
    <>
      <path d="M18 8A6 6 0 006 8c0 7-3 9-3 9h18s-3-2-3-9" />
      <path d="M13.73 21a2 2 0 01-3.46 0" />
    </>
  ),
  star: (
    <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" strokeLinejoin="round" />
  ),
  'star-filled': (
    <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" strokeLinejoin="round" fill="currentColor" />
  ),
  trophy: (
    <>
      <path d="M8 21h8M12 17v4" strokeLinecap="round" />
      <path d="M7 4H4v3a5 5 0 003.58 4.79M17 4h3v3a5 5 0 01-3.58 4.79" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M7 4h10v8a5 5 0 01-10 0V4z" />
    </>
  ),
  info: (
    <>
      <circle cx="12" cy="12" r="10" />
      <line x1="12" y1="16" x2="12" y2="12" strokeLinecap="round" />
      <line x1="12" y1="8" x2="12.01" y2="8" strokeLinecap="round" strokeWidth="2" />
    </>
  ),
  warning: (
    <>
      <path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" strokeLinejoin="round" />
      <line x1="12" y1="9" x2="12" y2="13" strokeLinecap="round" />
      <line x1="12" y1="17" x2="12.01" y2="17" strokeLinecap="round" strokeWidth="2" />
    </>
  ),
  refresh: (
    <>
      <polyline points="23 4 23 10 17 10" strokeLinecap="round" strokeLinejoin="round" />
      <path strokeLinecap="round" d="M20.49 15a9 9 0 11-2.12-9.36L23 10" />
    </>
  ),
  external: (
    <>
      <path d="M18 13v6a2 2 0 01-2 2H5a2 2 0 01-2-2V8a2 2 0 012-2h6" />
      <polyline points="15 3 21 3 21 9" strokeLinecap="round" strokeLinejoin="round" />
      <line x1="10" y1="14" x2="21" y2="3" strokeLinecap="round" />
    </>
  ),
  bet: (
    <>
      <rect x="3" y="5" width="18" height="14" rx="2" />
      <path strokeLinecap="round" d="M7 9h10M7 13h6" />
      <circle cx="17" cy="13" r="1.5" fill="currentColor" stroke="none" />
    </>
  ),
  horse: (
    <>
      <path strokeLinecap="round" strokeLinejoin="round" d="M5 19l2-5 4-2 2-4 3-1 1-3h2l-1 4-2 1-1 3-3 2-1 5H5z" />
      <circle cx="16" cy="5" r="1.5" fill="currentColor" stroke="none" />
    </>
  ),
};

export default function Icon({ name, size = 24, color = 'currentColor' }) {
  const paths = PATHS[name];
  if (!paths) return null;
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke={color}
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {paths}
    </svg>
  );
}
