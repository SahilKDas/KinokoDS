# KinokoDS architecture

Status: parameter preparation, ordinary scalar driving and movement stages have
offline instruction comparisons. The original driver/contact dispatcher can be
replayed from captured RAM. Full C++ physics and live timing are unfinished.
Target: deterministic, headless C++26 simulation suitable for RL. See
[offline recovery and coverage](offline-physics.md).

## Fidelity contract

One `step` advances one game simulation tick. The actual cadence and reference
sampling boundary must be established experimentally; do not assume a rounded
60 Hz timestep. Simulation behavior must not depend on wall time or rendering.
Preserve integer arithmetic, intermediate widths, shifts, rounding, overflow,
angle formats and lookup tables where confirmed by evidence. Do not substitute
generic rigid-body dynamics for recovered game rules.

Pin a single game region/revision and ROM digest before collecting reference
data. The current reference is pinned AMCE (USA/Australia), revision 0; the ROM
digest is checked by the extraction and offline execution tools.
Evidence priority: observed game execution and inspected instructions; validated
RE; community documentation; hypotheses. Record provenance and confidence for
every recovered rule and parameter. Reimplementation code is not an oracle.

## Module boundaries

| Module | Purpose | Status |
| --- | --- | --- |
| math | Explicit fixed-point, vector and angle semantics | Integer scalar/vector arithmetic and normalization stages; full angle library pending |
| assets | KCL/NKM and vehicle parameter readers; immutable WorldData | Vehicle records/preparation implemented; C++ KCL/NKM pending |
| sim | Kart state transitions and contact response | Recovered scalar/movement stages; C++ contact/whole driver update pending; separate synthetic scaffold |
| race | Checkpoints, laps, start, respawn, dynamic course objects | Planned |
| replay | Versioned traces, comparison, later full snapshots and hashes | Minimal trace comparator |
| bindings | Python and batched stepping outside the tick loop | Planned |
| env | Gymnasium observations, actions, rewards, termination | Planned |
| tools | Extraction, emulator capture, diagnostics, optional viewer | Bounded original-code dispatcher replay and C++ comparisons; no desktop required |

Current layout: public interfaces in `include/kinoko/`, implementations in
`src/`, executables in `tools/`, tests and small synthetic fixtures in `tests/`.
Add planned modules when they acquire code; avoid empty abstraction layers.
No runtime dependencies or network fetching during builds.

WorldData will be immutable and shared across independent WorldState instances.
WorldState must eventually contain every future-affecting value: input history,
movement/contact/drift state, timers, race/object state, and RNG state. A full
snapshot must restore an identical continuation. Trace v1 is NOT a snapshot.
Keep serialization versioned and independent of C++ struct memory layout.

The recovered update order is part of the implementation, not an interchangeable
pipeline. Until it is known, keep candidate stages explicit and traceable.
Initial functions may use ordinary structs; defer ECS, SIMD and worker pools
until correctness and profiling justify them.

## Recovery checklist

- Arithmetic formats, division/square root/trig behavior, tick and input timing.
- Vehicle/driver parameter schemas and how values combine at runtime.
- Acceleration, speed cap, coast, brake, reverse, steering and lateral velocity.
- Hop, drift eligibility/direction, charge transitions and mini-turbo release.
- Boost duration/precedence, start boost, surface interaction.
- Gravity, airborne orientation, slopes, ramps, landing and retained momentum.
- Kart contact geometry, KCL prism tests, contact ordering and correction.
- Surface attributes: road, offroad, slippery, panels, jump pads, special roads.
- Checkpoint validity, lap progression, out-of-bounds and respawn behavior.
- Dynamic platforms/hazards, kart interactions, items and RNG (later scope).

KCL retains fixed-point vertices/normals, prism geometry, attributes and spatial
indexing. NKM contains course setup and logic. Preserve raw data alongside
decoded interpretations where useful. Parameter candidates include
`kartphysicalparam.bin`, `charphysicalparam.bin`, and `kartcrsmat.bin`; runtime
usage and field semantics still require verification.

## Milestones

1. Harness: strict trace parsing, exact comparison, synthetic replay, restoration.
2. Reference acquisition: pinned revision, emulator adapter, reproducible start
   state, tick-boundary alignment and recovered fields/numeric behavior.
3. Acceleration: one kart/driver on flat road; match speed and position each tick
   through acceleration and speed saturation using the same inputs/initial state.
4. Coast/brake/reverse, then steering/hop/drift and surface transitions.
5. Collision, slopes, airborne transitions; complete lap and respawn validation.
6. Python environment and batching; dynamic world and broader course coverage.

A match only covers captured fields and scenarios. Diagnose the first differing
field/tick before tuning constants. Timing-state divergence can precede position
divergence. Do not claim full physics fidelity from a completed lap.

## RL boundary

Begin with digital game controls. Action repeat runs ordinary simulation ticks;
it does not enlarge dt. Rewards consume race events without modifying physics.
Use explicit seeds and independent state per environment. Expose state-based
observations first; optional visualization must remain a separate consumer.

## References

Consulted 2026-10-24; pin commit IDs when relying on specific implementation code.

- https://github.com/HaroohiePals/MKDS-decomp-headers — structures and declarations.
- https://github.com/XorTroll/mkds-re — EU reverse engineering and symbols.
- https://github.com/RHY3756547/mkjs — experimental reimplementation, not a fidelity oracle.
- https://github.com/HaroohiePals/MarioKartToolbox — course tooling/format research.
- https://wiki.dshack.org/Wiki.jsp?page=KCL — collision representation.
- https://wiki.dshack.org/wiki/The%20Ultimate%20NKM%20Guide%202 — course data.
- https://wiki.dshack.org/wiki/Navigating%20the%20File%20System%20of%20MKDS — asset locations.

Review licenses before incorporating third-party code. Keep ROMs/extracted assets
out of version control, and respect the workspace storage budget.
