# Acceleration comparison harness

## Current capability

`kinoko_accel INPUT OUTPUT` reads an input/reference trace, replays its accelerate
buttons from a zero synthetic state, and writes predicted values. Only profile
`synthetic-accel-v1` is supported. Its rule is speed += 3 up to 12 when accelerating,
then position += speed; releasing acceleration coasts unchanged. Units are made
up. This is plumbing verification, not MKDS behavior.

`kinoko_compare EXPECTED ACTUAL` compares profile, then each row in field order
(tick, accelerate, position, speed), then length. Exit codes: 0 match, 1 mismatch,
2 invalid file/usage/I/O. It reports the first differing field, expected value,
and actual value. Comparisons are exact with no float tolerance.

Example from the repository root (PowerShell):

```powershell
./build/kinoko_accel.exe tests/fixtures/synthetic.csv build/actual.csv
./build/kinoko_compare.exe tests/fixtures/synthetic.csv build/actual.csv
```

## Trace v1

```text
kinoko-trace-v1
profile=synthetic-accel-v1
tick,accelerate,position_raw,speed_raw
1,1,3,3
2,1,9,6
```

UTF-8/ASCII without BOM; LF or CRLF; no blank/comment rows or quoted fields.
Ticks are contiguous from 1. Each row records the input applied during that tick
and state AFTER it completes. Accelerate is 0/1. Position is signed 64-bit and
speed signed 32-bit. No unit conversion or normalization is performed.
Empty traces, extra/missing columns, malformed and out-of-range values fail.
The profile must define units, initial state and configuration. The current
synthetic profile implies position/speed/tick=0 and previous_accelerate=false.

## Reference acquisition gate

No emulator capture adapter or retail trace is supplied yet. Before adding one:

1. Pin ROM region/revision/digest, emulator build/settings and exporter version.
2. Identify the physics tick boundary and input application point. Establish
   addresses/widths for speed and position using inspected code and experiments.
3. Define a new profile: kart/driver, engine class, course and exact flat-road
   start state, heading, surface/contact conditions, RNG/timers and input history.
4. Save an initial reference snapshot and a manifest documenting field addresses,
   numeric formats, provenance, and confidence. Keep local game data ignored.
5. Capture repeated identical runs to establish reference determinism. Include
   startup and speed saturation; retain raw values and button history.
6. Implement the recovered arithmetic/update rule and initial-state loading.
   Upgrade the trace schema when additional fields are needed. Never relabel
   synthetic output as a retail profile.
7. Replay and compare every tick. Expand capture to hidden state as it is mapped.

Acceptance: identical input/configuration and exact captured speed/position at
every sampled tick through speed saturation, with evidence for field semantics.
The fixture is hand-authored synthetic data and cannot satisfy this acceptance.
