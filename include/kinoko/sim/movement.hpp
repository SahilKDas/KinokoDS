#pragma once
#include <array>
#include <cstdint>

namespace kinoko::sim {
using RawVector = std::array<std::int32_t, 3>;
struct NormalizedMovement {
    RawVector displacement_a4, direction_b0;
    std::int32_t magnitude_2a4;
};
// Complete 0x01FFAE14 routine, including its 0x02039860 dependency.
// direction_b0 remains unchanged for squared magnitude <16 after scaling.
NormalizedMovement normalize_movement(RawVector displacement_a4,
    RawVector previous_direction_b0, std::int32_t scale_3f8);
// Individually recovered stages, not a complete physics tick. Unknown field
// meanings stay explicit by offset; callers must supply the actual game state.
std::int32_t approach_cap(std::int32_t current_d0, std::int32_t target_cc);
struct CapTargetInput {
    std::int32_t kart_max_speed, field_dc, field_d4, field_d8, field_4c4;
    std::uint32_t flags_7c, flags_48, flags_4c;
};
struct CapTargetOutput { std::int32_t target_cc, field_dc; };
// Complete 0x01FFBE70 routine; flag meanings are intentionally not inferred.
CapTargetOutput resolve_cap_target(const CapTargetInput& input);
std::int32_t apply_direction_penalty(std::int32_t scalar, std::uint32_t collision_mode_180,
    std::uint32_t flags_44, std::int32_t field_2d4, std::int32_t coefficient);
struct MovementFraction {
    std::int32_t fraction_2a0;
    std::int32_t magnitude_2a4;
};
MovementFraction movement_fraction(std::int32_t magnitude_2a4, std::int32_t cap_d0);
struct FractionDirectionOutput { MovementFraction ratio; RawVector direction_278; };
FractionDirectionOutput update_fraction_direction(std::int32_t magnitude_2a4, std::int32_t cap_d0,
    std::uint32_t flags_44, RawVector basis_120, RawVector normal_244, RawVector source_138);
RawVector blend_direction(RawVector direction_68, RawVector direction_50,
    std::uint32_t flags_44, std::uint32_t flags_4c, std::int32_t factor_240);
struct DisplacementInput {
    std::int32_t scalar;
    RawVector direction_68, direction_50;
    std::uint32_t collision_mode_180, flags_44, field_380;
    RawVector field_374;
    std::int32_t field_260, field_274;
    RawVector field_268, field_2f0, field_1fc;
};
struct DisplacementOutput {
    RawVector displacement_a4, signed_direction_5c;
};
// Exact fragment [0x01FFB638,0x01FFB754), before two subsequent helpers.
DisplacementOutput assemble_displacement(const DisplacementInput& input);
struct PositionOutput {
    RawVector position_80;
    std::int32_t field_38c;
};
// Exact fragment [0x01FFB7CC,0x01FFB7F0), after those helpers.
PositionOutput add_displacement(RawVector position_80, RawVector displacement_a4,
    std::uint32_t flags_7c, std::int32_t field_38c);
struct MovementTailInput {
    DisplacementInput assembly;
    RawVector position_80, previous_direction_b0;
    std::uint32_t flags_7c;
    std::int32_t field_38c, scale_3f8, field_2b8, field_2bc, field_c8;
    std::int32_t global_scale_217ad0c, global_value_217ad10, field_4d4;
};
struct MovementTailOutput {
    NormalizedMovement movement;
    RawVector signed_direction_5c;
    PositionOutput position;
    std::uint32_t flags_44;
    std::int32_t field_2b8, field_2bc;
    std::int32_t global_value_217ad10, field_4d4;
};
// Connected original instruction range [0x01FFB638,0x01FFB7F0).
// Includes its global projected-movement write when flags_7c bit 0 is set.
MovementTailOutput update_movement_tail(const MovementTailInput& input);
}
