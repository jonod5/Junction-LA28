# Stated-preference (SP) survey CSV format

For Kapil — this is the format `python -m app.ingest_sp` reads. One row per
alternative; alternatives sharing a `task_code` become one choice task.

## Columns

| Column              | Required | Type   | Notes |
|---------------------|----------|--------|-------|
| `task_code`         | yes      | string | Groups rows into a choice task. Any stable identifier (`T1`, `S03_Q2`, etc.) |
| `alt_code`           | yes      | string | Identifies the alternative within its task (`A`, `B`, `1`, `2`, ...) |
| `mode_label`         | yes      | string | Shown to the respondent, e.g. "Transit + walk", "Rideshare" |
| `block_id`           | no       | string | Experimental-design block. Leave blank if you're not blocking the design — all tasks share one implicit pool. Must be the same value for every row of a given `task_code`. |
| `travel_time_min`    | no       | number | |
| `cost_usd`           | no       | number | |
| `walk_time_min`      | no       | number | |
| `transfers`          | no       | integer | |

**Any other column** you add gets stored per-alternative in a flexible
`extra` field (e.g. a `comfort_rating` column, a `reliability` column) — no
migration needed to add attributes. Numeric-looking values are stored as
numbers, everything else as text.

## Rules

- Every `task_code` needs **at least 2** rows (alternatives) — a task with
  only one option isn't a choice.
- `block_id` must be consistent across all rows of the same `task_code`.
- Blank cells are fine for any optional column — they come through as
  `null`, not `0` or `""`.
- Leave `block_id` empty everywhere if your design doesn't use blocks.

## Re-running ingest

`python -m app.ingest_sp survey.csv --name "LA28 SP v1"` is **idempotent by
name**: running it again with the same `--name` replaces that survey's
tasks and alternatives with whatever is in the CSV this time — it does not
duplicate or merge. If that survey already has recorded respondent
choices, the command refuses to proceed (since deleting the tasks would
also delete those responses) unless you pass `--force`.

```
python -m app.ingest_sp docs/sample_survey.csv --name "LA28 SP v1" \
    --description "Pilot stated-preference survey" \
    --tasks-per-respondent 4
```

## Sample data

`docs/sample_survey.csv` is dummy/placeholder data (not from Kapil) used to
build and demo the pipeline end-to-end before real scenario data exists.
Swap it out for the real CSV once it arrives — the schema above is what it
needs to match.
