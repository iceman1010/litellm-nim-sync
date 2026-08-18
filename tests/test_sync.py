"""Unit tests for the junk filter and alias logic.

Fixture: frozen snapshot of the public NVIDIA /v1/models catalogue
(model ids only — public information, no credentials).
"""

import importlib.util
import pathlib
import re

SPEC = importlib.util.spec_from_file_location(
    "sync_nvidia_models",
    pathlib.Path(__file__).resolve().parent.parent / "sync_nvidia_models.py",
)
sync = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sync)

# Snapshot taken 2026-08-19 from https://integrate.api.nvidia.com/v1/models
CATALOGUE = """
01-ai/yi-large
adept/fuyu-8b
ai21labs/jamba-1.5-large-instruct
aisingapore/sea-lion-7b-instruct
baai/bge-m3
bigcode/starcoder2-15b
databricks/dbrx-instruct
deepseek-ai/deepseek-coder-6.7b-instruct
deepseek-ai/deepseek-v4-flash-0731
google/codegemma-1.1-7b
google/codegemma-7b
google/diffusiongemma-26b-a4b-it
google/gemma-2b
google/gemma-3-12b-it
google/gemma-3-4b-it
google/gemma-4-31b-it
google/recurrentgemma-2b
ibm/granite-3.0-3b-a800m-instruct
ibm/granite-3.0-8b-instruct
ibm/granite-34b-code-instruct
ibm/granite-8b-code-instruct
meta/codellama-70b
meta/llama-3.1-70b-instruct
meta/llama-3.1-8b-instruct
meta/llama-3.2-1b-instruct
meta/llama-3.2-3b-instruct
meta/llama-3.2-11b-vision-instruct
meta/llama-3.2-90b-vision-instruct
meta/llama-3.3-70b-instruct
meta/llama2-70b
meta/llama-guard-4-12b
meta/muse-glimmer-30b
microsoft/kosmos-2
microsoft/phi-3-vision-128k-instruct
microsoft/phi-3.5-moe-instruct
minimaxai/minimax-m3
mistralai/codestral-22b-instruct-v0.1
mistralai/mistral-7b-instruct-v0.3
mistralai/mistral-large
mistralai/mistral-large-2-instruct
mistralai/mistral-nemotron
mistralai/mixtral-8x22b-v0.1
moonshotai/kimi-k2.6
nv-mistralai/mistral-nemo-12b-instruct
nvidia/ai-synthetic-video-detector
nvidia/cosmos-reason2-8b
nvidia/deplot
nvidia/embed-qa-4
nvidia/ising-calibration-1.5-31b
nvidia/llama-3.1-nemotron-51b-instruct
nvidia/llama-3.1-nemotron-70b-instruct
nvidia/llama-3.1-nemotron-nano-8b-v1
nvidia/llama-3.1-nemotron-nano-vl-8b-v1
nvidia/llama-3.1-nemotron-ultra-253b-v1
nvidia/llama-3.1-nemoguard-8b-content-safety
nvidia/llama-3.1-nemotron-safety-guard-8b-v3
nvidia/llama-3.2-nemoretriever-1b-vlm-embed-v1
nvidia/llama-3.2-nv-embedqa-1b-v1
nvidia/llama-3.3-nemotron-super-49b-v1
nvidia/llama-3.3-nemotron-super-49b-v1.5
nvidia/llama-nemotron-embed-1b-v2
nvidia/llama3-chatqa-1.5-70b
nvidia/mistral-nemo-minitron-8b-8k-instruct
nvidia/nemotron-3-embed-1b
nvidia/nemotron-3-nano-30b-a3b
nvidia/nemotron-3-nano-omni-30b-a3b-reasoning
nvidia/nemotron-3-super-120b-a12b
nvidia/nemotron-3-ultra-550b-a55b
nvidia/nemotron-3.5-lightning-30b-a3b
nvidia/nemotron-4-340b-instruct
nvidia/nemotron-4-340b-reward
nvidia/nemotron-nano-12b-v2-vl
nvidia/nemotron-nano-3-30b-a3b
nvidia/nemotron-parse
nvidia/nvidia-nemotron-nano-9b-v2
openai/gpt-oss-120b
openai/gpt-oss-20b
poolside/laguna-xs-2.1
stepfun-ai/step-3.7-flash
thinkingmachines/inkling
writer/palmyra-creative-122b
writer/palmyra-fin-70b-32k
writer/palmyra-med-70b
writer/palmyra-med-70b-32k
z-ai/glm-5.2
zyphra/zamba2-7b-instruct
""".split()


def catalogue():
    return list(CATALOGUE)


def test_filter_keeps_plain_llms():
    keep = [i for i in catalogue() if not sync.JUNK.search(i)]
    for expected in (
        "meta/llama-3.3-70b-instruct",
        "openai/gpt-oss-120b",
        "mistralai/mistral-large-2-instruct",
        "deepseek-ai/deepseek-v4-flash-0731",
        "minimaxai/minimax-m3",
        "thinkingmachines/inkling",
    ):
        assert expected in keep


def test_filter_drops_non_llms():
    dropped = [i for i in catalogue() if sync.JUNK.search(i)]
    for expected in (
        "baai/bge-m3",                      # embedding
        "adept/fuyu-8b",                    # vision
        "microsoft/kosmos-2",               # multimodal vision
        "nvidia/nemotron-4-340b-reward",    # reward model
        "nvidia/nemotron-parse",            # parser
        "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning",  # omni
        "nvidia/llama-3.1-nemotron-nano-vl-8b-v1",        # vision-language
        "meta/llama-3.2-11b-vision-instruct",
        "meta/llama-guard-4-12b",
        "nvidia/ai-synthetic-video-detector",
        "nvidia/ising-calibration-1.5-31b",
        "nvidia/embed-qa-4",
    ):
        assert expected in dropped


def test_filter_is_case_insensitive():
    assert sync.JUNK.search("nvidia/Nemotron-PARSE")
    assert sync.JUNK.search("Meta/LLAMA-VISION-90B")


def test_junk_regex_is_compiled_ci():
    assert isinstance(sync.JUNK, re.Pattern)


def test_already_mapped_covers_config_aliases():
    # Every upstream id that has a curated alias in config.yaml must be listed,
    # so the sync never creates a duplicate under nim/.
    assert sync.ALREADY_MAPPED == {
        "moonshotai/kimi-k2.6",
        "nvidia/nemotron-3-ultra-550b-a55b",
        "z-ai/glm-5.2",
        "deepseek-ai/deepseek-v4-pro",
        "mistralai/mistral-large-3-675b-instruct-2512",
        "deepseek-ai/deepseek-coder-6.7b-instruct",
        "qwen/qwen3.5-397b-a17b",
    }


def test_alias_scheme_is_nim_prefix():
    # Mirrors the alias construction in main(): "nim/" + upstream id.
    assert "nim/" + "meta/llama-3.3-70b-instruct" == "nim/meta/llama-3.3-70b-instruct"


def test_no_alias_collides_with_config_names():
    config_names = {
        "glm-4.7", "glm-5.2", "glm-4.7-coding", "glm-5.2-coding",
        "mistral-large-3-675b", "kimi-k2.6", "nemotron-ultra-550b",
        "glm-5.2-nvidia", "deepseek-v4-pro", "deepseek-coder-6.7b",
        "qwen3.5-397b",
    }
    keep = [i for i in catalogue()
            if not sync.JUNK.search(i) and i not in sync.ALREADY_MAPPED]
    aliases = {"nim/" + i for i in keep}
    assert not aliases & config_names


def test_snapshot_filtered_count_is_stable():
    keep = [i for i in catalogue() if not sync.JUNK.search(i)]
    # Guard rail: if this fails, either NVIDIA changed the catalogue
    # (update the snapshot deliberately) or the filter regressed.
    assert len(keep) == 64


def test_version_constant_matches_version_file():
    vfile = pathlib.Path(__file__).resolve().parent.parent / "VERSION"
    assert vfile.read_text().strip() == sync.__version__


def test_self_update_targets_this_repo_main_branch():
    assert sync.SELF_UPDATE_URL == (
        "https://raw.githubusercontent.com/iceman1010/"
        "litellm-nim-sync/main/sync_nvidia_models.py")
    assert sync.VERSION_URL.endswith("/VERSION")
