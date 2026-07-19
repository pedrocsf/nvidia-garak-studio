
from __future__ import annotations

import builtins
import contextlib
import functools
import importlib
import inspect
import pkgutil
from dataclasses import asdict, dataclass, field
from typing import Any

PLUGIN_CATEGORIES = ("probes", "detectors", "generators", "harnesses", "buffs")

_BASE_CLASS = {
    "probes": ("garak.probes.base", "Probe"),
    "detectors": ("garak.detectors.base", "Detector"),
    "generators": ("garak.generators.base", "Generator"),
    "harnesses": ("garak.harnesses.base", "Harness"),
    "buffs": ("garak.buffs.base", "Buff"),
}


@contextlib.contextmanager
def _utf8_open():
    original = builtins.open

    @functools.wraps(original)
    def _open(file, mode="r", *args, **kwargs):
        if "b" not in mode and "encoding" not in kwargs:
            kwargs["encoding"] = "utf-8"
        return original(file, mode, *args, **kwargs)

    builtins.open = _open
    try:
        yield
    finally:
        builtins.open = original


class GarakUnavailable(RuntimeError):
    pass


@dataclass
class PluginInfo:
    name: str
    category: str
    module: str
    class_name: str
    description: str = ""
    goal: str = ""
    tags: list[str] = field(default_factory=list)
    frameworks: dict[str, list[str]] = field(default_factory=dict)
    primary_detector: str | None = None
    extended_detectors: list[str] = field(default_factory=list)
    active: bool = True
    doc_url: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


def garak_available() -> bool:
    try:
        importlib.import_module("garak")
        return True
    except Exception:
        return False


def garak_version() -> str:
    garak = _import_garak()
    return getattr(garak, "__version__", "unknown")


def _import_garak():
    try:
        return importlib.import_module("garak")
    except Exception as exc:  # pragma: no cover
        raise GarakUnavailable(
            "garak is not importable in this environment. Install it with "
            "`pip install garak` into the same interpreter running this backend."
        ) from exc


def _extract_frameworks(tags: list[str]) -> dict[str, list[str]]:
    buckets: dict[str, list[str]] = {}
    for tag in tags or []:
        if not isinstance(tag, str) or ":" not in tag:
            continue
        prefix = tag.split(":", 1)[0].lower()
        key = {
            "owasp": "owasp",
            "avid-effect": "avid",
            "avid": "avid",
            "mitre-atlas": "mitre_atlas",
            "cwe": "cwe",
        }.get(prefix, prefix)
        buckets.setdefault(key, []).append(tag)
    return buckets


def _load_class(fq_name: str):
    garak = _import_garak()  # noqa: F841  (ensures garak on path)
    module_path, _, class_name = fq_name.rpartition(".")
    mod = importlib.import_module(f"garak.{module_path}")
    return getattr(mod, class_name)


def _plugin_info_from_class(fq_name: str, category: str, active: bool) -> PluginInfo:
    cls = _load_class(fq_name)
    module_path, _, class_name = fq_name.rpartition(".")
    doc = inspect.getdoc(cls) or ""
    tags = list(getattr(cls, "tags", []) or [])
    goal = getattr(cls, "goal", "") or ""

    primary = getattr(cls, "primary_detector", None)
    extended = list(getattr(cls, "extended_detectors", []) or [])
    doc_url = getattr(cls, "doc_uri", None) or getattr(cls, "uri", None)

    extra: dict[str, Any] = {}
    if category == "generators":
        for attr in ("supports_multiple_generations", "generator_family_name"):
            if hasattr(cls, attr):
                extra[attr] = getattr(cls, attr)

    return PluginInfo(
        name=fq_name,
        category=category,
        module=f"garak.{module_path}",
        class_name=class_name,
        description=doc.strip(),
        goal=goal.strip() if isinstance(goal, str) else "",
        tags=tags,
        frameworks=_extract_frameworks(tags),
        primary_detector=primary,
        extended_detectors=extended,
        active=active,
        doc_url=doc_url if isinstance(doc_url, str) else None,
        extra=extra,
    )


def _enumerate_module_by_module(category: str) -> list[tuple[str, bool]]:
    base_mod_name, base_cls_name = _BASE_CLASS[category]
    base_mod = importlib.import_module(base_mod_name)
    base_cls = getattr(base_mod, base_cls_name)
    pkg = importlib.import_module(f"garak.{category}")
    pkg_dir = pkg.__path__  # type: ignore[attr-defined]

    result: list[tuple[str, bool]] = []
    for mod_info in pkgutil.iter_modules(pkg_dir):
        if mod_info.name.startswith("_") or mod_info.name == "base":
            continue
        try:
            mod = importlib.import_module(f"garak.{category}.{mod_info.name}")
        except Exception:
            continue
        for cls_name, obj in inspect.getmembers(mod, inspect.isclass):
            if (
                issubclass(obj, base_cls)
                and obj is not base_cls
                and obj.__module__ == mod.__name__
            ):
                active = bool(getattr(obj, "active", True))
                result.append((f"{category}.{mod_info.name}.{cls_name}", active))
    return result


@functools.lru_cache(maxsize=None)
def _enumerate_raw(category: str) -> list[tuple[str, bool]]:
    with _utf8_open():
        try:
            plugins_mod = importlib.import_module("garak._plugins")
            enumerate_plugins = getattr(plugins_mod, "enumerate_plugins")
            raw = enumerate_plugins(category=category)
            result: list[tuple[str, bool]] = []
            for entry in raw:
                if isinstance(entry, (tuple, list)) and len(entry) >= 2:
                    result.append((str(entry[0]), bool(entry[1])))
                else:
                    result.append((str(entry), True))
            if result:
                return result
        except Exception:
            pass
        return _enumerate_module_by_module(category)


@functools.lru_cache(maxsize=None)
def list_category(category: str, include_meta: bool = True) -> list[dict]:
    if category not in PLUGIN_CATEGORIES:
        raise ValueError(f"Unknown plugin category: {category}")
    _import_garak()
    infos: list[dict] = []
    entries = _enumerate_raw(category)
    for fq_name, active in entries:
        if include_meta:
            try:
                with _utf8_open():
                    info = _plugin_info_from_class(fq_name, category, active)
            except Exception as exc:  # pragma: no cover - a broken plugin
                info = PluginInfo(
                    name=fq_name,
                    category=category,
                    module="",
                    class_name=fq_name.rpartition(".")[2],
                    description=f"(metadata unavailable: {exc})",
                    active=active,
                )
        else:
            info = PluginInfo(
                name=fq_name,
                category=category,
                module="",
                class_name=fq_name.rpartition(".")[2],
                active=active,
            )
        infos.append(asdict(info))
    infos.sort(key=lambda d: d["name"].lower())
    return infos


def summary() -> dict:
    _import_garak()
    return {
        "version": garak_version(),
        "counts": {cat: len(_enumerate_raw(cat)) for cat in PLUGIN_CATEGORIES},
    }


def clear_cache() -> None:
    _enumerate_raw.cache_clear()
    list_category.cache_clear()
