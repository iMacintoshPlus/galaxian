#!/usr/bin/env python3
"""Export and build an unsigned device IPA in an isolated staging directory."""
import argparse
import os
import plistlib
import re
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[2]
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--godot', type=Path, default=Path('/Applications/Godot.app/Contents/MacOS/Godot'))
p.add_argument('--template', type=Path, required=True, help='ios.zip from the official 4.7.2 export templates')
p.add_argument('--output', type=Path, default=Path('Galaxian-iOS-unsigned.ipa'))
p.add_argument('--simulator-library', type=Path, help='Optional matching ARM64 simulator libgodot.a built from source')
p.add_argument('--branding-directory', type=Path, help='Directory containing branding.json and icon.png, without any game archive')
p.add_argument('--branding-ipa', type=Path, help='Local original IPA supplying only the Home Screen name and icon')
p.add_argument('--export-only', action='store_true', help='Prepare Xcode project for interactive simulator testing')
a = p.parse_args()
env = dict(os.environ)
env.setdefault('DEVELOPER_DIR', '/Applications/Xcode.app/Contents/Developer')
def run(command, **kwargs):
    subprocess.run([str(x) for x in command], env=env, check=True, **kwargs)
version = subprocess.check_output([str(a.godot), '--version'], text=True).strip()
if version != '4.7.2.stable.official.ed1daf0bf':
    raise SystemExit('Use the official Godot 4.7.2 editor and matching templates.')
for target in ('debug', 'release'):
    if not (ROOT/f'game/ios/plugins/galaxian_files/GalaxianFiles.{target}.xcframework').is_dir():
        raise SystemExit('Build the native plugin first with build_plugin.py.')
# Never rewrite the developer checkout, its presets or its resource imports.
build = ROOT/'ios/build/export'
if build.exists(): shutil.rmtree(build)
stage = build/'game'
shutil.copytree(ROOT/'game', stage, ignore=shutil.ignore_patterns('.godot', '.DS_Store'))
# Allow both landscape directions only in the disposable iOS project.
project = stage/'project.godot'
settings = re.sub(r'^window/handheld/orientation=.*\n?', '', project.read_text(), flags=re.MULTILINE)
if '[display]' not in settings:
    settings += '\n[display]\n'
settings = settings.replace('[display]', '[display]\nwindow/handheld/orientation=4', 1)
project.write_text(settings)
presets = stage/'export_presets.cfg'
text = presets.read_text()
path = str(a.template.resolve()).replace('\\', '\\\\').replace('"', '\\"')
text = text.replace('[preset.6.options]', '[preset.6.options]\ncustom_template/debug="'+path+'"\ncustom_template/release="'+path+'"')
presets.write_text(text)
xcode = build/'xcode'
xcode.mkdir()
run([a.godot, '--headless', '--path', stage, '--editor', '--import'])
run([a.godot, '--headless', '--path', stage, '--export-release', 'iOS', xcode/'Galaxian.ipa'])
# The template emits empty permission descriptions for features this game does
# not use. Keep any future explicit descriptions, but omit unused empty keys.
app_info = xcode/'Galaxian/Galaxian-Info.plist'
app_settings = plistlib.loads(app_info.read_bytes())
app_settings['CFBundleDisplayName'] = 'Galaxian'
app_settings['CFBundleName'] = 'Galaxian'
for key in ('NSCameraUsageDescription', 'NSMicrophoneUsageDescription', 'NSPhotoLibraryUsageDescription'):
    if app_settings.get(key) == '':
        del app_settings[key]
app_info.write_bytes(plistlib.dumps(app_settings, sort_keys=False))
for localized in (xcode/'Galaxian').glob('*.lproj/InfoPlist.strings'):
    localized.write_text('"CFBundleDisplayName" = "Galaxian";\n')
# Godot's exported project always links MoltenVK, which needs these frameworks
# even for the Compatibility renderer. Keep this fix in generated build files.
pbx = xcode/'Galaxian.xcodeproj/project.pbxproj'
pbx.write_text(pbx.read_text().replace(' -ObjC";', ' -ObjC -framework Metal -framework QuartzCore -framework IOSurface";'))
if a.simulator_library:
    library = a.simulator_library.resolve()
    archs = subprocess.check_output(['xcrun', 'lipo', '-archs', str(library)], env=env, text=True).split()
    if archs != ['arm64']:
        raise SystemExit('The simulator override must contain only ARM64 code.')
    framework = xcode/'Galaxian.xcframework'
    info = plistlib.loads((framework/'Info.plist').read_bytes())
    for entry in info['AvailableLibraries']:
        if entry.get('SupportedPlatformVariant') == 'simulator':
            shutil.copyfile(library, framework/entry['LibraryIdentifier']/entry['LibraryPath'])
            entry['SupportedArchitectures'] = ['arm64']
    (framework/'Info.plist').write_bytes(plistlib.dumps(info))
if a.branding_directory:
    import json
    from ipa_branding import apply_icon_and_name
    branding = json.loads((a.branding_directory/'branding.json').read_text())
    apply_icon_and_name(branding['name'], (a.branding_directory/'icon.png').read_bytes(), xcode)
if a.branding_ipa:
    from ipa_branding import apply_branding
    apply_branding(a.branding_ipa, xcode)
if a.export_only:
    print(f'Open {xcode / "Galaxian.xcodeproj"} in Xcode and select an iPhone simulator.')
    raise SystemExit(0)
run(['xcodebuild', '-project', xcode/'Galaxian.xcodeproj', '-scheme', 'Galaxian',
     '-configuration', 'Release', '-sdk', 'iphoneos', '-destination', 'generic/platform=iOS',
     '-derivedDataPath', build/'DerivedData', 'CODE_SIGNING_ALLOWED=NO',
     'CODE_SIGNING_REQUIRED=NO', 'CODE_SIGN_IDENTITY=', 'DEVELOPMENT_TEAM=', 'build'])
app = build/'DerivedData/Build/Products/Release-iphoneos/Galaxian.app'
if not app.is_dir(): raise SystemExit('Xcode did not produce Galaxian.app')
package = build/'package/Payload'
package.mkdir(parents=True)
shutil.copytree(app, package/app.name, symlinks=True)
output = a.output.resolve()
output.parent.mkdir(parents=True, exist_ok=True)
if output.exists(): output.unlink()
run(['ditto', '-c', '-k', '--keepParent', 'Payload', output], cwd=package.parent)
print(f'Unsigned IPA ready for a sideloading tool: {output}')
