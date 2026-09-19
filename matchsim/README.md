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
# Tier 1 (team level, real 2023-27 Serie A results)
matchsim fit --results data/results.csv --out models/
matchsim predict --home "Udinese Calcio" --away "Cagliari Calcio" --date 2026-09-19 --tier 1

# Tier 2 (player level): fits VAEP + RAPM + the calibrated lineup-strength
# link on StatsBomb open data (demo/validation only -- takes a few minutes,
# fetches over the network). No 2026-27 lineup/event data exists yet, so
# --tier 2 on the actual fixture explains why and points at the demo instead.
matchsim fit --results data/results.csv --events statsbomb --max-games 150 --out models/
matchsim predict --home "Hellas Verona" --away "AS Roma" --date 2015-08-22 --tier 2 \
  --lineups examples/demo_lineup_statsbomb_serieA_2015_16.json
matchsim whatif --scenario examples/demo_whatif_no_key_midfielder.yaml
```

## Tests

```bash
pytest
```

Tier 2's StatsBomb/VAEP/RAPM pipeline is validated by actually running it
(see the commands above), not by an automated test -- it's network-dependent
and takes minutes, which doesn't belong in a fast test suite.

## Status

- Tier 1 (Dixon-Coles + pi-ratings): done. `fit`, `predict --tier 1`.
- Tier 2 (player-level lineup model via RAPM/VAEP): done for the machinery
  and validated on StatsBomb open-data demo fixtures (`predict --tier 2`,
  `whatif`). Cannot yet serve the actual Udinese vs Cagliari fixture: no
  2026-27 lineup or event data exists to rate either squad's current
  players from. A style-interaction term (section 4.4) was tried and
  dropped -- it looked significant in-sample but worsened held-out RPS.
- Tier 3 (possession-sequence stub): not started, optional.
- Eval report with ablations: not started.
