# matchsim

Tiered Udinese vs Cagliari (Serie A, 19 Sep 2026) match simulator: a
Dixon-Coles team-level baseline, a player-level lineup model, and an
optional possession-sequence stub. Self-contained Python package —
unrelated to the Estádio sticker-album app in the rest of this repository;
it lives under `matchsim/` so the two projects don't collide.

See `CLAUDE.md` in this directory for the non-negotiable data/modeling
constraints (no synthesized contract data, no scraping, no injury
inference, thin-sample flagging, demo-data labelling).

## Setup

```bash
cd matchsim
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

## Usage

```bash
matchsim fit --results data/results.csv --out models/
matchsim predict --home "Udinese Calcio" --away "Cagliari Calcio" --date 2026-09-19 --tier 1
```

## Tests

```bash
pytest
```

## Status

- Tier 1 (Dixon-Coles + pi-ratings): in progress.
- Tier 2 (player-level lineup model via RAPM/VAEP): not started.
- Tier 3 (possession-sequence stub): not started, optional.
