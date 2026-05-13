#!/usr/bin/env node
// Process a GitHub issue submitted via the "Publish a trade profile" template.
//
// Inputs (env):
//   ISSUE_NUMBER  the issue number
//   ISSUE_BODY    the raw issue body (markdown produced by the form)
//   ISSUE_USER    the GitHub login of the submitter
//   ISSUE_TITLE   the issue title
//
// Behavior: parses fields, validates strictly, updates public/trade-network.json
// in place. On any validation failure, writes a human-readable error message to
// stdout and exits with code 1 (the workflow then comments on the issue).
//
// Security notes:
// - No shell interpolation of issue content.
// - Alias is restricted to [A-Za-z0-9 _-] and trimmed to 32 chars.
// - Region must match the curated list.
// - Sticker IDs must be integers in [1, CATALOG_TOTAL]. Caps on list size.
// - Consent checkbox must be ticked.
// - Submitter's github login is recorded, but no email or precise location.

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = path.resolve(__dirname, '..');
const DB_PATH = path.join(REPO_ROOT, 'public', 'trade-network.json');
const CATALOG_PATH = path.join(REPO_ROOT, 'src', 'data', 'catalog.json');

const MAX_LIST = 1000;
const ALIAS_RE = /^[A-Za-z0-9 _-]{2,32}$/;

const ALLOWED_REGIONS = new Set([
  'London, UK', 'Manchester, UK', 'Berlin, DE', 'Munich, DE', 'Paris, FR',
  'Madrid, ES', 'Barcelona, ES', 'Milan, IT', 'Rome, IT', 'Lisbon, PT',
  'Amsterdam, NL', 'Brussels, BE', 'Zurich, CH', 'Vienna, AT', 'Warsaw, PL',
  'New York, US', 'Los Angeles, US', 'Chicago, US', 'Toronto, CA',
  'Mexico City, MX', 'São Paulo, BR', 'Rio de Janeiro, BR', 'Buenos Aires, AR',
  'Bogotá, CO', 'Tokyo, JP', 'Seoul, KR', 'Sydney, AU', 'Cairo, EG',
  'Lagos, NG', 'Casablanca, MA', 'Other / prefer not to say',
]);

function die(msg) {
  process.stdout.write(`VALIDATION_ERROR: ${msg}\n`);
  process.exit(1);
}

// GitHub issue forms render each field as a `### Heading` followed by the value
// (or `_No response_`). We split on `### ` and build a map.
function parseFormSections(body) {
  const sections = {};
  const parts = body.split(/^###\s+/m).slice(1);
  for (const part of parts) {
    const nl = part.indexOf('\n');
    const heading = (nl === -1 ? part : part.slice(0, nl)).trim();
    const value = nl === -1 ? '' : part.slice(nl + 1).trim();
    sections[heading.toLowerCase()] = value;
  }
  return sections;
}

function parseIntList(raw, label) {
  if (!raw || raw === '_No response_') die(`${label} is required.`);
  const tokens = raw.split(/[\s,]+/).map(s => s.trim()).filter(Boolean);
  const ids = [];
  for (const t of tokens) {
    if (!/^-?\d+$/.test(t)) die(`${label}: "${t}" is not an integer.`);
    ids.push(Number(t));
  }
  return ids;
}

function parseDuplicates(raw, label) {
  if (!raw || raw === '_No response_') die(`${label} is required.`);
  const lines = raw.split(/\r?\n/).map(s => s.trim()).filter(Boolean);
  const out = {};
  for (const line of lines) {
    let id, count;
    if (line.includes(':')) {
      const [a, b] = line.split(':').map(s => s.trim());
      if (!/^\d+$/.test(a) || !/^\d+$/.test(b)) die(`${label}: invalid line "${line}".`);
      id = Number(a); count = Number(b);
    } else {
      if (!/^\d+$/.test(line)) die(`${label}: invalid line "${line}".`);
      id = Number(line); count = 2;
    }
    out[id] = count;
  }
  return out;
}

function validateConsent(raw) {
  if (!raw) die('Consent section is required.');
  // GH issue-form checkboxes render as "- [x] ..." when ticked.
  const lines = raw.split(/\r?\n/);
  const ticked = lines.filter(l => /^\s*-\s*\[x\]/i.test(l)).length;
  if (ticked < 2) die('Both consent checkboxes must be ticked.');
}

function main() {
  const issueNumber = Number(process.env.ISSUE_NUMBER || 0);
  const submitter = (process.env.ISSUE_USER || '').trim();
  const body = process.env.ISSUE_BODY || '';
  if (!issueNumber || !submitter || !body) die('Missing ISSUE_NUMBER/ISSUE_USER/ISSUE_BODY.');

  const catalog = JSON.parse(fs.readFileSync(CATALOG_PATH, 'utf8'));
  const catalogTotal = Number(catalog.total) || 0;
  if (!catalogTotal) die('Catalog total missing.');

  const sections = parseFormSections(body);
  const alias = (sections['alias'] || '').trim();
  const region = (sections['coarse region'] || '').trim();
  const missingRaw = sections['missing sticker ids'] || '';
  const dupsRaw = sections['duplicate sticker ids and counts'] || '';
  const consentRaw = sections['consent'] || '';

  if (!ALIAS_RE.test(alias)) {
    die('Alias must be 2-32 characters and contain only letters, digits, spaces, dashes, and underscores.');
  }
  if (!ALLOWED_REGIONS.has(region)) {
    die(`Region "${region}" is not in the allowed list.`);
  }

  const missing = parseIntList(missingRaw, 'Missing sticker IDs');
  if (missing.length === 0) die('At least one missing sticker ID is required.');
  if (missing.length > MAX_LIST) die(`Too many missing IDs (max ${MAX_LIST}).`);
  for (const id of missing) {
    if (!Number.isInteger(id) || id < 1 || id > catalogTotal) {
      die(`Missing ID ${id} is out of range [1, ${catalogTotal}].`);
    }
  }

  const duplicates = parseDuplicates(dupsRaw, 'Duplicate sticker IDs and counts');
  const dupIds = Object.keys(duplicates);
  if (dupIds.length === 0) die('At least one duplicate entry is required.');
  if (dupIds.length > MAX_LIST) die(`Too many duplicate entries (max ${MAX_LIST}).`);
  for (const [idStr, count] of Object.entries(duplicates)) {
    const id = Number(idStr);
    if (!Number.isInteger(id) || id < 1 || id > catalogTotal) {
      die(`Duplicate ID ${id} is out of range [1, ${catalogTotal}].`);
    }
    if (!Number.isInteger(count) || count < 2 || count > 99) {
      die(`Duplicate count for ID ${id} must be an integer in [2, 99].`);
    }
  }

  // Disallow overlap (cannot both own duplicates of X and be missing X).
  const dupSet = new Set(dupIds.map(Number));
  for (const id of missing) {
    if (dupSet.has(id)) die(`Sticker ID ${id} cannot be both missing and a duplicate.`);
  }

  validateConsent(consentRaw);

  // Load existing DB.
  const db = JSON.parse(fs.readFileSync(DB_PATH, 'utf8'));
  if (!Array.isArray(db.profiles)) db.profiles = [];

  // De-duplicate: replace any existing profile with the same alias OR the same
  // submitter (one submitter = one profile, latest wins).
  const submitterKey = submitter.toLowerCase();
  db.profiles = db.profiles.filter(p =>
    p.alias.toLowerCase() !== alias.toLowerCase() &&
    (p.submittedBy || '').toLowerCase() !== submitterKey
  );

  const profile = {
    id: `gh-${submitter}-${issueNumber}`,
    alias,
    region,
    submittedBy: submitter,
    submittedAt: new Date().toISOString(),
    sourceIssue: issueNumber,
    missingIds: Array.from(new Set(missing)).sort((a, b) => a - b),
    duplicates,
    completionPct: Math.round(((catalogTotal - missing.length) / catalogTotal) * 1000) / 10,
  };

  db.profiles.push(profile);
  db.profiles.sort((a, b) => a.alias.localeCompare(b.alias));
  db.generatedAt = new Date().toISOString();
  db.version = 1;

  fs.writeFileSync(DB_PATH, JSON.stringify(db, null, 2) + '\n', 'utf8');
  process.stdout.write(`OK: added profile "${alias}" (issue #${issueNumber}) — ${db.profiles.length} total.\n`);
}

main();
