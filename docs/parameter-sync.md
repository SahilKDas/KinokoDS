# Character and vehicle sync

## Scope and evidence

Sync currently means importing original parameter records into a typed C++ data
layer, preserving IDs and raw values. It does not mean driving physics matches.
The synthetic acceleration simulator remains separate and unchanged.

Source ROM: pinned AMCE revision 0, SHA-256 recorded in `docs/emulator.md`.
The extractor reads Nitro FNT/FAT, decompresses LZ10 and parses NARC in memory.
Only two small tables from `data/KartModelMainA.carc` are written under ignored
`local/parameters/`; no models, textures or full archive copies are retained.

Observed in this ROM:

| Table | Record count | Stride | Total bytes |
| --- | ---: | ---: | ---: |
| kartphysicalparam.bin | 50 | 0x98 | 7,600 |
| charphysicalparam.bin | 13 | 8 | 104 |

The JSON catalogs contain individual IDs, offsets, original record bytes, hashes,
and interpreted fields. Binary and JSON are local, not committed. Table hashes
and ROM identity accompany the import. All 50 kart records are retained: do not
equate record count with the selectable vehicle roster or drop special slots.

Layout research is pinned to HaroohiePals/MKDS-decomp-headers commit
`2d089194e146650406f6c257914ec397d35c8de7`:

- https://github.com/HaroohiePals/MKDS-decomp-headers/blob/2d089194e146650406f6c257914ec397d35c8de7/race/drivers/physicalParams.h
- https://github.com/HaroohiePals/MKDS-decomp-headers/blob/2d089194e146650406f6c257914ec397d35c8de7/race/raceConfig.h

Names and field semantics from RE are provisional for this ROM until traced at
runtime. In particular, the header represents offset 0x34 as a signed 32-bit
field; an older experimental mkjs reader splits this area differently. Preserve
all four bytes, and resolve the discrepancy against AMCE instructions before
using it. Unknown fields retain offset-based names. No float conversion, stat
normalization or guessed driver/kart combination formula is applied.

## Reproduce

```powershell
$env:PYTHONDONTWRITEBYTECODE = '1'
python -B tests/test_sync_parameters.py
python -B tools/sync_parameters.py
cmake --build --preset dev
ctest --preset dev
./build/kinoko_parameters.exe local/parameters/kartphysicalparam.bin local/parameters/charphysicalparam.bin
./tools/check-size.ps1
```

C++ readers check record alignment and count bounds, decode little-endian values
explicitly and retain signed widths. Tests cover record boundaries, signedness,
malformed tables, archive ranges and overlapping LZ copies using synthetic data.

## One-by-one validation queue

Every character below has its own extracted record and hash. Labels follow the
upstream enum; runtime index and effective kart/driver combination are pending.

| ID | Character | Import | Runtime validation |
| ---: | --- | --- | --- |
| 0 | Mario | Complete | Active ID/record corroborated; physics pending |
| 1 | Donkey Kong | Complete | Pending |
| 2 | Toad | Complete | Pending |
| 3 | Bowser | Complete | Pending |
| 4 | Peach | Complete | Pending |
| 5 | Wario | Complete | Pending |
| 6 | Yoshi | Complete | Pending |
| 7 | Luigi | Complete | Pending |
| 8 | Dry Bones | Complete | Pending |
| 9 | Daisy | Complete | Pending |
| 10 | Waluigi | Complete | Pending |
| 11 | R.O.B. | Complete | Pending |
| 12 | Shy Guy | Complete | Special mode availability also pending |

Vehicle queue is IDs 0 through 49, each independently catalogued in
`local/parameters/kartphysicalparam.bin.json`. Names, playable/special status and
runtime mapping are pending except ID 0: Mario/Standard MR is corroborated by the
active identity/pointer chain in the [first runtime check](mario-kart0-validation.md).
Do not assign other names from menu order without corroboration.

For each entry: establish runtime index -> compare loaded raw parameters ->
identify transformations for driver/engine class -> capture acceleration from a
fixed start -> compare every tick -> record evidence and remaining discrepancies.
Vary the kart with one driver fixed; then vary drivers with one verified kart
fixed. Eventually test combinations where runtime transformations interact.
No entry is marked physics-verified merely because its parameters import.

The [upstream audit](upstream-physics.md) cross-checks recovered parameter copy
logic against AMCE instructions. The C++ selection layer now handles normal
race, character-indexed battle records 37..49, and award/staff-roll record 0.
This mapping is statically corroborated; live battle validation remains pending.

The [offline sync audit](sync-audit.md) now verifies every imported byte, all
1,950 selection cases, and all 650 surface-adjustment pairs against execution of
the captured ARM loop. This covers that parameter substage only.

The [offline longitudinal pipeline](offline-longitudinal.md) additionally checks
complete per-driver preparation and isolated ordinary acceleration/drag/cap
stages. Other characters are not thereby live-validated game trajectories.
