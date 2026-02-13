# CLAUDE.md

## Project Overview

Claude Agent SDK (Python) backend deployed on Google Cloud Run with Firestore-backed session persistence. FastAPI serves a `/chat` endpoint that runs the Claude agent with a dummy weather MCP tool, persists conversations to Firestore, and supports session resume.

## Tech Stack

- **Runtime**: Python 3.12, FastAPI, Uvicorn
- **Agent**: `claude-agent-sdk` (Python) — uses bundled CLI internally
- **Database**: Google Cloud Firestore (Native mode)
- **Persistence**: GCS FUSE volume mount for `~/.claude/` session data
- **Deployment**: Google Cloud Run (gen2, source deploy)
- **Config**: pydantic-settings, env vars / `.env` file

## GCP Details

| Setting | Value |
|---|---|
| Project ID | `$GCP_PROJECT_ID` |
| Region | `us-central1` |
| Cloud Run service | `claude-agent-api` |
| Service Account | `<PROJECT_NUMBER>-compute@developer.gserviceaccount.com` |
| Firestore collection | `sessions` |
| GCS bucket | `claude-sessions-<GCP_PROJECT_ID>` |

## Key Architecture Decisions

### Streaming prompt (CRITICAL)

When using `query()` with SDK MCP servers (`create_sdk_mcp_server`), you **must** pass an async generator as `prompt`, not a plain string. String prompts launch the CLI in `--print` mode which closes stdin immediately, but SDK MCP tools need bidirectional stdin/stdout for the control protocol (CLI sends tool invocation requests, SDK writes results back). Always use the `_streaming_prompt()` wrapper in `app/services/agent.py`.

### Non-root Docker container

`permission_mode="bypassPermissions"` maps to `--dangerously-skip-permissions` in the CLI, which **refuses to run as root**. The Dockerfile creates and switches to `appuser`.

### Bundled CLI — do not install separately

The `claude-agent-sdk` pip package bundles its own CLI at `claude_agent_sdk/_bundled/claude`. Do **not** install Claude Code separately via `curl -fsSL https://claude.ai/install.sh` — it's unnecessary and can cause version conflicts.

### GCS FUSE volume mount for session persistence

The SDK stores session data at `~/.claude/` on the container filesystem. Cloud Run containers are ephemeral, so we mount a GCS bucket at `/home/appuser/.claude` via GCS FUSE. This persists session data across container restarts so `resume` works reliably. Requires `--execution-environment gen2`.

### Two-layer persistence

1. **SDK internal** (`~/.claude/` → GCS FUSE) — used by the CLI for conversation context and `resume`, persisted to GCS bucket
2. **Firestore** — our read-optimized mirror for the API layer (history, costs, session listing)

Session data survives container recycling via GCS FUSE. Firestore data is never lost.

### Resume fallback

If `resume` fails (e.g., corrupted session data), `run_agent()` catches the error, logs a warning, and retries as a fresh session instead of returning a 500.

## Project Structure

```
app/
├── main.py              # FastAPI app, lifespan, CORS
├── config.py            # pydantic-settings (env vars)
├── routers/
│   ├── chat.py          # POST /chat
│   ├── sessions.py      # GET /sessions/{session_id}
│   └── health.py        # GET /health
├── services/
│   ├── agent.py         # Claude Agent SDK query() — CORE FILE
│   └── firestore.py     # Firestore session CRUD
├── models/
│   └── schemas.py       # Pydantic request/response models
└── tools/
    └── weather.py       # @tool decorator + create_sdk_mcp_server
```

## Common Commands

```bash
# Local dev
cp .env.example .env     # Fill in ANTHROPIC_API_KEY
pip install -r requirements.txt
uvicorn app.main:app --reload

# Deploy (replace $GCP_PROJECT_ID and $BUCKET_NAME with your values)
gcloud run deploy claude-agent-api \
    --source . --region us-central1 --project $GCP_PROJECT_ID \
    --platform managed --allow-unauthenticated \
    --execution-environment gen2 \
    --memory 1Gi --cpu 1 --timeout 300 \
    --set-secrets "ANTHROPIC_API_KEY=ANTHROPIC_API_KEY:latest" \
    --set-env-vars "GCP_PROJECT_ID=$GCP_PROJECT_ID" \
    --min-instances 0 --max-instances 3 \
    --session-affinity \
    --add-volume name=claude-sessions,type=cloud-storage,bucket=$BUCKET_NAME \
    --add-volume-mount volume=claude-sessions,mount-path=/home/appuser/.claude

# Test
curl https://<YOUR_SERVICE_URL>/health
curl -X POST https://<YOUR_SERVICE_URL>/chat \
    -H "Content-Type: application/json" \
    -d '{"message": "What is the weather in SF?"}'
```

## Gotchas

- `tools=[]` disables ALL built-in tools (Bash, Read, Write, etc.). Only set this if you truly want to restrict Claude to just your MCP tools. The default (`None`) keeps standard tools available.
- The `/chat` endpoint blocks until the full agent response completes (3-30s). No streaming to the client yet.
- Two simultaneous requests on the same session may race — no concurrent session safety.
