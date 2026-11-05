# Offline initialization and longitudinal reconstruction

Implemented 2026-10-25 from the pinned AMCE revision 0 ROM, existing RAM snapshot,
installed capstone and C++ compiler. No computer use, live emulator control,
new capture or toolchain download was used.

## Interfaces and supported path

`prepare_parameters` selects original records, makes fresh copies, applies the
per-driver speed/drift and character surface adjustments, and returns the
derived driver field at 0x3F4. Original tables remain unchanged. Supply original
tables, never previously prepared records.

`update_longitudinal` is an isolated scalar update for grounded, forward,
straight driving without drift, brake, wheelspin, boosts, slopes, contacts,
rotation or other special effects. It accepts prepared parameters, scalar
speed/coasting state, throttle, an explicit upstream speed fraction and an
explicit resolved speed cap. It returns speed/coasting state. Unsupported
conditions throw instead of falling back to approximations.

The synthetic `WorldState`/`step` remains separate. This API does not calculate
the upstream fraction/cap, integrate position, identify tick cadence or simulate
the complete game-frame update.

## Code recovery and instruction evidence

`rom_code.py` verifies the ROM digest, backward-LZ expands ARM9 to 0x1773B8 bytes,
and follows the SDK autoload table: source 0x0216F320 maps 0x7FA0 bytes into ITCM
at 0x01FF8000; the next 0xE0 bytes map into DTCM at 0x027E0000. Main initialization
bytes match the saved main-RAM capture. ITCM is recovered from the ROM, not a
live ITCM capture. No decompressed full image is retained on disk.

`inspect_longitudinal.py` records sixteen bounded disassemblies, code-region and
segment hashes, decoder version and ROM provenance under ignored local data.

| Address | Role |
| --- | --- |
| 0x0208AEA8 | Select/copy 152-byte kart and 8-byte character records |
| 0x02062EB0 | Read presentation predicate from global state +0x38 |
| 0x020726BC | Per-driver speed, drift, surface and derived-field initialization |
| 0x01FFC5A0 | Map A/B input and clear per-update flags |
| 0x01FFBA68 | Acceleration stages, addition, release flag; excluded effect paths |
| 0x01FFB9E0 | Coasting drag and excluded force-stop modifier |
| 0x01FFAF18 | Speed cap, near-zero stop and excluded modifiers |
| 0x01FFBD9C | Upstream speed-fraction update, identified but not ported |
| 0x02147F34 | SDK FX_Div wrapper |
| 0x02147D88 / 0x02147E28 | Signed division hardware setup / rounded Q12 result |

Caller 0x01FFC6C0 maps input and calls acceleration at 0x01FFC7E4 when collision
mode +0x180 is zero. Caller 0x01FFB130 calls drag at 0x01FFB368 and the limiter
at 0x01FFB5A4. Other intervening code handles direction, contacts and other state;
the scalar pipeline does not claim to reproduce the entire caller.

Main-RAM speed stores were distinguished from acceleration: 0x02065428 loads
packed network state; 0x02067C5C clears speed on a transition; 0x0206E4E0 and
0x0206E55C modify interacting drivers; 0x0207073C and 0x02070E90 assign special
fixed speeds. Ordinary acceleration resides in relocated ITCM instead.

## Exact arithmetic and initialization

The presentation predicate forces source records 0/0 and skips engine adjustment.
Otherwise raw race-config +0x10 chooses:

| Raw value | Speed factor | Drift halfword delta |
| ---: | ---: | ---: |
| 0 | 0xB33 | -40 |
| 1 | 0xD9A | -20 |
| all others | 4096 | 0 |

Speed extracts product bits 12..43 WITHOUT rounding. Drift wraps to 16 bits.
Before character surface adjustment, driver field 0x3F4 is computed as
`FX_Div(4096 - surface_speed[4], collision_radius * 2)` with wrapping arithmetic.
The confirmed rounded character surface loop then runs. Battle copies record
37+character; presentation copies 0/0. The API receives explicit scene/raw class
inputs, not guesses based on menu labels.

Mario/kart 0 classes 0/1/2 produce speed 21502/26115/30720 and drift 180/200/220.
Class 2's prepared records and derived field 179 exactly match the captured
active snapshot.

## Ordinary scalar update rule

Let A=kart+0x14, B=kart+0x18, T=kart+0x1C, f=driver+0x2A0. The acceleration is:

1. f < 2048: A.
2. Otherwise f > T: B.
3. Otherwise: `A - trunc_mul(FX_Div(A-B, T-2048), f-2048)`.

Branch order matters: several real karts have T=1843 and jump directly to B at
f=2048. T=2048 reaches the hardware zero-divisor behavior, modeled explicitly.
For Mario, f=2867 yields 99; f=2868 yields 98 because of fixed-point quantization.

The input mapper clears the prior coast flag. Holding A adds acceleration with
32-bit wrapping. Release sets driver+0x44 bit 0x400; the drag routine applies
`trunc_mul(speed, kart+0x2C)`.

For ordinary limiter fields (0x274=0, 0x38C=4096, 0x394=4096, 0x39C=0, 0x3A0=0),
speed magnitude is capped to driver+0xD0. With neither A nor B held, magnitude
<=410 becomes zero. Sign handling is preserved even in overflow test vectors.

FX_Div executes signed hardware division `(a * 2^32)/b` with truncation toward
zero, adds 0x80000, then extracts bits 20..51. Signed multiply with and without
rounding, word wrapping and halfword wrapping are separate operations. No
floating-point constants are used.

## Differential validation and reproduction

`arm_offline.py` executes original instructions with bounded steps, condition
flags, registers, stack, memory, long multiply, carry and division MMIO. The
only high-level code hook is the identified byte-copy helper, restricted to
152/8-byte parameter copies. No acceleration/initialization equations are hooked.
Unsupported instructions fail closed.

The validator compares complete prepared records, selected source indices and
the derived field. Scalar checks compare speed and input/coast flags and reject
unexplained writes elsewhere in the synthetic driver record. Divergences record
the case, first differing field, instruction tail and driver-write trace.

The current matrix has 2,031 initialization and 4,822 longitudinal cases. The
latter include 2,550 repeated scalar updates (accelerate/release/reapply), stage
thresholds, stop/cap boundaries, input history, arithmetic overflow and other
parameter pairs. Invalid reverse input, out-of-range fractions and nonpositive
caps are rejected. Unit tests also reject airborne/drift/effect conditions.

Repeated fixtures supply an idealized external fraction schedule derived from
the previous scalar result. They do NOT establish that scalar speed equals the
game's measured movement magnitude, or that these are complete physics frames.

```powershell
$env:TEMP = "$PWD/build/tmp"
$env:TMP = $env:TEMP
$env:PYTHONDONTWRITEBYTECODE = '1'
cmake --build --preset dev
ctest --preset dev
python -B -m unittest discover -s tests -p 'test_*.py'
python -B tools/audit_sync.py
python -B tools/inspect_longitudinal.py
python -B tools/validate_longitudinal.py
./tools/check-size.ps1
```

Generated evidence and `offline-validation.json` stay in
`local/validation/mario-standard-mr-figure8-01/`. Large vector files are not
retained. Keep the whole folder below 200,000,000 bytes, including builds.

All four initial offline tasks are implemented for the declared forward scalar
path. Subsequent [offline physics recovery](offline-physics.md) adds cap/fraction
production, movement stages, B/reverse scalar rules and original driver/contact
dispatcher replay. Complete C++ driver/contact behavior, hardware timing and
live acceleration agreement remain pending. The only live evidence remains the
stationary Mario/Standard MR snapshot.
