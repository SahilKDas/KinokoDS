#include "kinoko/sim/longitudinal.hpp"
#include "kinoko/math/fixed.hpp"
#include <stdexcept>

namespace kinoko::sim {
LongitudinalState update_longitudinal(LongitudinalState state,
    const assets::KartParameters& p, LongitudinalInput in, std::int32_t cap) {
    if (state.speed_raw < 0 || in.brake) throw std::invalid_argument("outside recovered forward longitudinal domain");
    return update_grounded_drive(state, p, in, cap);
}
LongitudinalState update_grounded_drive(LongitudinalState state,
    const assets::KartParameters& p, LongitudinalInput in, std::int32_t cap) {
    if (!in.grounded || in.drifting || in.special_effect || (in.accelerate && in.brake) ||
        in.speed_fraction_raw < 0 || in.speed_fraction_raw > 4096 || cap <= 0 ||
        p.base_acceleration < 0 || p.unknown_18 < 0 ||
        p.base_acceleration > 4096 || p.unknown_18 > 4096 || p.deceleration < 0 || p.deceleration > 4096)
        throw std::invalid_argument("outside recovered grounded longitudinal domain");
    auto acceleration = p.base_acceleration;
    const bool initially_negative = state.speed_raw < 0;
    if (in.brake) acceleration = -410; // literal 0x01FFBD80
    else if (initially_negative) {
        acceleration = math::add(acceleration, math::fx_mul(math::sub(0, state.speed_raw), 0x52, true));
    } else if (in.speed_fraction_raw >= 2048) {
        if (in.speed_fraction_raw > p.unknown_1c) acceleration = p.unknown_18;
        else {
            const auto gradient = math::fx_div(math::sub(p.base_acceleration, p.unknown_18), math::sub(p.unknown_1c, 2048));
            acceleration = math::sub(p.base_acceleration, math::fx_mul(gradient, in.speed_fraction_raw - 2048));
        }
    }
    // Input updater clears the previous coasting flag; the speed routine sets
    // it again only on release. Acceleration adds with ARM's 32-bit wrapping.
    state.coasting = !in.accelerate && !in.brake;
    if (in.accelerate || in.brake) state.speed_raw = math::add(state.speed_raw, acceleration);
    if (state.coasting) state.speed_raw = math::fx_mul(state.speed_raw, p.deceleration);
    // Mirror the cap routine's signed magnitude handling even if the addition
    // wrapped. Its slope/scale/extra-speed fields are the ordinary 0/1 values.
    const bool negative = state.speed_raw < 0;
    auto magnitude = state.speed_raw <= 0 ? math::sub(0, state.speed_raw) : state.speed_raw;
    if (in.brake && initially_negative && cap > 0x3000) cap = 0x3000;
    if (magnitude > cap) magnitude = cap;
    else if (magnitude <= 410 && !in.accelerate && !in.brake) magnitude = 0;
    state.speed_raw = negative ? math::sub(0, magnitude) : magnitude;
    return state;
}
}
