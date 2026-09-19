# results.csv

Serie A results, 2023-24 to 2026-27 matchday 4. 1,126 rows.

Source: openfootball/football.json on GitHub (public domain). Matchday 4 rows for Atalanta-Cagliari (1-2) and Inter-Udinese (5-3) added from the live scores feed.

Known gaps: 2024-25 has 370 of 380 matches and 2025-26 has 344 of 380 in the public-domain file. 2026-27 is complete only through matchday 3 for most teams. Dixon-Coles handles missing matches without bias, but state the gap in any report.

Team names are the openfootball long form (e.g. "Udinese Calcio", "Cagliari Calcio"). Use them verbatim in `matchsim predict --home "Udinese Calcio" --away "Cagliari Calcio"`.

Refresh: `curl https://raw.githubusercontent.com/openfootball/football.json/master/2026-27/it.1.json`

Everything in this directory except this README is gitignored (see
`.gitignore`): result/lineup data is user-supplied from licensed sources
and is not committed to the repo (CLAUDE.md section 1).
