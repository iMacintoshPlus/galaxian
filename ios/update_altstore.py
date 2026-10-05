#!/usr/bin/env python3
"""Regenerate the Classic source from published GitHub release IPAs."""
import io
import json
import os
from pathlib import Path, PurePosixPath
import plistlib
import subprocess
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parent
BUNDLE = 'com.imacintoshplus.galaxian'


def ipa_metadata(data):
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        names = archive.namelist()
        plists = [n for n in names if len(PurePosixPath(n).parts) == 3
                  and n.startswith('Payload/') and n.endswith('.app/Info.plist')]
        if len(plists) != 1:
            raise ValueError('Expected exactly one application in the IPA')
        # This feed is for our unsigned, extension-free build. Fail for a new
        # signing/extension setup so its entitlements receive explicit review.
        if any('/_CodeSignature/' in n or '/PlugIns/' in n or
               n.endswith('embedded.mobileprovision') for n in names):
            raise ValueError('Review permissions for this signed or extended IPA')
        info = plistlib.loads(archive.read(plists[0]))
        if info['CFBundleIdentifier'] != BUNDLE:
            raise ValueError('Unexpected bundle identifier')
        return info


def generate(releases, download, repository):
    versions, privacy, seen = [], {}, set()
    published = sorted((r for r in releases if not r['draft'] and r['published_at']),
                       key=lambda r: r['published_at'], reverse=True)
    for release in published:
        assets = [a for a in release['assets']
                  if a['name'].startswith('Galaxian') and a['name'].endswith('.ipa')]
        if not assets:
            continue
        if len(assets) != 1:
            raise ValueError('Release must have exactly one Galaxian IPA')
        asset = assets[0]
        data = download(asset['browser_download_url'])
        if len(data) != asset['size']:
            raise ValueError('Downloaded IPA size differs from release metadata')
        info = ipa_metadata(data)
        identity = (info['CFBundleShortVersionString'], info['CFBundleVersion'])
        if identity in seen:
            continue
        seen.add(identity)
        versions.append({
            'version': identity[0], 'buildVersion': identity[1],
            'date': release['published_at'],
            'localizedDescription': release.get('body') or release['tag_name'],
            'downloadURL': asset['browser_download_url'], 'size': len(data),
            'minOSVersion': info['MinimumOSVersion'],
        })
        for key, value in info.items():
            if 'UsageDescription' in key:
                privacy.setdefault(key, value)
    if not versions:
        raise ValueError('No published Galaxian IPA; existing source left untouched')
    icon = f'https://raw.githubusercontent.com/{repository}/master/ios/altstore-icon.png'
    return {
        'name': 'Galaxian', 'identifier': 'com.imacintoshplus.galaxian.source',
        'subtitle': 'Galaxian for iOS', 'iconURL': icon,
        'website': f'https://github.com/{repository}',
        'apps': [{
            'name': 'Galaxian', 'bundleIdentifier': BUNDLE,
            'developerName': 'TheWWWorm; iOS port by iMacintoshPlus',
            'localizedDescription': 'Native iOS port of Galaxian. Import your own original Galaxy on Fire IPA on first launch. Original game content is not included.',
            'iconURL': icon, 'category': 'games', 'versions': versions,
            'appPermissions': {'entitlements': [], 'privacy': privacy},
        }], 'news': [],
    }


def main():
    repository = os.environ.get('GITHUB_REPOSITORY', 'iMacintoshPlus/galaxian')
    pages = json.loads(subprocess.check_output([
        'gh', 'api', '--paginate', '--slurp', f'repos/{repository}/releases?per_page=100']))
    def download(url):
        with urllib.request.urlopen(url, timeout=120) as response:
            return response.read()
    source = generate([r for page in pages for r in page], download, repository)
    (ROOT/'altstore.json').write_text(json.dumps(source, indent=2) + '\n')
    print(f"Source contains {len(source['apps'][0]['versions'])} published version(s)")


if __name__ == '__main__':
    main()
