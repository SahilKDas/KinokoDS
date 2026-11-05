# Mario / kart 0: first runtime parameter check

Date: 2026-10-25. Game: pinned AMCE revision 0; melonDS 1.1 Windows x64.
Mode: Time Trials, Figure-8 Circuit. Menu selection: Mario / Standard MR.
No engine-class menu was offered in this mode; do not infer a runtime CC value
from this check. No acceleration was intentionally applied. Captured speed is 0.

## Result

The selected driver has character ID 0 and kart ID 0 in the referenced charkart
object. Its active character record is byte-identical to character table record
0. Its active kart record matches kart table record 0 except six values in the
surface speed multiplier array. This corroborates identity and parameter loading;
it does not validate the simulator's acceleration or the full driver structure.

Evidence is ignored under `local/validation/mario-standard-mr-figure8-01/`:

- `arm9-main-ram.bin`: 4 MB main-RAM snapshot.
- `report.json`: capture digest and raw byte-match locations.
- `active-parameters.json`: pointer chain, active IDs, decoded differences.

Re-run offline (no emulator required):

```powershell
$env:PYTHONDONTWRITEBYTECODE = '1'
python -B tools/validate_baseline.py mario-standard-mr-figure8-01
python -B tests/test_validate_baseline.py
```

## Pointer corroboration

Addresses apply to THIS capture, not fixed addresses to assume in later runs.

| Object | Address |
| --- | --- |
| Complete kart table, exact ROM bytes | 0x0238ADC8 |
| Complete character table, exact ROM bytes | 0x02386568 |
| Physics parameter context | 0x022CD1FC |
| Driver 0 | 0x02359E40 |
| Active kart parameter record | 0x022CD220 |
| Active character parameter record | 0x022CD2C8 |
| Character/kart identity object | 0x022CCC68 |

The physics context points to both full original tables and to both active
records. Driver offsets 0x2CC/0x2D0 point to the same active records; its ID at
0x74 is 0. (The first checker used 0x78; instruction inspection corrected this.)
The pointer at 0x590 leads to the identity object, whose first two
32-bit values are character=0 and kart=0. The analyzer requires this complete
chain and a unique driver candidate, rather than accepting standalone matches.
Mario and Luigi share character parameter bytes, so the character byte match
alone would not distinguish them.

Offsets/layouts are drawn from research headers at commit
`2d089194e146650406f6c257914ec397d35c8de7` and corroborated for this chain:

- https://github.com/HaroohiePals/MKDS-decomp-headers/blob/2d089194e146650406f6c257914ec397d35c8de7/race/drivers/driver.h
- https://github.com/HaroohiePals/MKDS-decomp-headers/blob/2d089194e146650406f6c257914ec397d35c8de7/race/drivers/charKart.h
- https://github.com/HaroohiePals/MKDS-decomp-headers/blob/2d089194e146650406f6c257914ec397d35c8de7/race/drivers/physicalParams.h

## Observed transformation

Only surface speed multiplier slots 1,2,3,4,6,7 differ:

| Slot | ROM raw | Active raw |
| ---: | ---: | ---: |
| 1 | 409 | 389 |
| 2 | 2867 | 2724 |
| 3 | 2048 | 1946 |
| 4 | 1228 | 1167 |
| 6 | 3686 | 3502 |
| 7 | 409 | 389 |

All six fit `(source * 3891 + 2048) >> 12`, where 3891 is the first raw field of
Mario's active character record. Slots 0,5,8,9,10,11 remain 4096.
Other decoded kart values, including max speed 30720 and base acceleration 237,
are unchanged in the active record. That does not establish how they are used.

## Remaining validation

1. Reproduce the pointer chain and transformation in a second independent run.
2. Mode-dependent preparation is now implemented in the
   [offline pipeline](offline-longitudinal.md); broader field meanings remain under study.
3. Pin a deterministic pre-race state/input schedule and tick boundary.
4. Capture position/speed every physics tick through acceleration and saturation.
5. Implement the recovered update rule and compare, then advance to further
   driver/kart combinations one by one.

The capture halts through GDB and is not aligned to a recovered physics tick.
The game timer had advanced while the kart remained stationary. No acceleration
trace or savestate was collected, and no claim of physics fidelity is made.

## Instruction inspection and C++ implementation

Continued offline on 2026-10-25 with computer use disabled. No emulator input or
live debugger connection was used. The saved RAM contains ARM code as well as
data. `tools/inspect_initialization.py` records bounded disassembly and code
region digests locally, tied to the capture's verified SHA-256.

The routine at 0x020726BC obtains the driver's kart record and stores its pointer
at driver+0x2CC. At 0x02072760 it obtains the character record and stores its pointer
at +0x2D0. Both accessors take the driver ID from +0x74. The loop at
0x02072780..0x020727BC processes twelve signed 32-bit entries at kart+0x68:

1. Compare the entry with 4096; skip it when greater than or equal (signed).
2. Load character+0, multiply signed 32x32 to 64 bits.
3. Add 2048 with carry into the upper product word.
4. Extract product bits 12 through 43 and store the resulting 32-bit value.

Thus the six changed slots were selected by a threshold, not a hardcoded list.
The C++ `apply_character_surface_factor` implements precisely this operation on
a fresh copy. Its tests cover the threshold, signed rounding/ties, input
preservation, unchanged fields and 32-bit wraparound. Applying it to Mario and
kart 0 matches every decoded field of the captured 152-byte active kart record.
It remains separate from the synthetic driving simulator.

Earlier code also changes max speed and drift according to mode-dependent
branches, subsequently implemented in `prepare_parameters`; see the
[offline pipeline](offline-longitudinal.md). The surface helper alone remains
only one initialization stage.

```powershell
$env:PYTHONDONTWRITEBYTECODE = '1'
python -B tools/inspect_initialization.py
python -B tools/validate_baseline.py mario-standard-mr-figure8-01
cmake --build --preset dev
ctest --preset dev
./build/kinoko_verify_surface.exe local/parameters/kartphysicalparam.bin local/parameters/charphysicalparam.bin local/validation/mario-standard-mr-figure8-01/active-kart.bin
```

The first command needs the existing capstone installation; runtime simulation
and ordinary C++ tests have no disassembler dependency. This is instruction
corroboration plus one observed combination, not validation of every character
or an acceleration trace.
