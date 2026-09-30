# Real Samsung appliance data (for embedding)

Plain CSV, UTF-8, one row per fault code. Rebuild with `cd backend && uv run python -m scripts.export_real_data`
(both sources are pinned to one commit, so a rebuild gives the same rows).

## What replaces which sample file

| Sample in the app (`backend/data/manuals/`) | Real data here | Coverage |
|---|---|---|
| `WW90T.md` washer | `samsung_washer_faults.csv` + washer rows of `samsung_appliance_codes.csv` | 143 + 42 rows |
| `DV90T.md` dryer | dryer rows of `samsung_appliance_codes.csv` | 14 codes (US) |
| `AR12.md` air conditioner | **none found** (see below) | stays sample |
| (not in the demo yet) | refrigerator and dishwasher rows of `samsung_appliance_codes.csv` | 14 + 14 codes (US) |

The washer fault table is already inside the app (`SAMSUNG_WASHER_FAULTS.md`); the rest is here for embedding.

## Files

**`samsung_washer_faults.csv`** (143 rows): `brand, appliance_type, code, canonical_code, also_shown_as, meaning,
what_to_do, needs_service, source_name, source_url, license`. Rows with the same `canonical_code` are one fault shown
with different spellings (4E, 4C, NF...).

**`samsung_appliance_codes.csv`** (84 rows): `brand, market, appliance_type, code, meaning, component,
cause_category, severity, fix_steps, diy_difficulty, source_type, source_url, dataset, license`. `fix_steps` holds the
ranked repairs as `1. title: steps | 2. ...` (13 codes have none). Codes repeat across appliance types and markets:
the key is `(appliance_type, market, code)`.

Suggested embedding text per row: `"{appliance_type} {code}: {meaning}. {what_to_do or fix_steps}"`, and keep `code`
and `appliance_type` as filters so a dryer question never returns a washer answer.

## Sources and licences (keep these with the data)

- **ha-samsung-washer-local**, commit `b75ef1e`, MIT licence:
  https://github.com/perseus177/ha-samsung-washer-local/blob/b75ef1ee561de4426d2f150c81ce786169df2b3b/custom_components/samsung_washer_local/const.py
  The wording is the project's own, not Samsung's. MIT notice: `backend/data/licenses/ha-samsung-washer-local.LICENSE`.
- **ApplianceDB free developer sample**, commit `fe7d992`, Open Database License (ODbL) 1.0:
  https://github.com/ApplianceDB/ApplianceDB-public
  Contains information from ApplianceDB, which is made available under the ODbL 1.0
  (https://opendatacommons.org/licenses/odbl/1-0/). Meanings are paraphrased; each row links its source listing.
  Conditions: credit ApplianceDB with a link; share any database built from these rows under ODbL; don't present
  it as an official Samsung publication. Embedding the full corpus in a *commercial* product needs their paid licence.

## Why there is no air conditioner data

No Samsung AC fault-code source with an open licence could be verified (September 2026). Samsung's own support pages
list the codes, but their terms allow personal use only and forbid automated collection, so they were not copied.
The GitHub projects that carry AC codes have no licence or are GPL. Options: license ApplianceDB's paid corpus, ask
Samsung, or keep the AC manual marked as sample data.
