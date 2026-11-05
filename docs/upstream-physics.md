# Upstream physics reuse audit

Inspected 2026-10-25, without computer use. Only bounded source files and metadata
were downloaded under ignored `local/research/`; no repository clones, ROMs,
build toolchains or upstream build outputs were downloaded.

## Sources pinned

| Project | Commit | Useful material |
| --- | --- | --- |
| ai-tdd-labs/mkds-decomp | c6e18fa4b346643b74c402b605a84b43cba16c01 | Parameter loader/copy implementation, fixed-point SDK routines, USA symbol inventory |
| XorTroll/mkds-re | 4124540cfc0526f4febed62fe3227518f0f64f47 | MIT-licensed exported types/symbols and RE tools |
| HaroohiePals/MKDS-decomp-headers | 2d089194e146650406f6c257914ec397d35c8de7 | Driver/parameter structures and declarations; no repository-wide license detected |

The matching decomp's license explicitly applies MIT to its tooling and
documentation. Its separate paragraph describes reconstructed game sources;
it does not expressly place `src/` under that MIT grant. Therefore no game source
was copied into KinokoDS. The downloaded copies are local research material.
KinokoDS's new selection implementation is independently reconstructed from the
captured AMCE instructions, with upstream function names guiding inspection.
Do not describe it as an MIT-licensed upstream source transplant.

Links to inspected files:

- https://github.com/ai-tdd-labs/mkds-decomp/blob/c6e18fa4b346643b74c402b605a84b43cba16c01/LICENSE
- https://github.com/ai-tdd-labs/mkds-decomp/blob/c6e18fa4b346643b74c402b605a84b43cba16c01/src/arm9/CopyKartCharPhysicalParam.c
- https://github.com/ai-tdd-labs/mkds-decomp/blob/c6e18fa4b346643b74c402b605a84b43cba16c01/src/arm9/CreateLoadPhysicalParams.c
- https://github.com/XorTroll/mkds-re/blob/4124540cfc0526f4febed62fe3227518f0f64f47/LICENSE

## Cross-checks and implementation

The USA symbols locate the parameter copy routine at 0x0208AEA8, agreeing with
our captured instructions. At entry, r0 selects the destination driver, r1 the
kart source and r2 the character source. Some upstream C argument labels are
misleading: follow the assembly's table strides and actual use instead.

The AMCE routine performs these selections before copying 152 and 8 bytes:

- Award/staff-roll predicate true: both source indices become 0.
- Otherwise, race mode value 2: kart index becomes character index + 37.
- Otherwise: preserve the selected kart and character indices.

The existing RE race-mode enum labels value 2 as battle. The code's index
transformation is confirmed statically; its behavior has not been exercised in
a live battle session. `select_parameter_records` implements this selection
using an explicit scene argument. It accepts table indices, not unlock rules,
and returns independent kart/character record indices. Award selection ignores
both supplied indices, and battle ignores the supplied kart, matching the
instruction control flow. Bounds checks protect the host API.

This explains slots 37..49 as character-indexed battle parameter records. Slot
36 remains unclassified by this finding. Ordinary race selection still permits
the full raw table range without claiming every record is menu-selectable.

The loader's cached field is kart-record offset 0x10 (max speed), not evidence
of a file header or entry-table pointer. Our actual ROM tables are headerless.
This is another reason to cross-check descriptive comments against bytes.

## What is still missing

The inspected sources provide useful parameter and math work, but no complete
recoverable, drop-in driving simulation was identified. Acceleration, steering,
drift/hop state transitions, contacts and tick ordering remain outstanding.
The existing captured surface multiplier loop is implemented separately and
matches Mario/kart 0's active snapshot. Neither that comparison nor the new
selection tests establish complete gameplay fidelity.

The subsequent [offline longitudinal pipeline](offline-longitudinal.md) located
the speed update in ROM-recovered ITCM and implemented the ordinary scalar path.
Its limits and differential evidence supersede the earlier next-target note.
