#pragma once
#include <cstdint>

namespace kinoko {
struct FrameInput { bool accelerate = false; };
// Synthetic integer units only. These are NOT recovered MKDS parameters.
struct WorldData { std::int32_t acceleration = 3; std::int32_t max_speed = 12; };
struct WorldState {
    std::uint64_t tick = 0;
    std::int64_t position = 0;
    std::int32_t speed = 0;
    bool previous_accelerate = false;
    bool operator==(const WorldState&) const = default;
};
void step(WorldState& state, const WorldData& data, FrameInput input);
}
