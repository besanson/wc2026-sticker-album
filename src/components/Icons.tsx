// Inline icon set — kept tiny & consistent; uses currentColor.
const I = (path: React.ReactNode, viewBox = '0 0 24 24') => ({ size = 18 }: { size?: number }) => (
  <svg width={size} height={size} viewBox={viewBox} fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
    {path}
  </svg>
);

export const AlbumIcon = I(<>
  <rect x="4" y="3" width="16" height="18" rx="2" />
  <path d="M9 3v18" />
  <path d="M13 8h4M13 12h4" />
</>);

export const TradeIcon = I(<>
  <path d="M7 7h13" />
  <path d="M16 3l4 4-4 4" />
  <path d="M17 17H4" />
  <path d="M8 21l-4-4 4-4" />
</>);

export const ForecastIcon = I(<>
  <path d="M3 3v18h18" />
  <path d="M7 14l4-4 3 3 6-6" />
</>);

export const ProfileIcon = I(<>
  <circle cx="12" cy="8" r="4" />
  <path d="M4 21a8 8 0 0 1 16 0" />
</>);

export const SearchIcon = I(<>
  <circle cx="11" cy="11" r="7" />
  <path d="m20 20-3.5-3.5" />
</>);

export const SunIcon = I(<>
  <circle cx="12" cy="12" r="4" />
  <path d="M12 2v2M12 20v2M2 12h2M20 12h2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
</>);

export const MoonIcon = I(<>
  <path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8Z" />
</>);

export const CheckIcon = I(<>
  <path d="m5 12 5 5 9-11" />
</>);

export const MinusIcon = I(<>
  <path d="M5 12h14" />
</>);

export const PlusIcon = I(<>
  <path d="M12 5v14M5 12h14" />
</>);

export const CloseIcon = I(<>
  <path d="m6 6 12 12M18 6 6 18" />
</>);
