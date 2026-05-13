// Generates a structured 2026 World Cup sticker catalog.
// Output is intentionally formatted so it can be hand-replaced with the official Panini checklist later.
// Structure: sections -> stickers. Each sticker has stable numeric id (1..N), code, label, kind, team.
import { writeFileSync, mkdirSync } from 'node:fs';
import { dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));

// 48 nations expected at the 2026 tournament. We seed with confirmed hosts plus a realistic field.
// This is sample data — replace with the official checklist when Panini publishes it.
const TEAMS = [
  { code: 'CAN', name: 'Canada', confed: 'CONCACAF', host: true },
  { code: 'MEX', name: 'Mexico', confed: 'CONCACAF', host: true },
  { code: 'USA', name: 'United States', confed: 'CONCACAF', host: true },
  { code: 'ARG', name: 'Argentina', confed: 'CONMEBOL' },
  { code: 'BRA', name: 'Brazil', confed: 'CONMEBOL' },
  { code: 'URU', name: 'Uruguay', confed: 'CONMEBOL' },
  { code: 'COL', name: 'Colombia', confed: 'CONMEBOL' },
  { code: 'ECU', name: 'Ecuador', confed: 'CONMEBOL' },
  { code: 'PAR', name: 'Paraguay', confed: 'CONMEBOL' },
  { code: 'FRA', name: 'France', confed: 'UEFA' },
  { code: 'ENG', name: 'England', confed: 'UEFA' },
  { code: 'ESP', name: 'Spain', confed: 'UEFA' },
  { code: 'GER', name: 'Germany', confed: 'UEFA' },
  { code: 'POR', name: 'Portugal', confed: 'UEFA' },
  { code: 'ITA', name: 'Italy', confed: 'UEFA' },
  { code: 'NED', name: 'Netherlands', confed: 'UEFA' },
  { code: 'BEL', name: 'Belgium', confed: 'UEFA' },
  { code: 'CRO', name: 'Croatia', confed: 'UEFA' },
  { code: 'SUI', name: 'Switzerland', confed: 'UEFA' },
  { code: 'DEN', name: 'Denmark', confed: 'UEFA' },
  { code: 'AUT', name: 'Austria', confed: 'UEFA' },
  { code: 'POL', name: 'Poland', confed: 'UEFA' },
  { code: 'SCO', name: 'Scotland', confed: 'UEFA' },
  { code: 'NOR', name: 'Norway', confed: 'UEFA' },
  { code: 'SRB', name: 'Serbia', confed: 'UEFA' },
  { code: 'TUR', name: 'Türkiye', confed: 'UEFA' },
  { code: 'HUN', name: 'Hungary', confed: 'UEFA' },
  { code: 'JPN', name: 'Japan', confed: 'AFC' },
  { code: 'KOR', name: 'South Korea', confed: 'AFC' },
  { code: 'IRN', name: 'Iran', confed: 'AFC' },
  { code: 'AUS', name: 'Australia', confed: 'AFC' },
  { code: 'KSA', name: 'Saudi Arabia', confed: 'AFC' },
  { code: 'QAT', name: 'Qatar', confed: 'AFC' },
  { code: 'UZB', name: 'Uzbekistan', confed: 'AFC' },
  { code: 'JOR', name: 'Jordan', confed: 'AFC' },
  { code: 'MAR', name: 'Morocco', confed: 'CAF' },
  { code: 'SEN', name: 'Senegal', confed: 'CAF' },
  { code: 'EGY', name: 'Egypt', confed: 'CAF' },
  { code: 'NGA', name: 'Nigeria', confed: 'CAF' },
  { code: 'CIV', name: 'Côte d’Ivoire', confed: 'CAF' },
  { code: 'GHA', name: 'Ghana', confed: 'CAF' },
  { code: 'CMR', name: 'Cameroon', confed: 'CAF' },
  { code: 'ALG', name: 'Algeria', confed: 'CAF' },
  { code: 'TUN', name: 'Tunisia', confed: 'CAF' },
  { code: 'RSA', name: 'South Africa', confed: 'CAF' },
  { code: 'CRC', name: 'Costa Rica', confed: 'CONCACAF' },
  { code: 'PAN', name: 'Panama', confed: 'CONCACAF' },
  { code: 'NZL', name: 'New Zealand', confed: 'OFC' },
];

// Per-team sticker template aligned to the reported 2026 structure:
// 48 teams × 20 stickers = 960 team stickers.
const TEAM_TEMPLATE = [
  { suffix: 'BADGE', kind: 'badge', label: 'Team Badge' },
  { suffix: 'PHOTO', kind: 'team-photo', label: 'Team Photo' },
  ...Array.from({ length: 18 }, (_, i) => ({ suffix: `P${i + 1}`, kind: 'player', label: `Player ${i + 1}` })),
];

// 20 non-team stickers: 9 opening/tournament stickers + 11 museum/history stickers.
const SPECIAL_SECTIONS = [
  {
    section: 'Opening Stickers',
    items: [
      { code: '00', kind: 'logo', label: 'Panini Logo' },
      { code: 'WC-TROPHY', kind: 'trophy', label: 'FIFA World Cup Trophy' },
      { code: 'WC-LOGO', kind: 'logo', label: 'Official Logo' },
      { code: 'WC-MASCOTS', kind: 'mascot', label: 'Official Mascots' },
      { code: 'WC-SLOGAN', kind: 'slogan', label: 'Official Slogan' },
      { code: 'WC-BALL', kind: 'ball', label: 'Match Ball' },
      { code: 'WC-CANADA', kind: 'host', label: 'Host Country · Canada' },
      { code: 'WC-MEXICO', kind: 'host', label: 'Host Country · Mexico' },
      { code: 'WC-USA', kind: 'host', label: 'Host Country · United States' },
    ],
  },
  {
    section: 'FIFA Museum',
    items: [
      'Uruguay 1930','Italy 1934','Brazil 1958','England 1966','Argentina 1978','France 1998',
      'Germany 2014','France 2018','Argentina 2022','World Cup Icons','Road to 2026'
    ].map((n, i) => ({ code: `MUS-${String(i + 1).padStart(2, '0')}`, kind: 'museum', label: n })),
  },
];

const sections = [];
let id = 1;

for (const block of SPECIAL_SECTIONS) {
  const stickers = block.items.map(it => ({
    id: id++, code: it.code, kind: it.kind, label: it.label, section: block.section, team: null,
  }));
  sections.push({ name: block.section, kind: 'special', stickers });
}

for (const team of TEAMS) {
  const stickers = TEAM_TEMPLATE.map(t => ({
    id: id++,
    code: `${team.code}-${t.suffix}`,
    kind: t.kind,
    label: t.label,
    section: team.name,
    team: { code: team.code, name: team.name, confed: team.confed, host: !!team.host },
  }));
  sections.push({ name: team.name, kind: 'team', team: { code: team.code, name: team.name, confed: team.confed, host: !!team.host }, stickers });
}

const total = id - 1;
const catalog = {
  edition: 'FIFA World Cup 2026 — 980-sticker demo catalog',
  generatedAt: new Date().toISOString(),
  source: 'Demo catalog aligned to the reported 980-sticker structure; replace names/codes with the official Panini checklist for production.',
  total,
  stickersPerPack: 7,
  retailPackPriceUSD: 1.6,
  sections,
};

const out = `${__dirname}/../src/data/catalog.json`;
mkdirSync(dirname(out), { recursive: true });
writeFileSync(out, JSON.stringify(catalog, null, 2));
console.log(`Wrote ${total} stickers in ${sections.length} sections to ${out}`);
