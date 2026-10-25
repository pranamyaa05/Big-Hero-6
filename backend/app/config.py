"""Settings, read from environment variables when a Settings() is created (see .env.example)."""
from __future__ import annotations
import os
import re
from dataclasses import dataclass, field, asdict, fields
from pathlib import Path
from typing import Callable


def _env(name: str, default, cast: Callable = str):
    """A dataclass field whose value is read from the environment at construction time (not at import time)."""
    def read():
        raw = os.environ.get(name)
        if raw is None or raw == "":
            return default
        try:
            if cast is bool:
                return raw.strip().lower() in ("1", "true", "yes", "on")
            return cast(raw)
        except ValueError:
            return default
    return field(default_factory=read)


def _list(raw: str) -> list[str]:
    return [o.strip() for o in raw.split(",") if o.strip()]


# provider -> (OpenAI-compatible base URL, environment variable holding its API key, whether it accepts pictures when used as a pool member by default)
# "{NAME}" inside a URL is filled from the environment variable NAME.
PRESETS: dict[str, tuple[str, str, bool]] = {
    "gemini": ("https://generativelanguage.googleapis.com/v1beta/openai", "GEMINI_API_KEY", True),
    "openrouter": ("https://openrouter.ai/api/v1", "OPENROUTER_API_KEY", False),
    "groq": ("https://api.groq.com/openai/v1", "GROQ_API_KEY", False),
    "cerebras": ("https://api.cerebras.ai/v1", "CEREBRAS_API_KEY", False),
    "nvidia": ("https://integrate.api.nvidia.com/v1", "NVIDIA_API_KEY", False),
    "mistral": ("https://api.mistral.ai/v1", "MISTRAL_API_KEY", True),
    "sambanova": ("https://api.sambanova.ai/v1", "SAMBANOVA_API_KEY", False),
    "cloudflare": ("https://api.cloudflare.com/client/v4/accounts/{CLOUDFLARE_ACCOUNT_ID}/ai/v1", "CLOUDFLARE_API_TOKEN", False),
    "deepseek": ("https://api.deepseek.com", "DEEPSEEK_API_KEY", False),
    "zai": ("https://api.z.ai/api/paas/v4", "ZAI_API_KEY", False),
    "ollama": ("http://localhost:11434/v1", "", False),
    "openai": ("", "OPENAI_API_KEY", True),
}


@dataclass(frozen=True)
class PoolMember:
    """One model the server may call. The API key is kept out of repr so it cannot reach a log by accident."""
    kind: str                       # "openai" (any OpenAI-compatible server) or "anthropic"
    provider: str                   # preset name, used in labels
    model: str
    base_url: str
    api_key: str = field(default="", repr=False)
    vision: bool = True

    @property
    def label(self) -> str:
        return f"{self.provider}/{self.model}"


def parse_pool(raw: str, env=None, default_vision: bool = True) -> tuple[list[PoolMember], list[str]]:
    """Parse REFORM3D_LLM_POOL: entries `provider=model` separated by commas, semicolons or new lines. Add `+text` after the model for a model that
    cannot see pictures, or `+vision` for one that can when the provider's default says otherwise. Entries whose key is missing are skipped.
    Returns (members, reasons for skipped entries); a reason names the missing variable, never a key."""
    env = os.environ if env is None else env
    members: list[PoolMember] = []
    skipped: list[str] = []
    seen: set[str] = set()
    for entry in re.split(r"[,;\n]", (raw or "").strip().strip("\"'")):          # `docker --env-file` keeps the quotes of a quoted value
        entry = entry.strip()
        if not entry:
            continue
        provider, eq, rest = entry.partition("=")
        provider, model = provider.strip().lower(), rest.strip()
        slot = ""                                      # "gemini:2=model" uses GEMINI_API_KEY_2: a second key (another person's account) with its own quota
        m_slot = re.fullmatch(r"([a-z]+):(\d+)", provider)
        if m_slot:
            provider, slot = m_slot.group(1), m_slot.group(2)
        vision_flag = None
        for flag, value in (("+text", False), ("+vision", True)):
            if model.lower().endswith(flag):
                model, vision_flag = model[: -len(flag)].strip(), value
        if not eq or not model:
            skipped.append(f"'{entry}': write it as provider=model")
            continue
        if provider != "anthropic" and provider not in PRESETS:
            skipped.append(f"'{provider}': unknown provider (known: anthropic, {', '.join(PRESETS)})")
            continue
        if provider == "anthropic":
            kind, key_env = "anthropic", "ANTHROPIC_API_KEY" + (f"_{slot}" if slot else "")
            key, base, default = env.get(key_env, ""), "", True
        else:
            base, key_env, default = PRESETS[provider]
            if slot and key_env:
                key_env = f"{key_env}_{slot}"
            key = env.get(key_env, "") if key_env else ""
            kind = "openai"
            missing = [n for n in re.findall(r"\{(\w+)\}", base) if not env.get(n)]
            if missing:
                skipped.append(f"{provider}/{model}: {missing[0]} is not set")
                continue
            base = re.sub(r"\{(\w+)\}", lambda m: env.get(m.group(1), ""), base)
            if not base:
                skipped.append(f"{provider}/{model}: this provider needs a base URL; use REFORM3D_LLM_PROVIDER=openai with REFORM3D_LLM_BASE_URL instead")
                continue
        if key_env and not key:
            skipped.append(f"{provider}/{model}: {key_env} is not set")
            continue
        vision = default_vision and (default if vision_flag is None else vision_flag)
        member = PoolMember(kind, provider + (f":{slot}" if slot else ""), model, base, key, vision)
        if member.label not in seen:
            seen.add(member.label)
            members.append(member)
    return members, skipped


@dataclass
class Settings:
    data_dir: Path = field(default_factory=lambda: Path(os.environ.get("REFORM3D_DATA_DIR") or "./data").resolve())
    api_key: str = _env("REFORM3D_API_KEY", "")                               # optional: require X-API-Key on POST and DELETE
    cors_origins: list = field(default_factory=lambda: _list(os.environ.get("REFORM3D_CORS_ORIGINS") or "*"))
    llm_provider: str = _env("REFORM3D_LLM_PROVIDER", "anthropic")           # anthropic | openai | gemini | openrouter | groq | deepseek | zai | ollama (see app/llm.py)
    llm_base_url: str = _env("REFORM3D_LLM_BASE_URL", "")                    # for openai-style servers
    llm_api_key: str = _env("REFORM3D_LLM_API_KEY", "")                      # falls back to ANTHROPIC_API_KEY / GEMINI_API_KEY / ... by provider
    llm_model: str = _env("REFORM3D_LLM_MODEL", "")                          # falls back to ANTHROPIC_MODEL, then claude-sonnet-5-5 for anthropic
    llm_timeout_s: float = _env("REFORM3D_LLM_TIMEOUT", 120.0, float)
    llm_vision: bool = _env("REFORM3D_LLM_VISION", True, bool)               # false for text-only models: photos are not sent and the review uses measurements, not a picture
    llm_pool: str = _env("REFORM3D_LLM_POOL", "")                            # several models, tried in order: provider=model,provider=model+text (see README)
    enable_llm: bool = _env("REFORM3D_ENABLE_LLM", True, bool)               # false forces the offline template mode
    enable_design: bool = _env("REFORM3D_ENABLE_DESIGN", True, bool)         # AI designs new parts from scratch (needs a model; read the README security notes)
    design_attempts: int = _env("REFORM3D_DESIGN_ATTEMPTS", 4, int)          # code attempts, each with the previous error fed back
    review_rounds: int = _env("REFORM3D_REVIEW_ROUNDS", 1, int)              # times the model is shown a render of its own result to self-correct
    design_candidates: int = _env("REFORM3D_DESIGN_CANDIDATES", 1, int)      # >1: that many different pool models design the same part at once (uses that many times the quota)
    design_race: str = _env("REFORM3D_DESIGN_RACE", "first")                 # first = first valid design wins; best = wait a little and keep the best-ranked one
    design_race_grace_s: float = _env("REFORM3D_DESIGN_RACE_GRACE", 60.0, float)   # race=best: how long to wait for the others once one design is valid
    prompt_lean: bool = _env("REFORM3D_PROMPT_LEAN", False, bool)           # shorter standing prompt (about 3k tokens instead of 5k) for providers with a small tokens-per-minute limit (Groq free)
    design_cache: bool = _env("REFORM3D_DESIGN_CACHE", True, bool)           # an identical request reuses the earlier design instead of calling the model again
    template_fallback: bool = _env("REFORM3D_TEMPLATE_FALLBACK", True, bool) # auto mode: if no model can be reached, use the closest ready-made template
    design_timeout_s: float = _env("REFORM3D_DESIGN_TIMEOUT", 40.0, float) # wall-clock limit for running one design's code
    design_memory_mb: int = _env("REFORM3D_DESIGN_MEMORY_MB", 1536, int)
    workers: int = _env("REFORM3D_WORKERS", 2, int)
    job_timeout_s: float = _env("REFORM3D_JOB_TIMEOUT", 120.0, float)
    rate_limit_per_min: int = _env("REFORM3D_RATE_LIMIT", 20, int)           # per client IP, 0 disables
    max_upload_mb: float = _env("REFORM3D_MAX_UPLOAD_MB", 8.0, float)
    max_photos: int = 3
    keep_photos: bool = _env("REFORM3D_KEEP_PHOTOS", False, bool)            # photos are only used for planning unless this is on
    bed_x: float = _env("REFORM3D_BED_X", 220.0, float)
    bed_y: float = _env("REFORM3D_BED_Y", 220.0, float)
    bed_z: float = _env("REFORM3D_BED_Z", 250.0, float)
    retention_days: int = _env("REFORM3D_RETENTION_DAYS", 14, int)
    render_preview: bool = _env("REFORM3D_RENDER_PREVIEW", True, bool)
    slicer: str = _env("REFORM3D_SLICER", "auto")                            # PrusaSlicer for real print time, plastic and support numbers: auto (use it if installed), off, or a path
    slicer_in_loop: bool = _env("REFORM3D_SLICER_LOOP", True, bool)          # the design loop slices each attempt and tells the model how much support it needs
    slicer_timeout_s: float = _env("REFORM3D_SLICER_TIMEOUT", 60.0, float)
    trust_proxy: bool = _env("REFORM3D_TRUST_PROXY", False, bool)            # honour X-Forwarded-For (only behind a proxy you control)
    pool_entries: list = field(default_factory=list, init=False, repr=False)   # models parsed from llm_pool
    pool_skipped: list = field(default_factory=list, init=False, repr=False)   # why an llm_pool entry was left out (never contains a key)
    llm_provider_name: str = field(default="", init=False)                     # the provider as the operator wrote it, e.g. "groq" (llm_provider becomes "openai")

    def __post_init__(self) -> None:
        prov = (self.llm_provider or "anthropic").strip().lower()
        self.llm_provider_name = prov if (prov in PRESETS or prov == "anthropic") else "anthropic"
        if prov in PRESETS:
            base, key_env, _ = PRESETS[prov]
            base = re.sub(r"\{(\w+)\}", lambda m: os.environ.get(m.group(1), ""), base)
            self.llm_base_url = self.llm_base_url or base
            self.llm_api_key = self.llm_api_key or (os.environ.get(key_env, "") if key_env else "")
            prov = "openai"
        else:
            prov = "anthropic"
            self.llm_api_key = self.llm_api_key or os.environ.get("ANTHROPIC_API_KEY", "")
            self.llm_model = self.llm_model or os.environ.get("ANTHROPIC_MODEL", "") or "claude-sonnet-5-5"
        self.llm_provider = prov
        self.design_race = "best" if str(self.design_race).strip().lower() == "best" else "first"
        self.pool_entries, self.pool_skipped = parse_pool(self.llm_pool, os.environ, self.llm_vision)

    @property
    def primary_configured(self) -> bool:
        """The single-model settings (REFORM3D_LLM_PROVIDER / MODEL / KEY) are complete."""
        if self.llm_provider == "openai":
            return bool(self.llm_base_url and self.llm_model)
        return bool(self.llm_api_key)

    @property
    def llm_configured(self) -> bool:
        return self.primary_configured or bool(self.pool_entries)

    @property
    def uses_pool(self) -> bool:
        return bool(self.pool_entries)

    def models(self) -> list[PoolMember]:
        """Every model this server may call, in priority order: the single-model settings first (if complete), then the pool entries."""
        out: list[PoolMember] = []
        if self.primary_configured:
            out.append(PoolMember(self.llm_provider, self.llm_provider_name, self.llm_model, self.llm_base_url, self.llm_api_key, self.llm_vision))
        labels = {m.label for m in out}
        return out + [m for m in self.pool_entries if m.label not in labels]

    @property
    def timeout_for_llm(self) -> float:
        return self.llm_timeout_s

    def ensure_dirs(self) -> None:
        for sub in ("jobs", "uploads"):
            (self.data_dir / sub).mkdir(parents=True, exist_ok=True)

    def for_worker(self) -> dict:
        """The few settings the build subprocess needs, so it follows this instance's configuration rather than re-reading the environment."""
        return {"bed_x": self.bed_x, "bed_y": self.bed_y, "bed_z": self.bed_z, "render_preview": self.render_preview, "slicer": self.slicer,
                "slicer_in_loop": self.slicer_in_loop, "slicer_timeout_s": self.slicer_timeout_s}


def get_settings() -> Settings:
    return Settings()
