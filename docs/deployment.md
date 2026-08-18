# Deployment & Runbook

> Back to [index](index.md)

The script runs **manually** on the LiteLLM host. No cron. No restarts. No
config edits. (Host-specific details — machine names, env file locations,
who runs it — live in the internal ops docs, not in this public repo.)

## Install / update on the server

Preferred (script updates itself):

```bash
sudo python3 /opt/litellm-sync/sync_nvidia_models.py --self-update
```

First install, or if self-update can't reach GitHub — from a checkout of
this repo:

```bash
scp sync_nvidia_models.py <litellm-host>:/tmp/
ssh <litellm-host> 'sudo install -m 755 -D /tmp/sync_nvidia_models.py \
    /opt/litellm-sync/sync_nvidia_models.py'
```

`sudo install` sets owner root:root and mode in one step (world-readable is
fine — the script holds no secrets, it only reads env var *names*).

## Auth setup (once)

Preferred: a **virtual key** with model-management routes (created in the
LiteLLM admin UI), exported as `LITELLM_SYNC_KEY` when running. If it's
missing the script falls back to `LITELLM_MASTER_KEY`, which works but is
more power than the task needs.

`NVIDIA_NIM_API_KEY` must also be in the environment; a typical run wrapper
sources the proxy's env file via sudo. Never write keys to disk.

## Run procedure

1. **Dry run** (writes nothing, shows planned additions + upstream removals):
   ```bash
   sudo python3 /opt/litellm-sync/sync_nvidia_models.py --dry-run
   ```
   (with `NVIDIA_NIM_API_KEY` and the proxy key in the environment — see above)
2. Eyeball the `+ nim/...` list — anything that looks like a non-LLM means the
   `JUNK` filter needs a new pattern (fix in this repo, `--self-update` on the
   host, don't hand-edit on the server).
3. **Real run** — same command without `--dry-run`.
4. Verify:
   ```bash
   # nim/* models present, curated config models unchanged, no restart happened
   curl -s -H "Authorization: Bearer <MASTER_KEY>" http://localhost:4000/v1/models \
       | python3 -c 'import json,sys; [print(m["id"]) for m in json.load(sys.stdin)["data"]]'

   # one real completion through a synced model
   curl -s -H "Authorization: Bearer <MASTER_KEY>" -H "Content-Type: application/json" \
       http://localhost:4000/v1/chat/completions \
       -d '{"model":"nim/openai/gpt-oss-120b","messages":[{"role":"user","content":"ping"}]}' \
       | head -c 300
   ```

## What the script will never do (safety invariants)

- Write to the proxy's `config.yaml` or env file.
- Restart (or otherwise touch) the `litellm` systemd unit.
- Delete a model — upstream-disappeared models are printed for human review;
  removal happens manually in the admin UI if ever.
- The one file it *can* write is itself, via `--self-update` (atomic replace
  after validating the download compiles).

## Rollback

- Bad script version: `sudo .../sync_nvidia_models.py --self-update` again
  after fixing main, or reinstall via `scp` + `install` as above.
- Mistakenly added models: remove in the LiteLLM admin UI (Models → delete
  the `nim/...` entry). DB-only changes; the curated config models are
  unaffected either way.
