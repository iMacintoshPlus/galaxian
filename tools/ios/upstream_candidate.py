"""Prepare a release merge on its own branch; never merge into ios or publish."""
import json
import os
from pathlib import Path
import re
import subprocess


def run(*args):
    return subprocess.check_output(args, text=True).strip()


def output(key, value):
    with open(os.environ['GITHUB_OUTPUT'], 'a') as stream:
        stream.write(f'{key}={value}\n')

release = json.loads(run('gh', 'api', 'repos/TheWWWorm/galaxian/releases/latest'))
tag = release['tag_name']
if not re.fullmatch(r'v?[0-9][A-Za-z0-9._-]*', tag):
    raise SystemExit('Unexpected upstream tag; manual review required.')
branch = 'upstream-release/' + tag
repo = os.environ['GITHUB_REPOSITORY']
existing = run('git', 'ls-remote', '--heads', 'origin', branch)
if existing:
    print('Candidate already exists for', tag)
    manual = os.environ.get('GITHUB_EVENT_NAME') == 'workflow_dispatch'
    output('build', 'true' if manual else 'false')
    if manual:
        output('sha', existing.split()[0])
        output('tag', tag)
        output('branch', branch)
    raise SystemExit(0)
run('git', 'config', 'user.name', 'github-actions[bot]')
run('git', 'config', 'user.email', '41898282+github-actions[bot]@users.noreply.github.com')
run('git', 'fetch', 'https://github.com/TheWWWorm/galaxian.git', 'refs/tags/' + tag)
upstream_sha = run('git', 'rev-parse', 'FETCH_HEAD^{commit}')
run('git', 'switch', '-c', branch)
try:
    run('git', 'merge', '--no-edit', upstream_sha)
except subprocess.CalledProcessError:
    run('git', 'merge', '--abort')
    raise SystemExit('Upstream merge conflict. Resolve manually; ios was not modified.')
marker = Path('ios/upstream-release.json')
marker.write_text(json.dumps({'tag': tag, 'commit': upstream_sha}, indent=2) + '\n')
run('git', 'add', str(marker))
run('git', 'commit', '-m', 'Prepare iOS candidate for upstream ' + tag)
run('git', 'push', 'origin', 'HEAD:refs/heads/' + branch)
sha = run('git', 'rev-parse', 'HEAD')
output('build', 'true')
output('sha', sha)
output('tag', tag)
output('branch', branch)
body = ('Candidate for upstream ' + tag + '. The workflow builds an unsigned IPA and creates a draft release. '
        'Review the diff and test the IPA before manually merging this PR and publishing the draft. '
        'No original game archive or personal signing credentials are included.\n\n'
        'Workflow: https://github.com/' + repo + '/actions/runs/' + os.environ['GITHUB_RUN_ID'])
Path('/tmp/ios-pr-body.md').write_text(body)
try:
    run('gh', 'pr', 'create', '--repo', repo, '--base', 'ios', '--head', branch,
        '--title', 'iOS update for upstream ' + tag, '--body-file', '/tmp/ios-pr-body.md')
except subprocess.CalledProcessError:
    print('PR creation unavailable. Review the candidate branch via GitHub Compare; the build will continue.')
