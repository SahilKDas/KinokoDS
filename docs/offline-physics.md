# Offline physics recovery

The pinned AMCE revision-0 ROM and saved Mario/Standard MR RAM now support a
bounded replay of the original driver dispatcher, including its course/contact
callbacks. This does not require melonDS or desktop access. C++ implements the
recovered scalar and movement stages; the whole dispatcher is not yet ported.
Hardware frame timing and live-game agreement remain unverified.

## Reproduce

After configuring the project as described in the README:

```powershell
./tools/validate-physics.ps1
```

The script uses installed tools, keeps temporary files in `build/tmp`, checks
the folder budget, runs existing audits, regenerates code/data hashes, compares
the C++ stages, replays eight input schedules, and repeats the straight schedule
to check byte-identical trace output. It fails on a differing field, unsupported
instruction, unexpected write, code/snapshot mismatch, or instruction budget.

The verified run completed all eight schedules: 1,120 dispatcher updates, with
1,120 matching C++ movement-tail comparisons and 1,060 scalar comparisons inside
their declared domain. Reverse speed occurred in 94 updates; each R-turn schedule
included 14 updates with `+0x44` bit 1 set and 13 with ground bit 4 clear. All
observed movement modes were 0; modes 1..6 are not covered by these traces.
The repeated straight report was byte-identical. Eight CTest cases and 26 Python
tests passed alongside the differential matrices.

Individual commands:

```powershell
python -B tools/inspect_frame.py
python -B tools/validate_movement.py
python -B tools/validate_grounded_drive.py
python -B tools/trace_physics_offline.py --dispatch --scenario straight
python -B tools/trace_physics_offline.py --dispatch --scenario drift-left
```

Generated evidence stays in ignored `local/validation/frame-inspection/`.
Inputs are bounded schedules of A, B, left/right and R. The replay writes the
input unit's triggered, pressed and released key fields from their history.
It does not patch speed, position, driver flags, kart parameters or contact
results. The initial state is the existing stationary snapshot, not a new live
capture. Every replay verifies its RAM digest and pinned ROM digest. Executed
main-RAM instruction bytes are also checked against the saved capture; ITCM
instructions come from the pinned ROM's autoload image, since no live ITCM
capture exists.

## Recovered update order

`0x0207AAEC` performs these passes over the driver array:

1. `0x01FFCAC0`: save/update history fields, including copying position to
   `+0x8C`, then invoke the callback at driver `+0x220`.
2. Run the shared pass at `0x0207A32C`.
3. Invoke each driver's `+0x218` callback.
4. Invoke each driver's `+0x21C` callback.

The captured Mario's `+0x218` callback is `0x020646C0`, which calls the driver
body at `0x01FFCC50`. Its `+0x21C` callback is `0x020641D4`, which calls
`0x01FFCB58` and `0x020641F0`. These post-update paths reach course geometry
and can change position after the movement addition. Traces retain both the
position immediately after movement and the position after the dispatcher.

The driver body calls `0x01FFCA50`, cap production `0x01FFBE70`,
`0x02067488`, cap transition `0x01FFBE04`, fraction/direction production
`0x01FFBD9C`, input/driving `0x01FFC6C0`, `0x01FF9D18`, then movement
`0x01FFB130` on the selected ordinary branch. Entry predicates and alternate
branches remain part of the original executor; this list is not a replacement
for those predicates.

`0x020651FC` is a different caller with an additional dependency at
`0x02066AC0`. It must not be substituted for the captured driver's selected
update callback. Its enclosing context remains unresolved.

## C++ recovery coverage

Public stages live in `sim/movement.hpp` and `sim/longitudinal.hpp`. Raw offsets
are retained where field meaning is uncertain. Passing explicit fields avoids
silently assuming road material, drift state, direction or a fixed frame rate.

| Original instructions | C++ stage | Scope |
| --- | --- | --- |
| `0x01FFBE70..0x01FFBFD0` | `resolve_cap_target` | Complete routine, including flag precedence and raw multipliers |
| `0x01FFBE04..0x01FFBE6C` | `approach_cap` | Complete routine; truncating multiply by literal `0xF37` and target clamp |
| `0x01FFBD9C..0x01FFBE04` | `update_fraction_direction` | Complete routine and both vector dependencies |
| `0x01FFB5B8..0x01FFB638` | `blend_direction` | Complete fragment, with wrapping vector differences and Y replacement |
| `0x01FFB930..0x01FFB9C8` | `apply_direction_penalty` | Complete routine; explicit coefficient, original value `0x1EC` |
| `0x01FFB638..0x01FFB754` | `assemble_displacement` | Complete fragment, including signed products, additive vectors and falling clamp |
| `0x01FFAE14..0x01FFAF18` | `normalize_movement` | Complete routine and original normalization dependency at `0x02039860` |
| `0x01FFB7CC..0x01FFB7F0` | `add_displacement` | Complete conditional position-add fragment |
| `0x01FFB638..0x01FFB7F0` | `update_movement_tail` | Connected range, all branch writes and dependencies accounted for |
| Scalar input/acceleration/drag/limiter | `update_grounded_drive` | Ordinary grounded A, B, coast and reverse, with explicit fraction/cap |

The connected tail includes the flag-gated accumulator at `0x01FF9C40`, the
global write through `0x0207A74C` to `0x0217AD10`, and damping of driver
`+0x4D4`. It preserves unrelated fields. Its global scale/value are explicit
inputs/outputs, rather than hidden global C++ state. The earlier bit-0 exclusion
has been removed after tracing and implementing that dependency.

Movement mode 0 dispatches to `0x020738F4`, a `BX LR` no-op. That does **not**
mean contact processing is absent: contact/correction also occurs elsewhere,
including the post-update phase.

## Arithmetic details

Fraction production divides the previous measured magnitude at `+0x2A4` by
`+0xD0` using the SDK's rounded division result. Values above 4096 are clamped,
and magnitude is then replaced by the cap. Depending on `+0x44` bit `0x10`,
direction at `+0x278` is either a cross product of `+0x120` and `+0x244`, or a
copy of `+0x138`. Cross products subtract the full 64-bit products **before**
extracting bits 12..43; separately truncating the two terms is incorrect.

Normalization first scales displacement by `+0x3F8` with truncating Q12
multiplication. Squared components accumulate with wrapping 64-bit arithmetic.
If the signed accumulated value is below 16, magnitude is zero and the previous
direction at `+0xB0` is preserved. Otherwise the original helper uses the signed
64-bit divider and unsigned integer square-root device, then constructs its
direction using the observed intermediate widths and rounding. The returned
magnitude is capped at `0xD000`; if capped, displacement is reconstructed from
the normalized direction. This is not replaced with floating-point `sqrt` or
an approximate normalization. Extreme overflow inputs retain original wrapping
behavior, even when the resulting value is not a conventional vector length.

B braking selects literal `-410` at `0x01FFBD80` and does not set coasting.
While already moving backward under B, the ordinary limiter restricts the cap
to `0x3000`. When A is pressed while moving backward, base acceleration gains
a **rounded** Q12 product of the wrapping speed negation and `0x52`. This differs
from the truncating products used in forward acceleration. The original forward
API retains its negative-speed guard; the broader `update_grounded_drive` API
supports the recovered reverse path. A+B, enhanced braking under `+0x4C` bit
`0x40`, drift-specific acceleration, boosts/effects and airborne scalar rules
remain outside that C++ API's declared domain.

## Evidence and current limits

The movement matrix contains 6,513 cases; grounded A/B/reverse adds 3,693 cases,
including 1,020 chained scalar steps. Existing 2,031 initialization and 4,822
forward-scalar comparisons remain separate. Movement tests include signed and
overflow boundaries, actual captured fields, flag combinations, and 256 chained
position writes. First differences identify a field and instruction case;
unrelated driver writes are rejected. Math-device and ARM/Thumb interworking
regressions have independent known-result tests.

Dispatcher schedules cover idle, accelerate/release/reapply, left, right,
braking, reverse/recovery, and left/right R inputs. The scalar C++ comparison is
skipped when raw state leaves its declared domain, rather than treating drift
or airborne execution as ordinary acceleration. The complete movement tail is
compared separately. Scenario names describe supplied buttons; raw state flags
and observed collision modes are retained to distinguish input coverage from
coverage of a mechanic. Successful dispatcher execution is an **original-code
reference**, not proof that every executed routine has been independently
reimplemented in C++.

The executor models division and square-root results, not device latency,
interrupts, graphics, DMA, or CPU cycles. It supports the ARM/Thumb instructions
needed by these bounded paths and fails on unsupported operations. It is not
a full DS emulator. The hardware arithmetic contract was checked against
[melonDS 1.1's math-device implementation](https://github.com/melonDS-emu/melonDS/blob/1.1/src/NDS.cpp#L1650);
the game rules and C++ arithmetic were independently recovered from ROM
instructions.

## Remaining recovery work

| Area | Remaining work |
| --- | --- |
| Full C++ driver update | Port the rest of input/steering/hop/drift, material preparation, effects and movement-body writes; the original dispatcher currently supplies these in offline replay |
| Contact geometry | Port KCL traversal/prism tests, correction ordering and surface responses; currently executed from original instructions and captured course memory |
| Additional driving states | Recover nonzero movement modes, mini-turbo/boost precedence, unusual surfaces, landing/airborne scalar branches and stronger braking |
| Scene/world integration | Account for outer scene phases, moving objects, timers, checkpoints, respawn and relevant RNG |
| Timing and live reference | Establish hardware tick cadence and sample alignment; compare against a later live trace |
| Vehicle coverage | Repeat behavioral validation beyond the Mario/kart-0 snapshot; parameter fidelity alone is insufficient |

Full physics remains unfinished. There is no guessed whole-frame C++ simulator
behind these results, and the existing synthetic `World` remains separate.
