from __future__ import annotations

import copy
import difflib
import hashlib
import os
import re
import stat
import tempfile
import threading
from pathlib import Path
from typing import Any


MAX_TEXT_BYTES = 1_000_000
MAX_DIFF_CHARS = 2_000_000
_HUNK_RE = re.compile(
    r"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(?: .*)?$"
)
_LOCKS: dict[str, threading.Lock] = {}
_LOCKS_GUARD = threading.Lock()


def _resolved(path: Path) -> Path:
    try:
        return Path(path).expanduser().resolve(strict=False)
    except (TypeError, ValueError, OSError) as exc:
        raise ValueError(f"Invalid workspace path: {path!r}") from exc


def _lock_for(path: Path) -> threading.Lock:
    key = os.path.normcase(str(path))
    with _LOCKS_GUARD:
        return _LOCKS.setdefault(key, threading.Lock())


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _validate_text(value: Any, label: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{label} must be a string")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise ValueError(f"{label} is not valid UTF-8 text") from exc
    return value


def _encode_result(text: str) -> bytes:
    _validate_text(text, "Result")
    data = text.encode("utf-8")
    if len(data) > MAX_TEXT_BYTES:
        raise ValueError(
            f"Result exceeds the {MAX_TEXT_BYTES:,}-byte UTF-8 limit"
        )
    return data


def _read_utf8(path: Path) -> tuple[str, bytes]:
    try:
        with path.open("rb") as handle:
            data = handle.read(MAX_TEXT_BYTES + 1)
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"Workspace file not found: {path}") from exc
    except IsADirectoryError as exc:
        raise ValueError(f"Workspace path is not a regular file: {path}") from exc
    if len(data) > MAX_TEXT_BYTES:
        raise ValueError(
            f"Source exceeds the {MAX_TEXT_BYTES:,}-byte UTF-8 limit: {path}"
        )
    try:
        return data.decode("utf-8"), data
    except UnicodeDecodeError as exc:
        raise ValueError(f"Workspace file is not valid UTF-8: {path}") from exc


def _assert_absent(path: Path) -> None:
    if os.path.lexists(path):
        raise ValueError(f"Refusing to create an existing path: {path}")


def _newline_style(text: str) -> str:
    crlf = text.count("\r\n")
    lf = text.count("\n") - crlf
    cr = text.count("\r") - crlf
    styles = sum((crlf > 0, lf > 0, cr > 0))
    if styles > 1:
        raise ValueError("Source has mixed newline conventions")
    if crlf:
        return "\r\n"
    if cr:
        return "\r"
    return "\n"


def _to_lf(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _from_lf(text: str, newline: str) -> str:
    return text if newline == "\n" else text.replace("\n", newline)


def _split_lf_lines(text: str) -> list[str]:
    if not text:
        return []
    parts = text.split("\n")
    lines = [part + "\n" for part in parts[:-1]]
    if parts[-1]:
        lines.append(parts[-1])
    return lines


def _make_diff(before: str, after: str, path: Path, create: bool) -> str:
    fromfile = "/dev/null" if create else f"a/{path.name}"
    tofile = f"b/{path.name}"
    generated = difflib.unified_diff(
        _split_lf_lines(before),
        _split_lf_lines(after),
        fromfile=fromfile,
        tofile=tofile,
        lineterm="\n",
    )
    output: list[str] = []
    for index, line in enumerate(generated):
        control = index < 2 or line.startswith("@@ ")
        if control or line.endswith("\n"):
            output.append(line if line.endswith("\n") else line + "\n")
        else:
            output.append(line + "\n")
            output.append("\\ No newline at end of file\n")
    diff = "".join(output)
    if len(diff) > MAX_DIFF_CHARS:
        raise ValueError(f"Diff exceeds the {MAX_DIFF_CHARS:,}-character limit")
    _validate_text(diff, "Diff")
    return diff


def _prepared(
    path: Path,
    operation: str,
    arguments: dict[str, Any],
    before: str,
    result: str,
    base_sha256: str | None,
    source_bytes: int,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    result_bytes = _encode_result(result)
    diff = _make_diff(before, _to_lf(result), path, operation == "create")
    preview = {
        "operation": operation,
        "path": str(path),
        "diff": diff,
        "base_bytes": source_bytes,
        "result_bytes": len(result_bytes),
    }
    if metadata:
        preview.update(metadata)
    return {
        "content": result,
        "preview": preview,
        "bindings": {
            "base_sha256": base_sha256,
            "result_sha256": _sha256(result_bytes),
            "diff_sha256": _sha256(diff.encode("utf-8")),
            "path": str(path),
        },
        "operation": operation,
        "arguments": copy.deepcopy(arguments),
    }


def _create_result(arguments: Any) -> str:
    if not isinstance(arguments, dict) or set(arguments) != {"content"}:
        raise ValueError("Create arguments must contain only content")
    content = _validate_text(arguments["content"], "Create content")
    return _to_lf(content)


def _edit_result(before: str, newline: str, arguments: Any) -> tuple[str, int]:
    if not isinstance(arguments, dict) or set(arguments) != {"replacements"}:
        raise ValueError("Edit arguments must contain only replacements")
    replacements = arguments["replacements"]
    if not isinstance(replacements, list):
        raise ValueError("Replacements must be a list")

    matches: list[tuple[int, int, str]] = []
    for index, replacement in enumerate(replacements):
        if not isinstance(replacement, dict) or set(replacement) != {
            "old",
            "new",
            "count",
        }:
            raise ValueError(
                f"Replacement {index} must contain only old, new, and count"
            )
        old = _to_lf(_validate_text(replacement["old"], f"Replacement {index} old"))
        new = _to_lf(_validate_text(replacement["new"], f"Replacement {index} new"))
        count = replacement["count"]
        if not old:
            raise ValueError(f"Replacement {index} old text must not be empty")
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise ValueError(f"Replacement {index} count must be a nonnegative integer")

        positions: list[int] = []
        start = 0
        while True:
            found = before.find(old, start)
            if found < 0:
                break
            positions.append(found)
            start = found + 1
        if len(positions) != count:
            raise ValueError(
                f"Replacement {index} expected {count} occurrences, found {len(positions)}"
            )
        for found in positions:
            matches.append((found, found + len(old), new))

    matches.sort(key=lambda match: (match[0], match[1]))
    previous_end = -1
    for start, end, _ in matches:
        if start < previous_end:
            raise ValueError("Replacements overlap or have ambiguous application")
        previous_end = end

    pieces: list[str] = []
    cursor = 0
    for start, end, new in matches:
        pieces.append(before[cursor:start])
        pieces.append(new)
        cursor = end
    pieces.append(before[cursor:])
    result = "".join(pieces)
    if result == before:
        raise ValueError("Edit is a no-op")
    return _from_lf(result, newline), len(replacements)


def _patch_label(line: str, prefix: str) -> str:
    if not line.startswith(prefix):
        raise ValueError("Malformed unified diff file header")
    label = line[len(prefix) :].split("\t", 1)[0]
    if not label or label == "/dev/null":
        raise ValueError("Patch must describe one existing file")
    if label.startswith(("a/", "b/")):
        label = label[2:]
    if not label:
        raise ValueError("Patch contains an empty file label")
    return label


def _parse_patch(patch_text: Any) -> list[dict[str, Any]]:
    patch_text = _validate_text(patch_text, "Patch")
    if len(patch_text) > MAX_DIFF_CHARS:
        raise ValueError(f"Patch exceeds the {MAX_DIFF_CHARS:,}-character limit")
    text = _to_lf(patch_text)
    if not text:
        raise ValueError("Patch is empty")
    lines = text.split("\n")
    if lines[-1] == "":
        lines.pop()
    if len(lines) < 3:
        raise ValueError("Patch must contain file headers and at least one hunk")

    old_label = _patch_label(lines[0], "--- ")
    new_label = _patch_label(lines[1], "+++ ")
    if old_label != new_label:
        raise ValueError("Patch must describe a single file without renaming")

    hunks: list[dict[str, Any]] = []
    index = 2
    while index < len(lines):
        match = _HUNK_RE.fullmatch(lines[index])
        if not match:
            raise ValueError(f"Malformed or trailing patch data at line {index + 1}")
        old_start = int(match.group(1))
        old_count = int(match.group(2)) if match.group(2) is not None else 1
        new_start = int(match.group(3))
        new_count = int(match.group(4)) if match.group(4) is not None else 1
        if (old_count > 0 and old_start == 0) or (new_count > 0 and new_start == 0):
            raise ValueError("Patch hunk starts are invalid for their line counts")
        index += 1
        old_lines: list[str] = []
        new_lines: list[str] = []
        old_seen = 0
        new_seen = 0
        no_newline_targets: list[tuple[list[str], int]] = []

        while (
            old_seen < old_count
            or new_seen < new_count
            or (index < len(lines) and lines[index] == "\\ No newline at end of file")
        ):
            if index >= len(lines):
                raise ValueError("Patch ends in a truncated hunk")
            line = lines[index]
            index += 1
            if line == "\\ No newline at end of file":
                if not no_newline_targets:
                    raise ValueError("Patch has a misplaced no-newline marker")
                for target, target_index in no_newline_targets:
                    if not target[target_index].endswith("\n"):
                        raise ValueError("Patch has a duplicate no-newline marker")
                    target[target_index] = target[target_index][:-1]
                no_newline_targets = []
                continue
            if not line or line[0] not in " +-":
                raise ValueError(f"Malformed patch hunk line at line {index}")
            kind, body = line[0], line[1:] + "\n"
            no_newline_targets = []
            if kind in " -":
                if old_seen >= old_count:
                    raise ValueError("Patch hunk exceeds its declared old line count")
                old_lines.append(body)
                old_seen += 1
            if kind in " +":
                if new_seen >= new_count:
                    raise ValueError("Patch hunk exceeds its declared new line count")
                new_lines.append(body)
                new_seen += 1
            if kind == " ":
                no_newline_targets = [
                    (old_lines, len(old_lines) - 1),
                    (new_lines, len(new_lines) - 1),
                ]
            elif kind == "-":
                no_newline_targets = [(old_lines, len(old_lines) - 1)]
            else:
                no_newline_targets = [(new_lines, len(new_lines) - 1)]

        if old_seen != old_count or new_seen != new_count:
            raise ValueError("Patch hunk does not match its declared line counts")
        hunks.append(
            {
                "old_start": old_start,
                "old_count": old_count,
                "new_start": new_start,
                "new_count": new_count,
                "old_lines": old_lines,
                "new_lines": new_lines,
            }
        )
    if not hunks:
        raise ValueError("Patch contains no hunks")
    return hunks


def _patch_result(before: str, newline: str, arguments: Any) -> tuple[str, int]:
    if not isinstance(arguments, dict) or set(arguments) != {"patch_text"}:
        raise ValueError("Patch arguments must contain only patch_text")
    hunks = _parse_patch(arguments["patch_text"])
    source_lines = _split_lf_lines(before)
    output: list[str] = []
    cursor = 0
    for number, hunk in enumerate(hunks, 1):
        old_index = (
            hunk["old_start"]
            if hunk["old_count"] == 0
            else hunk["old_start"] - 1
        )
        new_index = (
            hunk["new_start"]
            if hunk["new_count"] == 0
            else hunk["new_start"] - 1
        )
        if old_index < cursor or old_index > len(source_lines):
            raise ValueError(f"Patch hunk {number} overlaps or is out of range")
        if len(output) != new_index:
            raise ValueError(f"Patch hunk {number} has an inconsistent new position")
        old_lines = hunk["old_lines"]
        if source_lines[old_index : old_index + len(old_lines)] != old_lines:
            raise ValueError(f"Patch hunk {number} does not exactly match the source")
        output.extend(source_lines[cursor:old_index])
        output.extend(hunk["new_lines"])
        cursor = old_index + len(old_lines)
    output.extend(source_lines[cursor:])
    if any(not line.endswith("\n") for line in output[:-1]):
        raise ValueError("Patch places a no-newline marker before the end of the file")
    result = "".join(output)
    if result == before:
        raise ValueError("Patch is a no-op")
    return _from_lf(result, newline), len(hunks)


def prepare_create(path: Path, content: str) -> dict:
    path = _resolved(path)
    _assert_absent(path)
    arguments = {"content": content}
    result = _create_result(arguments)
    return _prepared(path, "create", arguments, "", result, None, 0)


def prepare_edit(path: Path, replacements: list[dict]) -> dict:
    path = _resolved(path)
    source, source_data = _read_utf8(path)
    newline = _newline_style(source)
    before = _to_lf(source)
    arguments = {"replacements": replacements}
    result, replacement_count = _edit_result(before, newline, arguments)
    return _prepared(
        path,
        "edit",
        arguments,
        before,
        result,
        _sha256(source_data),
        len(source_data),
        {"replacement_count": replacement_count},
    )


def prepare_patch(path: Path, patch_text: str) -> dict:
    path = _resolved(path)
    source, source_data = _read_utf8(path)
    newline = _newline_style(source)
    before = _to_lf(source)
    arguments = {"patch_text": patch_text}
    result, hunk_count = _patch_result(before, newline, arguments)
    return _prepared(
        path,
        "patch",
        arguments,
        before,
        result,
        _sha256(source_data),
        len(source_data),
        {"hunk_count": hunk_count},
    )


def _verify_prepared(
    prepared: Any,
    path: Path,
    operation: str,
    result: str,
    diff: str,
    base_sha256: str | None,
) -> bytes:
    if not isinstance(prepared, dict):
        raise ValueError("Prepared operation must be a dictionary")
    try:
        bindings = prepared["bindings"]
        preview = prepared["preview"]
        content = prepared["content"]
    except KeyError as exc:
        raise ValueError(f"Prepared operation is missing {exc.args[0]}") from exc
    if not isinstance(bindings, dict) or not isinstance(preview, dict):
        raise ValueError("Prepared bindings and preview must be dictionaries")
    if bindings.get("path") != str(path) or preview.get("path") != str(path):
        raise ValueError("Prepared operation is bound to a different path")
    if prepared.get("operation") != operation or preview.get("operation") != operation:
        raise ValueError("Prepared operation metadata was tampered with")
    if bindings.get("base_sha256") != base_sha256:
        raise ValueError("Prepared base hash is stale or was tampered with")

    result_data = _encode_result(result)
    expected_result_hash = _sha256(result_data)
    expected_diff_hash = _sha256(diff.encode("utf-8"))
    if bindings.get("result_sha256") != expected_result_hash:
        raise ValueError("Prepared arguments or result hash were tampered with")
    if bindings.get("diff_sha256") != expected_diff_hash:
        raise ValueError("Prepared patch or diff hash was tampered with")
    if content != result or _sha256(_encode_result(content)) != expected_result_hash:
        raise ValueError("Prepared final content was tampered with")
    if preview.get("diff") != diff or _sha256(
        _validate_text(preview.get("diff"), "Prepared diff").encode("utf-8")
    ) != expected_diff_hash:
        raise ValueError("Prepared preview diff was tampered with")
    return result_data


def _atomic_write(path: Path, data: bytes, create: bool, mode: int | None) -> None:
    parent = path.parent
    if not parent.is_dir():
        raise FileNotFoundError(f"Workspace parent directory not found: {parent}")
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=parent
    )
    temporary = Path(temporary_name)
    descriptor_open = True
    try:
        with os.fdopen(descriptor, "wb") as handle:
            descriptor_open = False
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        if mode is not None:
            os.chmod(temporary, mode)
        if create:
            try:
                # A hard link publishes the complete file and, unlike os.replace,
                # atomically fails rather than overwriting a late-arriving path.
                os.link(temporary, path)
            except FileExistsError as exc:
                raise ValueError(
                    f"Stale create: a file appeared at {path} before execution"
                ) from exc
            temporary.unlink()
        else:
            os.replace(temporary, path)
        temporary = None  # type: ignore[assignment]
    finally:
        if descriptor_open:
            os.close(descriptor)
        if temporary is not None:
            try:
                temporary.unlink()
            except FileNotFoundError:
                pass


def execute_prepared(path: Path, prepared: dict) -> dict:
    path = _resolved(path)
    with _lock_for(path):
        if not isinstance(prepared, dict):
            raise ValueError("Prepared operation must be a dictionary")
        operation = prepared.get("operation")
        if operation not in {"create", "edit", "patch"}:
            raise ValueError("Prepared operation has an unknown operation")
        arguments = prepared.get("arguments")
        create = operation == "create"
        mode: int | None = None
        if create:
            if os.path.lexists(path):
                raise ValueError(f"Stale create base: path now exists: {path}")
            before = ""
            source = ""
            base_sha256 = None
            result = _create_result(arguments)
            metadata = None
        else:
            source, source_data = _read_utf8(path)
            base_sha256 = _sha256(source_data)
            supplied_bindings = prepared.get("bindings")
            if (
                not isinstance(supplied_bindings, dict)
                or supplied_bindings.get("base_sha256") != base_sha256
            ):
                raise ValueError(
                    f"Stale or tampered base: current file differs from review: {path}"
                )
            newline = _newline_style(source)
            before = _to_lf(source)
            if operation == "edit":
                result, count = _edit_result(before, newline, arguments)
                metadata = {"replacement_count": count}
            else:
                result, count = _patch_result(before, newline, arguments)
                metadata = {"hunk_count": count}
            try:
                mode = stat.S_IMODE(path.stat().st_mode)
            except FileNotFoundError as exc:
                raise FileNotFoundError(
                    f"Workspace file disappeared before execution: {path}"
                ) from exc

        diff = _make_diff(before, _to_lf(result), path, create)
        if metadata:
            expected_preview_count = metadata.get(
                "replacement_count", metadata.get("hunk_count")
            )
            preview = prepared.get("preview")
            count_key = next(iter(metadata))
            if not isinstance(preview, dict) or preview.get(count_key) != expected_preview_count:
                raise ValueError("Prepared operation metadata was tampered with")
        result_data = _verify_prepared(
            prepared, path, operation, result, diff, base_sha256
        )
        _atomic_write(path, result_data, create, mode)
        from memory_archaeology import capture_saved
        context_save=capture_saved('document',str(path),'workspace-file-save')
        return {
            "path": str(path),
            "bytes": len(result_data),
            "sha256": _sha256(result_data),
            "diff": diff,
            **({'archaeology_save':context_save} if context_save else {}),
        }
