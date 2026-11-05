#include "kinoko/sim/world.hpp"
#include <algorithm>
#include <limits>
#include <stdexcept>

namespace kinoko {
void step(WorldState& state, const WorldData& data, FrameInput input) {
    if (data.acceleration < 0 || data.max_speed < 0 || state.speed < 0)
        throw std::invalid_argument("negative synthetic parameter/state");
    auto next = state;
    if (input.accelerate)
        next.speed = static_cast<std::int32_t>(std::min<std::int64_t>(
            static_cast<std::int64_t>(next.speed) + data.acceleration, data.max_speed));
    if (next.position > std::numeric_limits<std::int64_t>::max() - next.speed ||
        next.tick == std::numeric_limits<std::uint64_t>::max())
        throw std::overflow_error("synthetic state overflow");
    next.position += next.speed;
    ++next.tick;
    next.previous_accelerate = input.accelerate;
    state = next;
}
}
