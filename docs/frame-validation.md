# Frame timing and position validation

Status on 2026-10-25: **full-frame timing, position integration, and live
acceleration are not verified**. The stationary RAM capture and the existing
scalar differential tests cannot establish any of these results.
Subsequent [offline physics recovery](offline-physics.md) implements and compares
the position-add/normalization stages and replays the original driver/contact
dispatcher. Those results validate bounded offline paths; full-game timing and
live position agreement remain pending.

## Reproducible static evidence

Run `python -B tools/inspect_frame.py`. It verifies the pinned ROM through
`CodeImage`, records instruction listings and SHA-256 hashes for bounded code/data
ranges in ignored `local/validation/frame-inspection/`, and labels its output
as static inspection. It does not start an emulator.

The alternate caller `0x020651FC` calls fraction production at
`0x02065338`, input/acceleration handling at `0x02065340`, another update at
`0x02065348`, and movement processing at `0x020653AC`. This is instruction
ordering, not evidence of how often the caller runs per display frame. The
captured driver's selected callback leads to `0x01FFCC50`; see the offline
recovery document for dispatcher order and the distinction between callers.

`0x01FFBD9C` divides the previously stored driver `+0x2A4` by `+0xD0`, stores
the rounded division result at `+0x2A0`, and clamps results above 4096. The
producer and age of `+0x2A4` still need accounting across the complete tick.

At `0x01FFB638`, a local scalar is multiplied by each component of driver
`+0x68` using signed long multiplication and extraction of bits 12..43, with
no rounding addition. The vector becomes `+0xA4`. Subsequent instructions
combine `+0x374`, the Y contribution at `+0x260`, a helper using `+0x274`
and `+0x268`, and vectors at `+0x2F0` and `+0x1FC`. Calls to `0x01FF9C40`
and `0x01FFAE14` occur before position addition. Those dependencies are now
implemented and compared as part of the connected movement tail; uncertain
field meanings remain explicit by offset.

When driver `+0x7C` bit `0x20` is clear, `0x01FFB7D8..0x01FFB7E4` performs
`position[3] += displacement[3]` on fields `+0x80` and `+0xA4`, through the
complete helper `0x02148504..0x02148538`. Each component uses wrapping 32-bit
addition. This confirms one position write, not the final position for a
complete tick: other collision/correction paths and later writers remain to
be accounted for. No seconds-based timestep multiplier appears in this
addition; the caller cadence remains unmeasured.

## Live capture attempt and blocker

An isolated copy of the existing melonDS 1.1 executable was tried with
`-platform offscreen`, muted audio, separate local saves/configuration, and
debugger ports 4333/4334. The installed binary reported that only the
`windows` Qt platform plugin was available. Its startup error dialogs appeared
on the desktop; the user closed them. No debugger connection, race navigation,
or live acceleration trace succeeded. No physical inputs or physics fields
were changed. The temporary emulator processes were stopped, and the extra
executable was removed to recover space.

Do not repeat this launch with this binary. No desktop automation is
authorized. A compatible headless runtime or a later user-operated reference
session is needed before live verification can proceed. melonDS startup and
CLI implementation are documented in the upstream
[1.1 main](https://github.com/melonDS-emu/melonDS/blob/1.1/src/frontend/qt_sdl/main.cpp)
and [CLI](https://github.com/melonDS-emu/melonDS/blob/1.1/src/frontend/qt_sdl/CLI.cpp)
sources; CLI availability does not imply that an offscreen plugin is bundled.

## Required evidence before marking verified

- Establish an independent emulated VBlank/frame counter and count driver
  updates between consecutive values. Debugger wall time is not game time.
- Confirm Mario, kart 0, raw mode/class, course, prepared parameter bytes,
  initial position, and ordinary grounded state in the running reference.
- Capture input mapping, fraction production, acceleration, drag, limiter,
  displacement, and final post-correction position at fixed instruction
  boundaries. Preserve input history and all relevant flags.
- Compare the full recovered dependency path against the same initial state
  for acceleration, steady speed, release, and reapplication; report the first
  differing field and phase. Include a repeated run with matching initial state.
- Retain bounded trace data, code hashes, emulator/ROM provenance, and an
  explicit record of unsupported states. Do not feed scalar speed back as
  measured movement magnitude in a purported full-frame test.

The existing synthetic simulator remains separate. Neither it nor the
offline scalar validator currently implements this complete frame path.
