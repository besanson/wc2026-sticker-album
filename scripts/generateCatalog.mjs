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

// Per-team sticker template (mirrors Panini conventions — flag, badge, team photo, lineup, 16 player slots, legend, key player special).
const TEAM_TEMPLATE = [
  { suffix: 'FLAG', kind: 'badge', label: 'Flag' },
  { suffix: 'BADGE', kind: 'badge', label: 'Team Badge' },
  { suffix: 'PHOTO', kind: 'team-photo', label: 'Team Photo' },
  { suffix: 'LINEUP', kind: 'lineup', label: 'Starting XI' },
  ...Array.from({ length: 16 }, (_, i) => ({ suffix: `P${i + 1}`, kind: 'player', label: `Player ${i + 1}` })),
  { suffix: 'LEGEND', kind: 'legend', label: 'Legend' },
];

// Bonus/special sections to add depth and variety (mirrors host cities, mascots, trophy, FWC history).
const SPECIAL_SECTIONS = [
  {
    section: 'Tournament',
    items: [
      { code: 'WC-TROPHY', kind: 'trophy', label: 'FIFA World Cup Trophy' },
      { code: 'WC-LOGO', kind: 'logo', label: 'Official Logo' },
      { code: 'WC-MASCOT-MAPLE', kind: 'mascot', label: 'Mascot · Maple' },
      { code: 'WC-MASCOT-ZAYU', kind: 'mascot', label: 'Mascot · Zayu' },
      { code: 'WC-MASCOT-CLUTCH', kind: 'mascot', label: 'Mascot · Clutch' },
      { code: 'WC-BALL', kind: 'ball', label: 'Match Ball' },
      { code: 'WC-POSTER', kind: 'poster', label: 'Official Poster' },
    ],
  },
  {
    section: 'Host Cities',
    items: [
      'Atlanta','Boston','Dallas','Guadalajara','Houston','Kansas City','Los Angeles','Mexico City','Miami',
      'Monterrey','New York/New Jersey','Philadelphia','San Francisco','Seattle','Toronto','Vancouver'
    ].map((c, i) => ({ code: `HC-${String(i + 1).padStart(2, '0')}`, kind: 'city', label: c })),
  },
  {
    section: 'Legends of the Game',
    items: [
      'Pelé','Maradona','Cruyff','Zidane','Ronaldo','Beckenbauer','Müller','Charlton','Garrincha','Iniesta'
    ].map((n, i) => ({ code: `LEG-${String(i + 1).padStart(2, '0')}`, kind: 'legend', label: n })),
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
  edition: 'FIFA World Cup 2026 — sample catalog',
  generatedAt: new Date().toISOString(),
  source: 'Generated sample — replace with official Panini checklist when published.',
  total,
  stickersPerPack: 5,
  retailPackPriceUSD: 1.5,
  sections,
};

const out = `${__dirname}/../src/data/catalog.json`;
mkdirSync(dirname(out), { recursive: true });
writeFileSync(out, JSON.stringify(catalog, null, 2));
console.log(`Wrote ${total} stickers in ${sections.length} sections to ${out}`);
