"""Build a source-only delivery from an explicit reviewed file list."""
from pathlib import Path
import hashlib
import json
import sys
import zipfile

ROOT = Path(__file__).resolve().parent
FILES = (
    'README.md', 'START.md', 'LAUNCH.json', 'ROOMMATE-TEST.md', 'LICENSE', '.gitignore', 'requirements.txt',
    'cx.py', 'page.js', 'list.js', 'runtime.ps1', 'cx.ps1', 'setup.ps1', 'setup_deps.py', 'doctor.ps1', 'Open-Edge.cmd',
    'skills/homework-web/SKILL.md', 'docs/sources.md', 'docs/verification.md',
    'tests/test_plan.py', 'tests/test_page.py', 'tests/test_lists.py',
    'tests/test_portable.py', 'tests/test_package.py', 'pack.py',
)


def build_zip(target):
    target = Path(target).resolve()
    if target.suffix.lower() != '.zip':
        raise ValueError('Output must be a zip file')
    content = {}
    for name in FILES:
        source = ROOT / name
        if source.is_symlink() or not source.resolve().is_relative_to(ROOT):
            raise ValueError('Refusing a linked source file: ' + name)
        content[name] = source.read_bytes()
    target.parent.mkdir(parents=True, exist_ok=True)
    hashes = {name: hashlib.sha256(value).hexdigest() for name, value in content.items()}
    with zipfile.ZipFile(target, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for name, value in content.items():
            archive.writestr(name, value)
        archive.writestr('SHA256.json', json.dumps(hashes, indent=2))
    return {'files': len(content), 'bytes': target.stat().st_size,
            'sha256': hashlib.sha256(target.read_bytes()).hexdigest()}


if __name__ == '__main__':
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / 'dist' / 'homework-web-test.zip'
    print(json.dumps(build_zip(target)))
