# iOS downstream build

This branch adds a native Files picker and an iOS export preset to upstream
Galaxian. Gameplay, the original IPA parser, and persistent saves are unchanged.
The only runtime integration in an existing script is `main.gd::choose_file()`.

## Pinned tools

- Official Godot **4.7.2** (`ed1daf0bf001b61586d9930840f2f1394092c079`).
- Matching standard export templates; extract `templates/ios.zip` from the TPZ.
- macOS with Xcode and iOS platform support. Initial development uses Xcode 26.3.
- Python 3 and SCons (`python3 -m venv .venv`, then `.venv/bin/pip install scons`).
- Godot sources checked out at `4.7.2-stable`, outside this repository.

The build scripts set `DEVELOPER_DIR` to `/Applications/Xcode.app/Contents/Developer`
if it is not already set. They do not change the system's xcode-select setting.
The deployment target is iOS 14.0 (older-device runtime validation is pending). Both device ARM64 and Apple Silicon
simulator ARM64 plugin libraries are built. Intel simulator binaries are not included.

From the repository root:

```sh
python3 tools/ios/build_plugin.py --godot-source /path/to/godot-4.7.2 --scons /path/to/.venv/bin/scons
python3 tools/ios/build_ipa.py --template /path/to/ios.zip --output /path/to/Galaxian-iOS-unsigned.ipa
```

For an Apple Silicon simulator run, the inspected official 4.7.2 template needs
a replacement simulator engine library: its release simulator archive contains
only x86_64, despite its XCFramework metadata listing ARM64 as well. The downloaded
TPZ was verified against the official release SHA-256. Build the matching pinned
Godot source with SCons (in the Godot source directory):

```sh
scons platform=ios target=template_release arch=arm64 simulator=yes vulkan=no metal=no opengl3=yes -j4
```

Then export from this repository:

```sh
python3 tools/ios/build_ipa.py --template /path/to/ios.zip --simulator-library /path/to/godot-4.7.2/bin/libgodot.ios.template_release.arm64.simulator.a --export-only
```

Open `ios/build/export/xcode/Galaxian.xcodeproj`, select an iPhone simulator,
and Run. The override changes only the generated simulator library and its
architecture metadata. The export script also adds Metal, QuartzCore, and IOSurface
to the generated project's linker flags because the template links MoltenVK.
The export is a release Godot engine/plugin even if Xcode's Run action uses its
Debug configuration. Plugin ABI must match the exported engine, not Xcode's label.

The scripts work in a disposable `ios/build` directory and never rewrite the
source project's settings during export. The staged iOS project uses Sensor
Landscape (orientation value 4), allowing rotation between both landscape
directions while keeping portrait disabled. Generated libraries/frameworks and build
products are ignored by Git. The preset's `0000000000` team ID is an unsigned-export
placeholder, not a signing identity. For a physical device, sign the resulting IPA
with your sideloading tool; alternatively configure your actual team in the generated
Xcode project. Re-exporting replaces that generated project, including manual
signing settings; save those locally before re-exporting and restore them afterward.
Keep the installed bundle identifier stable to preserve app data.

## Import behavior

`GalaxianFiles` uses Apple's document picker with `asCopy:YES`. The selected file
is moved to a unique temporary directory, passed to the original GDScript importer,
and removed after success, failure, or import cancellation. Picker cancellation
returns to the menu. Selection is limited to regular files of at most 128 MiB;
the upstream importer remains responsible for validating the archive itself.
Files providers may need to download remote files before delivering the selection.
The file never leaves the device. Original game content must never be committed.

Imported content and saves remain in Godot's `user://` storage. The iOS preset
exposes Documents in Files so saves can be backed up. The source IPA is not retained
after import; keep your own backup for future upstream cache schema changes.

This first patch does not integrate native document import/export for save bundles.
Those menu actions retain upstream's embedded file browser. Sensor calibration,
safe areas, phone performance, audio interruptions, and suspend/resume must be
checked on a physical device before calling the port ready.

## Upstream updates

Keep fork `master` aligned with upstream and maintain the iOS changes on `ios`.
Merge upstream into a temporary update branch, review conflicts, rebuild, then
smoke-test launch/import/save/reopen before updating `ios`. Do not blindly publish
an upstream merge. If upstream changes Godot versions, update the editor, source
headers, templates, and version checks together and rebuild the plugin.

Automated update PRs/builds should be enabled after the first device-tested build.
No scheduled publishing or automatic merging is configured by this patch.

## Validation status

On 2026-10-04, Xcode 26.3 successfully built and launched the ARM64 simulator
export on an iPhone 17 Pro simulator running iOS 26.3. The user selected the
original IPA through the native picker, and the game reported successful import.
`Documents/install.cfg` references the extracted content cache; the plugin's
temporary import directory was removed. The simulator reports Apple's software
OpenGL renderer and starts slowly, so it is not a phone performance benchmark.
The export script removes empty camera, microphone, and photo-library usage
descriptions inherited from the template, while preserving any future nonempty
descriptions. A device build was also installed through Xcode on an iPhone 14 Pro
running iOS 18.7.8; the user reported that it works well. This is a manual smoke
test, not exhaustive validation of sensors, lifecycle handling, or iOS 14.
Standalone unsigned IPA packaging has not yet been validated end to end.

## Optional personal IPA branding

Pass `--branding-ipa /path/to/original.ipa` to `build_ipa.py` to extract the
legacy IPA's `CFBundleDisplayName` and `CFBundleIconFile` into the generated
iOS project. The bundle identifier stays unchanged. No original artwork is
stored in tracked files. Supply this option on each export to retain the branding.
The original 57-pixel icon is resized for modern icon slots. Without this option,
builds keep the Galaxian display name and project icon.
