# litellm-nim-sync

Keeps the [LiteLLM](https://docs.litellm.ai/docs/simple_proxy) proxy's NVIDIA NIM
model catalogue in sync with NVIDIA's live `/v1/models` endpoint — **in the
LiteLLM database**, never in `config.yaml`.

## Why this exists

The LiteLLM proxy routes live coding-assistant traffic. Its `config.yaml`
defines the hand-curated models that traffic depends on, so it must never be
edited by automation. This script instead uses the
LiteLLM Admin API (`POST /model/new` with `store_model_in_db: true`), which:

- writes models to the PostgreSQL-backed DB — **live immediately, no restart**;
- **never touches** `config.yaml`;
- **never deletes** models that disappear upstream (they are reported for human
  review only — something may still be calling them).

## What it does

1. Pulls `GET https://integrate.api.nvidia.com/v1/models` (retries on 429/5xx).
2. Filters out non-LLM models (embeddings, rerankers, guards, vision, reward,
   parsers, omni-multimodal, etc.).
3. Skips upstream ids that already have curated aliases in `config.yaml`.
4. Adds everything else under the `nim/` namespace: alias
   `nim/meta/llama-3.3-70b-instruct` → upstream `meta/llama-3.3-70b-instruct`
   (collision-free by construction).
5. Reports synced models the upstream no longer lists — log only, no deletion.

## Usage

Run **manually** on the LiteLLM host (no cron by design), with the proxy's
env vars in the environment:

```bash
# dry run — shows planned additions/removals, writes nothing
sudo python3 /opt/litellm-sync/sync_nvidia_models.py --dry-run

# real run — same, without --dry-run

# self-update — fetch the latest version from this repo's main branch and
# atomically replace this script (validates the download first)
sudo python3 /opt/litellm-sync/sync_nvidia_models.py --self-update
```

Requires Python 3.8+, **stdlib only** (no pip installs on the host).

## Configuration

Everything via environment variables — no secrets live in this repo, ever.

| Variable | Purpose |
|----------|---------|
| `NVIDIA_NIM_API_KEY` | Upstream NVIDIA key (required) |
| `LITELLM_SYNC_KEY` | Proxy key for `/model/new` — use a virtual key with model-management routes, **not** the master key |
| `LITELLM_MASTER_KEY` | Fallback if `LITELLM_SYNC_KEY` is unset |

Proxy base URL defaults to `http://localhost:4000`; override with `--base-url`.

## Safety invariants (do not weaken in PRs)

- No writes to the proxy's `config.yaml` or env file.
- No `systemctl` calls of any kind — the proxy is never restarted.
- No deletions via the API, ever.
- The only file the script may write is itself, via `--self-update`
  (CI-enforced: file writes are confined to the `_self_update` function).
- No secrets in code, tests, fixtures, CI logs, or docs.

## Deploy to the LiteLLM host

```bash
scp sync_nvidia_models.py <litellm-host>:/tmp/
ssh <litellm-host> 'sudo install -m 755 -D /tmp/sync_nvidia_models.py \
    /opt/litellm-sync/sync_nvidia_models.py'
```

After that, updates are a one-liner on the host:
`sudo python3 /opt/litellm-sync/sync_nvidia_models.py --self-update`

## Development

```bash
python3 -m pip install -r requirements-dev.txt
ruff check .
pytest
```

CI (GitHub Actions): lint + unit tests on every push/PR. The unit tests cover
the junk filter and alias logic against a frozen snapshot of the public NVIDIA
catalogue (public model ids only — no credentials involved).
