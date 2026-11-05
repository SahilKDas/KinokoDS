# KinokoDS
KinokoDS is a headless C++26 Mario Kart DS physics engine and gym environment for reinforcement learning and neural network training.

Early reconstruction: parameter initialization and ordinary scalar acceleration
stages are implemented; complete driving physics and Gymnasium bindings are pending.
See [architecture](docs/architecture.md) and [comparison harness](docs/comparison.md).
The [parameter sync](docs/parameter-sync.md) imports the pinned ROM's 50 kart and
13 character records into a typed C++ data layer; behavior remains unverified.
An [offline audit](docs/sync-audit.md) checks lossless import and implemented
parameter adjustments against captured game instructions; driving physics is pending.
The [offline longitudinal pipeline](docs/offline-longitudinal.md) implements and
checks the recovered scalar stages against pinned ROM instructions.
The [offline physics recovery](docs/offline-physics.md) also implements movement
stages and replays the original driver/contact dispatcher from saved RAM without
an emulator. Complete C++ driving physics and hardware timing remain pending.

## Build and verify

Requires installed CMake >=3.25, Ninja and a GCC/Clang-style compiler accepting
`-std=c++26`. C++26 mode does not imply complete implementation of the standard.
Verified locally with GCC 14.1 and CMake 3.29. No dependencies are downloaded.

```powershell
New-Item -ItemType Directory -Force build/tmp | Out-Null
$env:TEMP = "$PWD/build/tmp"
$env:TMP = $env:TEMP
./tools/check-size.ps1
cmake --preset dev
cmake --build --preset dev
ctest --preset dev
./build/kinoko_accel.exe tests/fixtures/synthetic.csv build/actual.csv
./build/kinoko_compare.exe tests/fixtures/synthetic.csv build/actual.csv
./tools/check-size.ps1
```

The whole workspace, including `.git`, must stay **strictly below 200 MB**
(200,000,000 bytes). Keep all work and temporary output here; leave headroom
before builds/downloads. The size checker audits usage; it does not impose a quota.

## Local emulator

melonDS 1.1 Windows x64 is downloaded to `local/melonDS/melonDS.exe` (ignored
by Git). Source: https://github.com/melonDS-emu/melonDS/releases/tag/1.1.
The release ZIP SHA-256 was verified against GitHub's published asset digest:
`9f3f8a244103be20b5b657af5b0ed1b2a66bb20a7181476a6d294c9a53d4f8c8`.
The ZIP was removed after extraction. Local configuration and reference ROM data
are ignored by Git. Use `./tools/start-melonds.ps1` to launch with repo-local
temporary files and working directory. See [local setup](docs/emulator.md).
