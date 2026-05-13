// Custom SVG mark — a stylized stadium tier above a sticker corner peel.
// "Estádio" means stadium in Portuguese — a nod to the tournament's three host nations and global game.
export function Logo({ size = 30 }: { size?: number }) {
  return (
    <svg
      aria-label="Estádio logo"
      role="img"
      width={size}
      height={size}
      viewBox="0 0 32 32"
      fill="none"
    >
      <rect x="0.75" y="0.75" width="30.5" height="30.5" rx="7" stroke="currentColor" strokeWidth="1.5" />
      <path d="M5 22 L16 6 L27 22" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" />
      <path d="M5 22 L27 22" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
      <circle cx="16" cy="20" r="2.2" fill="currentColor" />
    </svg>
  );
}
