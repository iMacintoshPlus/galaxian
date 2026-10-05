"""Download verified, pinned Godot tools."""
import hashlib
from pathlib import Path
import subprocess
import urllib.request
import zipfile

root = Path('ios/build/ci-tools').resolve()
root.mkdir(parents=True, exist_ok=True)
assets = [
    ('https://github.com/godotengine/godot/releases/download/4.7.2-stable/Godot_v4.7.2-stable_macos.universal.zip', 'c58a24e31d720be9d62f60cb5627c4e695fb72f21b0cfe1bc9ccaa9a3b3ba63e', 'editor.zip'),
    ('https://github.com/godotengine/godot/releases/download/4.7.2-stable/Godot_v4.7.2-stable_export_templates.tpz', 'f298490b8d44d934be425a5a65a51bf15f422428b229a06a6e11d9ffea248011', 'templates.tpz'),
]
for url, digest, name in assets:
    path = root/name
    if not path.exists():
        urllib.request.urlretrieve(url, path)
    with path.open('rb') as stream:
        actual = hashlib.file_digest(stream, 'sha256').hexdigest()
    if actual != digest:
        raise SystemExit('Checksum mismatch: ' + name)
subprocess.run(['ditto', '-x', '-k', str(root/'editor.zip'), str(root)], check=True)
with zipfile.ZipFile(root/'templates.tpz') as archive:
    (root/'ios.zip').write_bytes(archive.read('templates/ios.zip'))
if not (root/'godot-source').exists():
    subprocess.run(['git', 'clone', '--depth', '1', '--branch', '4.7.2-stable',
                    'https://github.com/godotengine/godot.git', str(root/'godot-source')], check=True)
