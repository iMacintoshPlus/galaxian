#!/usr/bin/env python3
"""Notify the shared AltStore repository after a manually published release."""
import json
import os
from pathlib import Path
import subprocess

repository = os.environ['GITHUB_REPOSITORY']
if repository not in ('iMacintoshPlus/abyssal', 'iMacintoshPlus/galaxian'):
    raise SystemExit('Unexpected repository')
app = repository.split('/')[1]
name = {'abyssal': 'Abyssal', 'galaxian': 'Galaxian'}[app]
event = json.loads(Path(os.environ['GITHUB_EVENT_PATH']).read_text())
if os.environ['GITHUB_EVENT_NAME'] == 'release':
    tag = event['release']['tag_name']
else:
    tag = os.environ['RELEASE_TAG']
release = json.loads(subprocess.check_output(['gh', 'release', 'view', tag, '--repo', repository,
                                            '--json', 'isDraft,assets,tagName'], text=True))
if release['isDraft']:
    raise SystemExit('Draft releases cannot be sent to AltStore')
if not any(a['name'] == name + '-iOS-unsigned.ipa' for a in release['assets']):
    raise SystemExit('Published release has no unsigned iOS IPA')
root = Path(os.environ['GITHUB_WORKSPACE']) / 'altstore-source'
request = root / 'requests' / (app + '.json')
request.parent.mkdir(exist_ok=True)
request.write_text(json.dumps({'repository': repository, 'tag': release['tagName'],
                               'run': os.environ['GITHUB_RUN_ID'],
                               'attempt': os.environ['GITHUB_RUN_ATTEMPT']}, indent=2) + '\n')
for args in [('config', 'user.name', 'github-actions[bot]'),
             ('config', 'user.email', '41898282+github-actions[bot]@users.noreply.github.com'),
             ('add', str(request)), ('commit', '-m', f'Sync approved {name} release')]:
    subprocess.run(['git', '-C', str(root), *args], check=True)
for attempt in range(3):
    subprocess.run(['git', '-C', str(root), 'pull', '--rebase', 'origin', 'main'], check=True)
    if subprocess.run(['git', '-C', str(root), 'push', 'origin', 'HEAD:main']).returncode == 0:
        break
else:
    raise SystemExit('Could not notify AltStore source after three push attempts')
