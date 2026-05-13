// Generates a fixed list of simulated nearby collectors with realistic owned/duplicate distributions.
// Locations are coarse (city + country + region centroid), never precise coordinates of real people.
import { writeFileSync, readFileSync, mkdirSync } from 'node:fs';
import { dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const catalog = JSON.parse(readFileSync(`${__dirname}/../src/data/catalog.json`, 'utf-8'));
const allIds = catalog.sections.flatMap(s => s.stickers.map(st => st.id));

// Coarse region centroids (lat, lng rounded to 0.5° — already obfuscated, never expose more).
const REGIONS = [
  { region: 'London, UK', lat: 51.5, lng: -0.0 },
  { region: 'Manchester, UK', lat: 53.5, lng: -2.5 },
  { region: 'Berlin, DE', lat: 52.5, lng: 13.5 },
  { region: 'Munich, DE', lat: 48.0, lng: 11.5 },
  { region: 'Madrid, ES', lat: 40.5, lng: -3.5 },
  { region: 'Barcelona, ES', lat: 41.5, lng: 2.0 },
  { region: 'Paris, FR', lat: 48.5, lng: 2.5 },
  { region: 'Milan, IT', lat: 45.5, lng: 9.0 },
  { region: 'Rome, IT', lat: 42.0, lng: 12.5 },
  { region: 'Lisbon, PT', lat: 38.5, lng: -9.0 },
  { region: 'Amsterdam, NL', lat: 52.5, lng: 5.0 },
  { region: 'Brussels, BE', lat: 51.0, lng: 4.5 },
  { region: 'Zurich, CH', lat: 47.5, lng: 8.5 },
  { region: 'Vienna, AT', lat: 48.0, lng: 16.5 },
  { region: 'Warsaw, PL', lat: 52.0, lng: 21.0 },
  { region: 'New York, US', lat: 40.5, lng: -74.0 },
  { region: 'Los Angeles, US', lat: 34.0, lng: -118.0 },
  { region: 'Chicago, US', lat: 41.5, lng: -87.5 },
  { region: 'Toronto, CA', lat: 43.5, lng: -79.5 },
  { region: 'Mexico City, MX', lat: 19.5, lng: -99.0 },
  { region: 'São Paulo, BR', lat: -23.5, lng: -46.5 },
  { region: 'Rio de Janeiro, BR', lat: -22.5, lng: -43.0 },
  { region: 'Buenos Aires, AR', lat: -34.5, lng: -58.5 },
  { region: 'Bogotá, CO', lat: 4.5, lng: -74.0 },
  { region: 'Tokyo, JP', lat: 35.5, lng: 139.5 },
  { region: 'Seoul, KR', lat: 37.5, lng: 127.0 },
  { region: 'Sydney, AU', lat: -33.5, lng: 151.0 },
  { region: 'Cairo, EG', lat: 30.0, lng: 31.0 },
  { region: 'Lagos, NG', lat: 6.5, lng: 3.5 },
  { region: 'Casablanca, MA', lat: 33.5, lng: -7.5 },
];

const HANDLES = [
  'pitchside','golazo','box-to-box','tikitaka','goldenboot','panenka','catenaccio','rabona','bicycle','header',
  'midfield-maestro','left-back','keeper-clean-sheets','sticker-swap','album-grind','full-set','foilhunter',
  'shinyseeker','wingback','number10','striker-9','iron-defense','set-piece','derby-day','match-day',
  'extra-time','penalty-king','offside-trap','rondo','passmaster','crossbar','clean-sheet','onesie','away-kit'
];

// Seeded RNG for reproducible builds.
function mulberry32(seed) {
  return () => {
    let t = (seed += 0x6D2B79F5);
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
const rng = mulberry32(20260613);

function shuffle(arr) {
  const a = [...arr];
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(rng() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

const users = [];
for (let i = 0; i < 36; i++) {
  const region = REGIONS[i % REGIONS.length];
  const handle = HANDLES[i % HANDLES.length] + (i > HANDLES.length - 1 ? `-${i}` : '');
  const completion = 0.25 + rng() * 0.65; // 25–90%
  const ownedCount = Math.floor(allIds.length * completion);
  const shuffled = shuffle(allIds);
  const owned = new Set(shuffled.slice(0, ownedCount));
  // Duplicates: 8–28% of owned, on a random subset.
  const dupRatio = 0.08 + rng() * 0.2;
  const dupCandidates = shuffle([...owned]).slice(0, Math.floor(owned.size * dupRatio));
  const duplicates = {};
  for (const id of dupCandidates) duplicates[id] = 1 + Math.floor(rng() * 4); // 1–4 dupes
  users.push({
    id: `u${i + 1}`,
    handle,
    alias: handle.replace(/-/g, ' ').replace(/\b\w/g, c => c.toUpperCase()),
    region: region.region,
    coords: { lat: region.lat, lng: region.lng }, // already coarse — fine to embed for simulated users
    confedFavorite: ['UEFA','CONMEBOL','CONCACAF','CAF','AFC','OFC'][Math.floor(rng() * 6)],
    ownedIds: [...owned],
    duplicates, // id -> count
    completionPct: Math.round((ownedCount / allIds.length) * 100),
    lastActiveDaysAgo: Math.floor(rng() * 14),
  });
}

const out = `${__dirname}/../src/data/users.json`;
mkdirSync(dirname(out), { recursive: true });
writeFileSync(out, JSON.stringify({ users }, null, 2));
console.log(`Wrote ${users.length} simulated users to ${out}`);
