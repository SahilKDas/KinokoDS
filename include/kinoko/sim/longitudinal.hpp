#pragma once
#include "kinoko/assets/parameters.hpp"

namespace kinoko::sim {
struct LongitudinalState {
    std::int32_t speed_raw = 0;
    bool coasting = false; // driver +0x44 bit 0x400
    bool operator==(const LongitudinalState&) const = default;
};
struct LongitudinalInput {
    bool accelerate = false;
    // Upstream-computed driver +0x2A0; do not infer this from speed here.
    std::int32_t speed_fraction_raw = 0;
    bool grounded = true;
    bool drifting = false;
    bool special_effect = false;
    bool brake = false;
};
// Grounded, forward, straight, no boost/brake/slopes/contacts/rotation effects.
// Executes only the recovered scalar input/acceleration/drag/cap stages.
// No position integration, upstream fraction update, or whole-frame simulation.
LongitudinalState update_longitudinal(LongitudinalState state,
    const assets::KartParameters& prepared, LongitudinalInput input,
    std::int32_t resolved_max_speed_raw);
// Extends the same ordinary scalar domain to B braking and reverse motion.
// Simultaneous A+B, drift, boosts/effects and airborne motion remain excluded.
LongitudinalState update_grounded_drive(LongitudinalState state,
    const assets::KartParameters& prepared, LongitudinalInput input,
    std::int32_t resolved_max_speed_raw);
}
