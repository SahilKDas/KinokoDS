# Parameter synchronization audit

Offline audit performed 2026-10-25. No desktop interaction, emulator connection,
game input or new capture was used. All generated evidence stays in `local/`.

## Checks passed

- Re-read the pinned ROM, verify its SHA-256, and extract both parameter tables
  in memory. Compare against the existing imported binaries without overwriting
  them first, so stale or corrupted imports cannot be hidden by a fresh sync.
- Validate every JSON catalog record: ID, offset, full raw bytes, record hash,
  decoded fields, count, and full-table hash.
- Decode and re-encode all 50 kart and 13 character records in C++; compare every
  byte with the originals, including signed fields and unknown fields.
- Check 1,950 scene/character/kart input combinations: 3 selection scenes x 13
  character IDs x 50 kart IDs. This is raw parameter mapping, not menu availability.
- Execute the actual captured ARM surface loop offline for all 650 distinct
  character/kart pairs. Compare the entire 152-byte C++ result and selected
  8-byte character record for every case.
- Compare the predicted Mario/kart 0 result to the actual active record in the
  saved runtime capture. All bytes match.

The loop executor is deliberately restricted to the inspected instructions at
0x02072774..0x020727BF, with exact instruction SHA-256:
`a22e38f958dc46500f8846cea3220b8859984321da99ecaf367902f9abc2a6d0`.
It models 32-bit registers, signed multiply, carry, shifts, threshold branches
and record writes. It does not use the C++ multiplier formula as its oracle.
Tests cover signed half-way rounding, the >=4096 skip condition, wide products,
carry/truncation, unchanged record bytes and rejection of different code.

## Reproduce

Uses the installed Python/capstone and existing local ROM/capture. No downloads.

```powershell
$env:TEMP = "$PWD/build/tmp"
$env:TMP = $env:TEMP
$env:PYTHONDONTWRITEBYTECODE = '1'
cmake --build --preset dev
ctest --preset dev
python -B tests/test_arm_surface.py
python -B tools/audit_sync.py
./tools/check-size.ps1
```

The final audit command fails on the first discrepancy and writes the summary
to `local/parameters/sync-audit.json` only after all checks pass. C++ audit output
is captured in memory instead of retaining thousands of generated records.

## Limits

This validates lossless import, selection and the implemented surface adjustment
against game instructions. It does not validate complete mode-dependent
initialization, acceleration, handling, collision, tick sequencing or a full
race. Mario/kart 0 remains the only live active-record observation. The 650-pair
checks execute the captured code offline; they are not 650 live game sessions.

The synthetic acceleration simulator is still isolated from these parameter
readers. Its passing fixture is not evidence of MKDS driving fidelity.
