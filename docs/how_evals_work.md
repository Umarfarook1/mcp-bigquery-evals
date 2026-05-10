# How the eval harness works

This document explains the methodology, the golden pairs format, and how to add your own.

## Methodology: result-set equivalence

For each golden pair `{nl, gold_sql, dataset}`:

1. Build a schema context (textual dump of every table in `dataset` + their columns + descriptions)
2. Send the schema + the natural-language question to an LLM, asking for a single SQL query
3. Execute the gold SQL via BigQuery → `gold_result` (list of row dicts)
4. Execute the model's predicted SQL via BigQuery → `predicted_result` (list of row dicts)
5. Compare the two as multisets of rows (order-independent, with float tolerance, NULL equality, Decimal handling, NaN equality, ARRAY/STRUCT recursion, bool/int distinction)
6. Pass = identical results

Aggregate `accuracy = passes / total` is the headline metric, displayed as a shields.io badge in the README.

## Why result-set equivalence (and not LLM-as-judge)

- **Deterministic.** The same model + the same goldens always yields the same accuracy. CI runs are reproducible.
- **Defensible.** This is the methodology used by Spider, BIRD, and most academic NL2SQL benchmarks.
- **Single number.** "Accuracy: 74%" goes in a badge. "LLM judge says these answers were mostly fine" doesn't.
- **No judge bias.** No model has a vested interest in the outcome.

The downside: result-set equivalence is strict. A model that produces `SELECT name, COUNT(*)` instead of `SELECT name, COUNT(*) AS n` will fail because the column name differs. A model that returns rows in a different order passes (we sort multiset-style). A model that returns the right count but as a float instead of int passes (we tolerance-match).

## What the comparator handles correctly

| BQ type | Python type | Comparator behavior |
|---|---|---|
| INT64 | `int` | Strict equality |
| FLOAT64 | `float` | Tolerance via `math.isclose` (rel_tol=1e-6) |
| NUMERIC / BIGNUMERIC | `decimal.Decimal` | Same tolerance as float |
| STRING | `str` | Strict equality |
| BOOL | `bool` | Strict equality; `True != 1` (Python's misleading default is overridden) |
| DATE / DATETIME / TIMESTAMP | `datetime.date` / `datetime.datetime` | Strict equality |
| BYTES | `bytes` | Strict equality |
| ARRAY | `list` | Recursive comparison; element order matters within an array |
| STRUCT / RECORD | `dict` | Recursive comparison; key order does NOT matter |
| NaN | `float('nan')` | NaN compares equal to NaN (eval semantic, not IEEE 754) |
| NULL | `None` | NULL compares equal to NULL |

## The golden pairs file

Production goldens: `src/mcp_bigquery_evals/evals/golden.yaml`. Format:

```yaml
golden_pairs:
  - id: 1
    dataset: bigquery-public-data.samples
    nl: "How many unique words appear in the Shakespeare dataset?"
    gold_sql: |
      SELECT COUNT(DISTINCT word) AS n
      FROM `bigquery-public-data.samples.shakespeare`
    tags: [count, distinct]
    verified: true
```

Required keys: `id`, `dataset`, `nl`, `gold_sql`. Optional: `tags`, `verified`. The runner schema-validates pairs at load time and refuses to run if any pair is missing required keys.

## Running the harness

```bash
mcp-bigquery-evals evals run --model <your-model-id>
```

Optional flags:
- `--golden PATH` - use a different golden file (default: `src/mcp_bigquery_evals/evals/golden.yaml`)
- `--limit N` - run only the first N pairs (useful for fast iteration)
- `--report PATH` - where to write the JSON report (default: `evals/last_report.json`)

The runner also writes a `badge.json` next to the report (consumed by shields.io).

## Adding a new golden pair

1. Pick a `bigquery-public-data` dataset and a real analyst question
2. Write the gold SQL
3. Run it manually against real BQ:
   ```bash
   bq query --use_legacy_sql=false 'SELECT ...'
   ```
4. Confirm the result matches what the question intended
5. Add the entry to `golden.yaml` with `verified: true`
6. Re-run the harness to confirm the new pair works
7. Open a PR

## Cost

Each golden pair costs:
- ~1 BQ dry-run (free)
- ~1 BQ query execution (typically ~1MB scanned ≈ $0.000005)
- ~1 LLM API call (varies by provider; small models are typically a fraction of a cent per pair)

15 pairs is roughly $0.002 per run on a small model. 50 pairs is roughly $0.007 per run. CI runs the full set on every main merge.

The runner threads the dry-run result through to `execute()` so each pair only triggers ONE BQ dry-run + ONE BQ execute, not two of each.

## Cost-effectively iterating on prompts

To test a prompt change without paying full freight:
```bash
mcp-bigquery-evals evals run --model <your-model-id> --limit 5
```

Five pairs on a small model is roughly $0.0005 per iteration. Iterate fast.

## How errors are reported

The JSON report includes `gold_errors` - the count of pairs whose `gold_sql` itself failed to execute. These are golden-file bugs (broken SQL, missing tables, permission issues), not model errors. They're surfaced separately so a single-digit `gold_errors` value next to a 90% accuracy doesn't get conflated with a model regression.

Per-pair errors carry stable prefixes:
- `predicted execution failed:` - the model's SQL ran into an error (this is a fail for accuracy)
- `gold execution failed:` - your golden_sql is broken (does NOT count as a model fail; counts toward `gold_errors`)
- `runner_error:` - a bug in the runner itself (model_fn raised, etc.); investigate the implementation
