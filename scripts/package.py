"""Package deployable sources without secrets, runtime data or QA artifacts."""
from pathlib import Path
import tarfile

root = Path(__file__).resolve().parent.parent
output = root / "outputs" / "license-registry-source.tar.gz"
output.parent.mkdir(exist_ok=True)
excluded = {".git", ".venv", ".env", ".local-access.txt", "__pycache__", "staticfiles", "backups", "test-results", "outputs"}
with tarfile.open(output, "w:gz") as archive:
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if path.is_file() and not set(relative.parts) & excluded and path.suffix not in {".pyc", ".pyo", ".sqlite3"}:
            archive.add(path, arcname=Path("license-registry") / relative, recursive=False)
print(output)
