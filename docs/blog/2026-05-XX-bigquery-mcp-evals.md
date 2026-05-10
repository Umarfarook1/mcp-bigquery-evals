# I built a BigQuery MCP server with built-in evals - here's what I learned

## Outline

### Hook
"Most AI agents that touch warehouses fail in three ways: cost, correctness, and unfounded confidence. Here's how I tried to fix all three in a weekend project."

### What I built
- `mcp-bigquery-evals` - an MCP server for any MCP-compatible client (Cursor, agent IDEs, etc.)
- 7 read-only tools, mandatory dry-run cost caps, in-the-box result-set-equivalence eval harness with a live accuracy badge
- Live in your MCP client in 5 minutes

### Three design decisions worth talking about

1. **Why the cost cap is mandatory, not advisory**
   - The first thing an agent does with `run_query` is run the most natural-looking query, which is sometimes a `SELECT *` against a billion-row table
   - Solution: mandatory dry-run before every execute. Refuse if estimate > cap. Return a *structured* error that includes the bytes-scanned estimate AND the override hint
   - Show the structured error response and how the agent self-corrects (narrows WHERE clause OR explicitly raises the cap)
   - Generalisable principle: the agent's failure mode should be *recoverable*, not *fatal*. Structured error > exception.

2. **Why I built the eval harness on day 1, not as a v2 nice-to-have**
   - "The agent is good now" is a vibe; accuracy on a fixed golden set is a number
   - Result-set equivalence > LLM-as-judge (link to Hamel Husain's writing on this)
   - Golden set against `bigquery-public-data` so anyone can reproduce
   - The badge in the README updates on every main merge - agent quality is publicly visible
   - The hardest part was the comparator, not the runner: NaN, Decimal, ARRAY/STRUCT, bool-vs-int. Show 1-2 specific edge cases that bit me.

3. **Why I dropped `explain_query`**
   - Tease only - point to the next post

### What surprised me
- How much faster the FakeBigQueryClient (sqlite-backed) made development. Wrote and tested the entire MCP server before touching real BQ.
- How many edge cases the comparator needed. The naive version was wrong in five ways.
- How much the cost cap caught - even my own queries during testing, a few times.
- The eval methodology debate is more interesting than the implementation. I had a lot to learn from reading Hamel/swyx/Eugene Yan.

### What's next
- Project 2: Standalone NL2SQL leaderboard (the eval harness, spun out)
- Project 3: Voice-driven version
- Project 4: Personal AI research assistant
- Project 5: prod-llm-starter

### Links
- Repo: github.com/Umarfarook1/mcp-bigquery-evals
- PyPI: pypi.org/project/mcp-bigquery-evals
- Eval methodology doc: docs/how_evals_work.md
- Architecture doc: docs/architecture.md

### Length target: 1200–1500 words
