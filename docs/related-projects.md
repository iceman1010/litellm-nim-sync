# Related Projects

> Back to [index](index.md)

This project is small on purpose — one script — but it sits in the middle of
a few other projects in the same family. This page maps the connections so
nobody has to rediscover them. (Internal infrastructure details are kept in
private ops docs; this public page stays generic.)

## Map

```
NVIDIA NIM (upstream, integrate.api.nvidia.com)
        │
        │  GET /v1/models (this script, manual run)
        ▼
litellm-nim-sync ──POST /model/new──▶ LiteLLM proxy
                                        │  config.yaml = curated models (untouched)
                                        │  DB         = nim/* synced models
                                        ▼
                     ┌──────────────────┴──────────────────┐
                     ▼                                     ▼
             llm-srt-translate                 coding-assistant tooling
             (subtitle translator,               (live traffic — the reason
              calls proxy models)                 config.yaml is untouchable)
```

## The projects

### `llm-srt-translate` — origin of this project

PHP-based SRT subtitle translator that calls models through the LiteLLM
proxy.

- Its translation runs exposed the original pain: a model list in the
  proxy's `config.yaml` goes stale, and every new NIM model needs a manual
  server edit.
- The sync work was first planned inside that repo before being spun out
  into this project.
- Its internal docs cover the proxy from the **client** perspective
  (endpoints, auth, model selection). This repo documents it from the
  **sync/operator** side. Keep the split; don't duplicate.

### `cf-llm-srt-translator` — predecessor, still deployed

Earlier Cloudflare-based translator. Historical interest mostly; no live
connection to this project.

### `glm-srt-translate` — discontinued ancestor

The original GLM-direct translator that motivated the LiteLLM proxy's
creation. Read its README for the historical "why a proxy at all". No live
connection to this project.

## Rule of thumb

- Model catalogue automation → **this repo**.
- How to *call* the proxy as a client → the client project's docs.
- How the proxy *itself* is installed/configured → the internal ops docs.
