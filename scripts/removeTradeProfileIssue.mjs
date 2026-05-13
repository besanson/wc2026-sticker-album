#!/usr/bin/env node
// Process a GitHub issue submitted via the "Remove a trade profile" template.
// Removes the matching profile from public/trade-network.json.
//
// Inputs (env): ISSUE_NUMBER, ISSUE_BODY, ISSUE_USER.

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = path.resolve(__dirname, '..');
const DB_PATH = path.join(REPO_ROOT, 'public', 'trade-network.json');

function die(msg) {
  process.stdout.write(`VALIDATION_ERROR: ${msg}\n`);
  process.exit(1);
}

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

function main() {
  const submitter = (process.env.ISSUE_USER || '').trim();
  const body = process.env.ISSUE_BODY || '';
  if (!submitter || !body) die('Missing ISSUE_USER/ISSUE_BODY.');

  const sections = parseFormSections(body);
  const alias = (sections['alias to remove'] || '').trim();
  if (!alias) die('Alias is required.');

  const db = JSON.parse(fs.readFileSync(DB_PATH, 'utf8'));
  const before = db.profiles.length;
  // Maintainer-approved policy: a submitter can remove their own profile by
  // GH login, or any profile matching the alias (the workflow gating limits
  // this to runs maintainers approve).
  const submitterKey = submitter.toLowerCase();
  db.profiles = db.profiles.filter(p =>
    p.alias.toLowerCase() !== alias.toLowerCase() ||
    (p.submittedBy || '').toLowerCase() !== submitterKey
  );

  if (db.profiles.length === before) {
    process.stdout.write(`NO_MATCH: no profile with alias "${alias}" submitted by @${submitter}.\n`);
    // Not an error — still allow maintainer to comment.
    process.exit(0);
  }

  db.generatedAt = new Date().toISOString();
  fs.writeFileSync(DB_PATH, JSON.stringify(db, null, 2) + '\n', 'utf8');
  process.stdout.write(`OK: removed ${before - db.profiles.length} profile(s) for alias "${alias}".\n`);
}

main();
