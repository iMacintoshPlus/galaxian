#!/usr/bin/env python3
"""Build device and simulator debug/release picker libraries against matching Godot headers."""
import argparse
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--godot-source', type=Path, required=True)
p.add_argument('--scons', default='scons')
a = p.parse_args()
source = a.godot_source.resolve()
env = dict(os.environ)
env.setdefault('DEVELOPER_DIR', '/Applications/Xcode.app/Contents/Developer')
def run(command, **kwargs):
    subprocess.run([str(x) for x in command], env=env, check=True, **kwargs)
revision = subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip()
if revision != 'ed1daf0bf001b61586d9930840f2f1394092c079':
    raise SystemExit('Use Godot 4.7.2-stable sources matching the official export templates.')
run([a.scons, 'platform=ios', 'target=template_release', 'arch=arm64',
     'core/disabled_classes.gen.h', 'core/version_generated.gen.h',
     'core/extension/gdextension_interface.gen.h'], cwd=source)
build = ROOT / 'ios/build/plugin'
build.mkdir(parents=True, exist_ok=True)
out = ROOT / 'ios/build/plugin'
for target in ('debug', 'release'):
    libraries = []
    for sdk_name, triple in [('iphoneos', 'arm64-apple-ios14.0'),
                             ('iphonesimulator', 'arm64-apple-ios14.0-simulator')]:
        sdk = subprocess.check_output(['xcrun', '--sdk', sdk_name, '--show-sdk-path'], env=env, text=True).strip()
        obj = build / f'galaxian_files.{target}.{sdk_name}.o'
        lib = build / f'GalaxianFiles.{target}.{sdk_name}.a'
        run(['xcrun', '--sdk', sdk_name, 'clang++', '-c', ROOT/'ios/native/galaxian_files.mm',
             '-o', obj, '-I'+str(source), '-I'+str(source/'platform/ios'), '-std=c++17',
             '-target', triple, '-isysroot', sdk, '-fobjc-arc', '-fblocks',
             '-DIOS_ENABLED', '-DAPPLE_EMBEDDED_ENABLED', '-DUNIX_ENABLED',
             '-DTHREADS_ENABLED', '-DNDEBUG', '-O2',
             *(['-DDEBUG_ENABLED'] if target == 'debug' else []),
             *(['-DIOS_SIMULATOR'] if sdk_name == 'iphonesimulator' else [])])
        run(['xcrun', 'libtool', '-static', '-o', lib, obj])
        libraries.extend(['-library', lib])
    framework = out/f'GalaxianFiles.{target}.xcframework'
    if framework.exists():
        import shutil
        shutil.rmtree(framework)
    run(['xcodebuild', '-create-xcframework', *libraries, '-output', framework])
print('Built iOS device and Apple Silicon simulator picker frameworks.')
