"""Read legacy IPA branding locally; never copy its bundle identifier or game data."""
import json
import plistlib
import re
from pathlib import Path, PurePosixPath
import subprocess
import tempfile
import zipfile


def apply_branding(ipa, xcode):
    with zipfile.ZipFile(ipa) as archive:
        candidates = [n for n in archive.namelist() if n.startswith('Payload/')
                      and n.count('/') == 2 and n.endswith('.app/Info.plist')]
        if len(candidates) != 1:
            raise ValueError('Expected one main app in the branding IPA.')
        metadata = plistlib.loads(archive.read(candidates[0]))
        name = metadata.get('CFBundleDisplayName') or metadata.get('CFBundleName')
        icon = metadata.get('CFBundleIconFile')
        if not isinstance(name, str) or not name or not isinstance(icon, str):
            raise ValueError('IPA must declare a display name and legacy CFBundleIconFile.')
        if PurePosixPath(icon).name != icon:
            raise ValueError('Expected a simple icon filename.')
        if not icon.lower().endswith('.png'):
            icon += '.png'
        entry = candidates[0].rsplit('/', 1)[0] + '/' + icon
        if archive.getinfo(entry).file_size > 16 * 1024 * 1024:
            raise ValueError('IPA icon is unexpectedly large.')
        icon_data = archive.read(entry)
    apply_icon_and_name(name, icon_data, xcode)


def apply_icon_and_name(name, icon_data, xcode):
    iconset = xcode/'Galaxian/Images.xcassets/AppIcon.appiconset'
    contents = json.loads((iconset/'Contents.json').read_text())
    with tempfile.TemporaryDirectory() as directory:
        source = Path(directory)/'original.png'
        source.write_bytes(icon_data)
        for item in contents['images']:
            pixels = round(float(item['size'].split('x')[0]) * float(item.get('scale', '1x')[:-1]))
            subprocess.run(['sips', '-s', 'format', 'png', '-z', str(pixels), str(pixels),
                            str(source), '--out', str(iconset/item['filename'])],
                           check=True, stdout=subprocess.DEVNULL)
    info = xcode/'Galaxian/Galaxian-Info.plist'
    settings = plistlib.loads(info.read_bytes())
    settings['CFBundleDisplayName'] = name
    settings['CFBundleName'] = name
    info.write_bytes(plistlib.dumps(settings, sort_keys=False))
    project = xcode/'Galaxian.xcodeproj/project.pbxproj'
    project.write_text(re.sub(r'INFOPLIST_KEY_CFBundleDisplayName = [^;]*;',
                             lambda _: 'INFOPLIST_KEY_CFBundleDisplayName = ' + json.dumps(name) + ';',
                             project.read_text()))
    # Localized InfoPlist.strings can override the display name.
    for localized in (xcode/'Galaxian').glob('*.lproj/InfoPlist.strings'):
        localized.write_text('"CFBundleDisplayName" = ' + json.dumps(name, ensure_ascii=False) + ';\n')
    print('Applied original IPA Home Screen name and icon:', name)
