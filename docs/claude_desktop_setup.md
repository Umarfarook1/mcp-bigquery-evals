# Claude Desktop Setup

This guide walks through wiring `mcp-bigquery-evals` into Claude Desktop on macOS, Windows, and Linux.

## Prerequisites

- Claude Desktop installed (latest version)
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

## 2. Find your `claude_desktop_config.json`

| OS | Path |
|---|---|
| macOS | `~/Library/Application Support/Claude/claude_desktop_config.json` |
| Windows | `%APPDATA%\Claude\claude_desktop_config.json` |
| Linux | `~/.config/Claude/claude_desktop_config.json` |

If the file doesn't exist, create it with `{}`.

## 3. Add the MCP server

```json
{
  "mcpServers": {
    "bigquery": {
      "command": "uvx",
      "args": ["mcp-bigquery-evals", "serve"],
      "env": {
        "BIGQUERY_PROJECT": "your-project-id"
      }
    }
  }
}
```

If you don't have `uv` installed, swap `command` to your `python` and use `args: ["-m", "mcp_bigquery_evals", "serve"]` after `pip install mcp-bigquery-evals` into a venv whose python is on PATH.

## 4. Restart Claude Desktop

Fully quit Claude Desktop (not just close window) and reopen. You should see "bigquery" listed in the MCP indicator (the small icon at the bottom of the chat input). Click it to confirm 7 tools are available.

## 5. Verify

Ask Claude:
> "Using the bigquery tool, list the datasets in my project."

If you see a list, you're done. If you see an error, see Troubleshooting below.

## Troubleshooting

### "BIGQUERY_PROJECT env var is required"

The `env` block in your config wasn't passed through. Double-check the JSON is valid (no trailing commas) and restart Claude Desktop fully.

### `unauthenticated` error / "Reauthentication is needed"

Run `gcloud auth application-default login` again. ADC tokens expire periodically.

### `permission_denied` when listing tables

Your account doesn't have BigQuery Data Viewer on the dataset. For `bigquery-public-data`, this is granted by default to any authenticated GCP user; for your own data, grant `roles/bigquery.dataViewer` to your account.

### The MCP indicator says "bigquery: 0 tools"

The server crashed on startup. Check Claude Desktop's MCP logs:
- macOS: `~/Library/Logs/Claude/mcp-server-bigquery.log`
- Windows: `%APPDATA%\Claude\Logs\mcp-server-bigquery.log`

The most common cause is a missing dependency. Re-run `uvx --no-cache mcp-bigquery-evals --help` to force a fresh install.

### Cost cap errors blocking your queries

The default cap is 100 MB scanned. To raise it for a single query, ask Claude:
> "Use the bigquery tool with max_bytes_scanned=2_000_000_000 to run [your query]"

To change the default permanently, fork this repo and patch `DEFAULT_MAX_BYTES_SCANNED` in `src/mcp_bigquery_evals/guardrails.py`.
