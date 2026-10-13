"""Discover VTube Studio / Cubism expressions in a Live2D model package."""

from __future__ import annotations

import json
from pathlib import Path


def discover_live2d_expressions(model_file: Path) -> list[dict[str, str]]:
    """Return expression files with useful display names, including unreferenced exp3 files."""
    model_file = Path(model_file).resolve()
    try:
        settings = json.loads(model_file.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return []

    root = model_file.parent
    display_names: dict[str, str] = {}
    references: list[dict[str, str]] = []
    refs = settings.get("FileReferences") or {}
    for expression in refs.get("Expressions") or []:
        if isinstance(expression, dict) and isinstance(expression.get("File"), str):
            references.append({"Name": str(expression.get("Name") or ""), "File": expression["File"]})

    # VTube Studio stores its actions in a companion .vtube.json. Use those
    # labels when present; many exports leave Name blank, so CDI names are the
    # next source of friendly labels.
    for config in sorted(root.glob("*.vtube.json")):
        try:
            data = json.loads(config.read_text(encoding="utf-8-sig"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            continue
        for hotkey in data.get("Hotkeys") or []:
            filename = hotkey.get("File") if isinstance(hotkey, dict) else None
            name = hotkey.get("Name") if isinstance(hotkey, dict) else None
            if filename and name and hotkey.get("Action") in {"ToggleExpression", "SetExpression", "Set/UnsetExpression"}:
                display_names[Path(filename).name.casefold()] = str(name).strip()

    display_file = refs.get("DisplayInfo")
    if isinstance(display_file, str):
        cdi_file = (root / display_file).resolve()
        try:
            cdi_file.relative_to(root.resolve())
            cdi = json.loads(cdi_file.read_text(encoding="utf-8-sig"))
        except (ValueError, OSError, UnicodeError, json.JSONDecodeError):
            cdi = {}
        parameter_names = {
            str(parameter.get("Id")): str(parameter.get("Name")).strip()
            for parameter in cdi.get("Parameters", [])
            if parameter.get("Id") and parameter.get("Name")
        }
    else:
        parameter_names = {}

    files: dict[str, dict[str, str]] = {}
    for expression in references:
        candidate = (root / expression["File"]).resolve()
        try:
            candidate.relative_to(root.resolve())
        except ValueError:
            continue
        if candidate.is_file() and candidate.suffix.casefold() == ".json":
            files[candidate] = {"Name": expression["Name"], "File": candidate.relative_to(root).as_posix()}

    # Some VTube Studio exports keep their expressions in an expressions/
    # subfolder but omit FileReferences.Expressions entirely from model3.json.
    for candidate in sorted(root.rglob("*.exp3.json")):
        try:
            candidate.resolve().relative_to(root.resolve())
        except ValueError:
            continue
        files.setdefault(candidate, {"Name": "", "File": candidate.relative_to(root).as_posix()})

    results = []
    used_names = set()
    for candidate, reference in files.items():
        try:
            data = json.loads(candidate.read_text(encoding="utf-8-sig"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            continue
        if data.get("Type") != "Live2D Expression" or not isinstance(data.get("Parameters"), list):
            continue
        name = reference["Name"].strip() or display_names.get(candidate.name.casefold(), "")
        if not name:
            labels = list(dict.fromkeys(parameter_names.get(str(parameter.get("Id")), "") for parameter in data["Parameters"]))
            labels = [label for label in labels if label]
            name = " / ".join(labels) if labels else candidate.name.removesuffix(".exp3.json")
        # A display label can be reused by several VTube Studio hotkeys.
        # Keep every file selectable rather than overwriting it in a JS Map.
        label = name
        if label in used_names:
            label = f"{name} ({candidate.name.removesuffix('.exp3.json')})"
        suffix = 2
        while label in used_names:
            label = f"{name} ({candidate.name.removesuffix('.exp3.json')} {suffix})"
            suffix += 1
        used_names.add(label)
        results.append({"Name": label, "File": reference["File"]})
    return results
