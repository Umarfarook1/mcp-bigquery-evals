# MCP Client Setup

This guide walks through wiring `mcp-bigquery-evals` into any MCP-compatible client (desktop AI clients, Cursor, agent IDEs, etc.) on macOS, Windows, and Linux.

## Prerequisites

- An MCP-compatible client (latest version)
- Python 3.11+ available on PATH
- A GCP project with the BigQuery API enabled
- (Optional) `uv` installed (recommended for `uvx` zero-install). Install via `pip install uv` or `brew install uv`.

## 1. Authenticate to GCP

The MCP server uses Application Default Credentials. Set them up once:

```bash
gcloud auth application-default login
```

This opens a browser tab. After login, ADC are stored at `~/.config/gcloud/application_default_credentials.json` and the server reads them automatically.

If you'd rather use a service account JSON, set `GOOGLE_APPLICATION_CREDENTIALS=/path/to/sa.json` instead.

## 2. Find your MCP client's server config

Most MCP clients store their server registry in a JSON config file under a per-OS app-data directory. The exact path and filename vary by client; consult your client's documentation.

If the file doesn't exist yet, create it with `{}`.

## 3. Add the MCP server

Add an `mcpServers` entry pointing at this package:

```json
{
  "mcpServers": {
    "bigquery": {
      "command": "uvx",
      "args": ["mcp-bigquery-evals", "serve"],
      "env": {
        "BIGQUERY_PROJECT": "YOUR_GCP_PROJECT_ID_HERE"
      }
    }
  }
}
```

If you don't have `uv` installed, swap `command` to your `python` and use `args: ["-m", "mcp_bigquery_evals", "serve"]` after `pip install mcp-bigquery-evals` into a venv whose python is on PATH.

## 4. Restart your MCP client

Fully quit your client (not just close the window) and reopen. You should see "bigquery" listed in the MCP server indicator. Click it to confirm 7 tools are available.

## 5. Verify

Try a query in your client:

> "Using the bigquery tool, list the datasets in my project."

If you see a list, you're done. If you see an error, see Troubleshooting below.

## Troubleshooting

### "BIGQUERY_PROJECT env var is required"

The `env` block in your config wasn't passed through. Double-check the JSON is valid (no trailing commas) and restart your client fully.

### `unauthenticated` error / "Reauthentication is needed"

Run `gcloud auth application-default login` again. ADC tokens expire periodically.

### `permission_denied` when listing tables

Your account doesn't have BigQuery Data Viewer on the dataset. For `bigquery-public-data`, this is granted by default to any authenticated GCP user; for your own data, grant `roles/bigquery.dataViewer` to your account.

### The MCP indicator says "bigquery: 0 tools"

The server crashed on startup. Check your MCP client's logs (location varies by client; usually under your OS's standard app-logs directory).

The most common cause is a missing dependency. Re-run `uvx --no-cache mcp-bigquery-evals --help` to force a fresh install.

### Cost cap errors blocking your queries

The default cap is 100 MB scanned (≈ $0.0005). To raise it for a single query, instruct the agent:

> "Use the bigquery tool with max_bytes_scanned=2_000_000_000 to run [your query]"

The cap is per-call; the agent can raise it explicitly for any query that needs more. There is no global default override in v0.1.0 - a `MCP_BIGQUERY_MAX_BYTES_SCANNED` env var is on the v0.1.x roadmap.
