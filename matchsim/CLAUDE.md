## 1. Non-negotiable constraints

These come from the project's existing design rules. Do not relax them.

- No synthesized fee, wage or contract data. Ever.
- No scraping of Transfermarkt, FBref, Sofascore or any site that forbids it. FBref advanced data has been unavailable since Opta pulled the feed in Jan 2026. Do not assume it exists.
- No injury-risk or fatigue inference on identifiable real players. Load and availability enter the model only as explicit user-provided scenario flags (`available`, `minutes_cap`, `fitness_multiplier`) that the user types in. The model never estimates them from data.
- Every player rating carries a sample-size field. Below 900 minutes, mark `thin_sample=True` and widen the uncertainty. Show the warning in every output that uses that player.
- All scores decompose to countable events. If a number cannot be traced to counts in the input data, do not print it.
- Demo data must be labelled as demo data in every output. Do not present StatsBomb open-data ratings as if they were 2026-27 Serie A ratings.
