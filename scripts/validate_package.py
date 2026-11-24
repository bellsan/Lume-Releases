"""Validate a Lume distribution before a GitHub release is made public."""
import hashlib
import json
import re
import stat
import zipfile
from pathlib import Path, PurePosixPath

repo = "bellsan/Lume-Releases"
manifest = json.loads(Path("publish.json").read_text(encoding="utf-8"))
version = manifest["version"]
digest = manifest["sha256"]
if not isinstance(version, str) or not re.fullmatch(r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)", version):
    raise ValueError("Invalid version")
if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
    raise ValueError("Invalid SHA-256")
archive = Path("packages") / f"LumePro-{version}.zip"
if not 0 < archive.stat().st_size <= 64 * 1024 * 1024:
    raise ValueError("Invalid archive size")
if hashlib.sha256(archive.read_bytes()).hexdigest() != digest:
    raise ValueError("SHA-256 mismatch")
with zipfile.ZipFile(archive) as z:
    infos = z.infolist()
    if len(infos) > 2000 or sum(i.file_size for i in infos) > 128 * 1024 * 1024:
        raise ValueError("Archive exceeds limits")
    names = {}
    for i in infos:
        p = PurePosixPath(i.filename)
        if p.is_absolute() or ".." in p.parts or "\\" in i.filename or ":" in i.filename or stat.S_ISLNK(i.external_attr >> 16):
            raise ValueError("Unsafe archive path")
        if i.is_dir():
            continue
        parts = p.parts[1:] if p.parts and p.parts[0] == "LumePro" else p.parts
        name = "/".join(parts)
        if name.casefold() in names:
            raise ValueError("Duplicate archive path")
        if any(x.startswith(".") or x.casefold() in {"__pycache__", "credentials", "secrets", "update_state.json", "user_data"} for x in parts):
            raise ValueError("Unexpected private file in distribution")
        names[name.casefold()] = i.filename
    required = ["app/version.json", "app/server.py", "app/index.html", "app/app.js", "app/style.css", "app/updater.py", "start_windows.bat", "launch_windows.ps1"]
    if any(x not in names for x in required):
        raise ValueError("Incomplete distribution")
    meta = json.loads(z.read(names["app/version.json"]))
    if meta.get("version") != version or meta.get("repository", "").lower() != repo.lower() or meta.get("private") is True:
        raise ValueError("Update channel/version mismatch")
    if z.testzip() is not None:
        raise ValueError("Corrupted archive")
    notes = z.read(names["release_notes_ja.md"]).decode("utf-8") if "release_notes_ja.md" in names else f"Lume Pro v{version}"
Path(f"/tmp/{archive.name}.sha256").write_text(f"{digest}  {archive.name}\n", encoding="utf-8")
Path("/tmp/lume-release-notes.md").write_text(notes, encoding="utf-8")
print(f"Verified {archive.name}, SHA-256 {digest}")
