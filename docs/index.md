# litellm-nim-sync — Docs

> Back to [README](../README.md)

Syncs NVIDIA NIM's live model catalogue into the LiteLLM proxy **database**
(never `config.yaml`, never a restart, never a deletion).

## Pages

| Topic | File |
|-------|------|
| Related projects & how they connect | [`related-projects.md`](related-projects.md) |
| Deployment & runbook | [`deployment.md`](deployment.md) |

## One-paragraph summary

The LiteLLM proxy serves live coding-assistant traffic and its curated model
list lives in `config.yaml` — untouchable by automation. This project's
single script (`sync_nvidia_models.py`) pulls
`https://integrate.api.nvidia.com/v1/models`, filters out non-LLM models,
and adds the rest under the `nim/` namespace via the LiteLLM Admin API
(`POST /model/new`), which persists to PostgreSQL (`store_model_in_db: true`)
and takes effect immediately. Run manually; no cron by design. Updates
itself from this repo's main branch via `--self-update`.
