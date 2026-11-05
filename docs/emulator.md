# Local melonDS setup

The workspace limit is strictly below 200,000,000 bytes, including ignored data,
builds and `.git`. Audit with `./tools/check-size.ps1`; this is not a disk quota.

## Files

- Executable: `local/melonDS/melonDS.exe` (official 1.1 Windows x64).
- ROM: `local/roms/Mario Kart DS.nds` (33,554,432 bytes).
- Settings: `local/melonDS/portable/melonDS.toml`.
- Battery saves: `local/melonDS/portable/saves/`.
- Slot save states: `local/melonDS/portable/states/`.
- Cheats: `local/melonDS/portable/cheats/` (disabled).
- Wi-Fi settings: melonDS local data directory, `local/melonDS/portable/`.
- Temporary files when launched via script: `local/melonDS/portable/tmp/`.
- Reference identity: `local/reference-manifest.json`.

The ROM header identifies AMCE, revision 0 (USA/Australia), not the EU candidate
discussed in the architecture proposal. Use this identity for subsequent address
mapping and traces. SHA-256 of the extracted ROM:

```text
0ea8a91a0ae3e9db26337c25a6a8568f6737fa36c1e0761988c0fa0ecbf210ed
```

Only the `.nds` entry was extracted. The original Downloads archive is unchanged;
no duplicate ZIP is kept in the workspace. All `local/` data is ignored by Git.

## Configuration and launch

```powershell
./tools/start-melonds.ps1
# Or start without loading the ROM:
./tools/start-melonds.ps1 -WithoutROM
```

The script sets the child process working directory and TEMP/TMP inside the repo
and restores the invoking shell's environment afterward. The portable directory
selects repo-local emulator configuration independently of working directory.
Explicit absolute save paths prevent dependence on launch location. If the repo
moves, update those paths in the local TOML before launching.

DS mode and direct boot are selected, using built-in BIOS/firmware replacements.
DSi SD and DLDI images are disabled to avoid unexpected large disk images.
Bindings: A=X, B=Z, X=S, Y=A, L=Q, R=W, Start=Enter, Select=Shift,
directions=arrow keys, pause=P, frame step=N.

Use configured slot save states and save directories; manual Save As dialogs can
choose arbitrary paths, so keep selections inside the repo. Do not enable large
SD images or accumulate states without checking available headroom.

Runtime check on 2026-10-24: AMCE booted to the Mario Kart DS main menu.
After correcting the initial settings to use the emulator-written TOML format,
the rewritten config retained all three explicit repo-local paths. A 262,144-byte
battery save was created in `portable/saves/`; Wi-Fi settings and RTC files were
created in `portable/`. No melonDS directory appeared in the standard Roaming or
Local AppData locations checked before/after. This is a targeted path check, not
a system-wide write audit. Slot-state paths are configured but not yet exercised.
The initial launch also generated a save beside the ROM (still within the repo);
it is retained rather than overwriting the newer configured-directory save.
This setup is not yet a validated deterministic reference profile.

The launcher now rejects duplicate repo instances to prevent hidden audio from
an accidentally running second emulator. It opens a visible window by default;
`-Hidden` is optional. For agent shell sessions use `-Wait` to keep the launch
session alive. Emulator instances used for verification were closed afterward.

## Upstream behavior checked

melonDS 1.1 checks for `portable` beside its executable before other config paths:
https://github.com/melonDS-emu/melonDS/blob/1.1/src/frontend/qt_sdl/main.cpp

The config is TOML, with per-instance save/state/cheat paths:
https://github.com/melonDS-emu/melonDS/blob/1.1/src/frontend/qt_sdl/Config.cpp

Save path resolution and generated firmware/Wi-Fi data handling:
https://github.com/melonDS-emu/melonDS/blob/1.1/src/frontend/qt_sdl/EmuInstance.cpp
