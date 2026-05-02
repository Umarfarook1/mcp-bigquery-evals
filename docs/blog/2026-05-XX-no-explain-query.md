# Why I dropped `explain_query` from my MCP server

## Outline

### Hook
"I had `explain_query` in my MCP tool list for two days before I realized it was a circular design smell."

### The setup
- Building a BigQuery MCP server. Initial tool list included `explain_query(sql) -> str` — call Claude, ask it to summarize what the SQL does in plain English
- Idea: let the agent verify its own SQL intent before running it. Sounds like good UX.

### The realization
- The MCP server's only consumer is Claude
- I was about to put a Claude call inside a server that's only ever called by Claude
- The agent already has the SQL it just generated; it can summarize it itself for free
- I'd added a network round-trip + a token cost for what the consumer can already do

### Why this matters as a general principle
- LLM-inside-LLM-tool is a code smell
- Server should be deterministic; reasoning belongs in the agent
- Two concrete reasons:
  1. Cost: every call to the tool now incurs an extra LLM round-trip. At Claude Sonnet rates, this can dominate the per-tool-call latency budget.
  2. Reliability: the server now has an external dependency that can rate-limit, time out, or change behavior independently of the consumer.

### When IS putting an LLM inside a tool actually right?
- When the tool's consumer is NOT an LLM (e.g., a CLI used by humans)
- When the LLM is doing work the consumer CAN'T do (e.g., embeddings, image gen, specialized fine-tune output)
- When the LLM call is structurally different from the consumer's reasoning (e.g., a small classifier-style model called in a loop, where re-prompting Claude would be 10x slower)

### What I do instead
- Tools return structured data
- The agent reasons about the data
- I get a deterministic, testable, debuggable server. Eval harness becomes possible.

### Generalization for other MCP tool builders
Every MCP server should ask: "would my consumer (an LLM) want me to do this work for them, or would they rather have the data and decide for themselves?"

Default to the latter. The exceptions are real but narrow.

### Counter-argument I considered
"Caching the explanation could justify the LLM call." — true if the same SQL is explained repeatedly, but agents typically generate one-off SQL, so the cache hit rate is low.

"What if the explanation needs different framing for different audiences?" — the agent KNOWS its audience; the server doesn't. Agent is the right place.

### Length target: 800–1000 words
