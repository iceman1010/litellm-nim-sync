#!/usr/bin/env python3
"""Manually sync NVIDIA NIM LLM models into the LiteLLM proxy DATABASE.

Design constraints (do not violate):
  - Never touches the proxy's config.yaml — live traffic depends on it.
  - Never restarts the proxy. Never deletes models.
  - Adds models via POST /model/new -> DB (store_model_in_db: true), live
    immediately, no restart.
  - Alias scheme: nim/<full-upstream-id>  e.g. nim/meta/llama-3.3-70b-instruct
  - --self-update replaces this script with the latest version from GitHub.

Run (on the LiteLLM host, with the proxy env vars in the environment):
    sudo python3 /opt/litellm-sync/sync_nvidia_models.py --dry-run

Auth (environment variables):
  - Proxy:   $LITELLM_SYNC_KEY if set (virtual key with model-management
             routes), else falls back to $LITELLM_MASTER_KEY.
  - Upstream: $NVIDIA_NIM_API_KEY.

Stdlib only (no pip deps). Python 3.8+.
"""

import argparse
import json
import os
import re
import stat
import sys
import time
import urllib.error
import urllib.request

__version__ = "1.1.0"

GITHUB_RAW = "https://raw.githubusercontent.com/iceman1010/litellm-nim-sync/main"
SELF_UPDATE_URL = GITHUB_RAW + "/sync_nvidia_models.py"
VERSION_URL = GITHUB_RAW + "/VERSION"

UPSTREAM_URL = "https://integrate.api.nvidia.com/v1/models"
DEFAULT_BASE = "http://localhost:4000"

# Case-insensitive substring exclusions: embedding/rerank/guard/vision/reward/
# parsing/multimodal-omni/calibration models etc. Review via --dry-run.
JUNK = re.compile(
    r"embed|rerank|guard|safety|vision|riva|usd|gliner|ocr|clip|sdxl|"
    r"stable-diffusion|flux|neva|vila|deplot|caption|tts|asr|retrieve|"
    r"bge|fuyu|kosmos|reward|parse|-vl|video-detector|omni|calibration",
    re.I,
)

# Upstream ids already mapped by curated aliases in the proxy's config.yaml.
# The sync skips these (they already have curated short aliases).
ALREADY_MAPPED = {
    "moonshotai/kimi-k2.6",
    "nvidia/nemotron-3-ultra-550b-a55b",
    "z-ai/glm-5.2",
    "deepseek-ai/deepseek-v4-pro",
    "mistralai/mistral-large-3-675b-instruct-2512",
    "deepseek-ai/deepseek-coder-6.7b-instruct",
    "qwen/qwen3.5-397b-a17b",
}

RETRY_CODES = {429, 500, 502, 503, 504}


def http_json(method, url, key, body=None, timeout=60):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", "Bearer %s" % key)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode()
            return json.loads(raw) if raw.strip() else {}
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            detail = e.read().decode()[:300]
        except Exception:
            pass
        raise RuntimeError("HTTP %s %s %s: %s" % (e.code, method, url, detail)) from e


def get_with_retry(url, key, tries=3):
    last = None
    for attempt in range(tries):
        try:
            return http_json("GET", url, key)
        except RuntimeError as e:
            last = e
            if any(("HTTP %d " % c) in str(e) for c in RETRY_CODES) and attempt < tries - 1:
                wait = 5 * (attempt + 1)
                print("  retry in %ds (%s)" % (wait, str(e)[:120]))
                time.sleep(wait)
                continue
            raise
    raise last


def http_text(url, timeout=30):
    """Plain unauthenticated GET returning text (for GitHub self-update)."""
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return resp.read().decode()
    except urllib.error.HTTPError as e:
        raise RuntimeError("HTTP %s GET %s" % (e.code, url)) from e


def _self_update(force=False):
    """Replace this script with the latest main-branch copy from GitHub.

    The ONLY place in this file that writes to disk (enforced by CI).
    """
    remote_version = http_text(VERSION_URL).strip()
    if remote_version == __version__ and not force:
        print("self-update: already at latest version (%s)" % __version__)
        return
    print("self-update: %s -> %s" % (__version__, remote_version))
    src = http_text(SELF_UPDATE_URL)
    if not src.startswith("#!"):
        raise RuntimeError("downloaded file does not look like this script")
    if "__version__" not in src:
        raise RuntimeError("downloaded file is missing __version__")
    compile(src, SELF_UPDATE_URL, "exec")  # refuse to install garbage
    here = os.path.abspath(__file__)
    tmp = here + ".new"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(src)
    os.chmod(tmp, stat.S_IMODE(os.stat(here).st_mode))
    os.replace(tmp, here)
    print("self-update: installed %s" % remote_version)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--base-url", default=DEFAULT_BASE,
                    help="LiteLLM proxy base URL (default %(default)s)")
    ap.add_argument("--dry-run", action="store_true",
                    help="show planned additions/removals, write nothing")
    ap.add_argument("--self-update", action="store_true",
                    help="download the latest version from GitHub and "
                         "replace this script, then exit")
    ap.add_argument("--force", action="store_true",
                    help="with --self-update: reinstall even if same version")
    args = ap.parse_args()

    if args.self_update:
        _self_update(force=args.force)
        return 0

    proxy_key = os.environ.get("LITELLM_SYNC_KEY") or os.environ.get("LITELLM_MASTER_KEY")
    nvidia_key = os.environ.get("NVIDIA_NIM_API_KEY")
    if not proxy_key:
        sys.exit("ERROR: set LITELLM_SYNC_KEY or LITELLM_MASTER_KEY")
    if not nvidia_key:
        sys.exit("ERROR: set NVIDIA_NIM_API_KEY")

    print("== pulling NVIDIA upstream catalogue ==")
    upstream = get_with_retry(UPSTREAM_URL, nvidia_key)
    upstream_ids = sorted(m["id"] for m in upstream["data"])
    llm_ids = [i for i in upstream_ids if not JUNK.search(i)]
    junk_ids = [i for i in upstream_ids if JUNK.search(i)]
    print("upstream: %d total, %d pass LLM filter, %d filtered out"
          % (len(upstream_ids), len(llm_ids), len(junk_ids)))

    print("== pulling current proxy model list ==")
    proxy = get_with_retry(args.base_url.rstrip("/") + "/v1/models", proxy_key)
    proxy_ids = sorted(m["id"] for m in proxy["data"])
    print("proxy currently exposes %d models" % len(proxy_ids))

    existing = set(proxy_ids)
    to_add = []
    for uid in llm_ids:
        alias = "nim/" + uid
        if alias in existing:
            continue
        if uid in ALREADY_MAPPED:
            print("  skip (config alias exists): %s" % uid)
            continue
        to_add.append((alias, uid))

    synced = {i[len("nim/"):] for i in existing if i.startswith("nim/")}
    gone = sorted(synced - set(llm_ids))
    if gone:
        print("!! upstream no longer lists these synced models (NOT deleting; "
              "remove manually in the admin UI if really dead):")
        for g in gone:
            print("    -", g)

    if not to_add:
        print("nothing to add — proxy is in sync.")
        return 0

    print("== planned additions (%d) ==" % len(to_add))
    for alias, uid in to_add:
        print("    + %s  <-  %s" % (alias, uid))
    if args.dry_run:
        print("dry-run: no changes written.")
        return 0

    print("== adding via /model/new (DB, no restart) ==")
    ok, failed = 0, []
    for alias, uid in to_add:
        payload = {
            "model_name": alias,
            "litellm_params": {
                "model": "nvidia_nim/" + uid,
                "api_key": "os.environ/NVIDIA_NIM_API_KEY",
            },
        }
        try:
            http_json("POST", args.base_url.rstrip("/") + "/model/new", proxy_key, payload)
            print("    ok:", alias)
            ok += 1
        except RuntimeError as e:
            print("    FAIL:", alias, "->", str(e)[:200])
            failed.append(alias)

    print("== verifying ==")
    proxy2 = get_with_retry(args.base_url.rstrip("/") + "/v1/models", proxy_key)
    nim_now = sorted(m["id"] for m in proxy2["data"] if m["id"].startswith("nim/"))
    print("nim/* models now on proxy: %d (added ok: %d, failed: %d)"
          % (len(nim_now), ok, len(failed)))
    if failed:
        print("FAILED aliases:")
        for f in failed:
            print("    ?", f)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
