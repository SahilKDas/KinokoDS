#include "kinoko/assets/parameters.hpp"
#include <limits>
#include <stdexcept>
#include <iostream>

void require(bool condition) { if (!condition) throw std::runtime_error("surface adjustment failed"); }
int main() {
    try {
        kinoko::assets::KartParameters source{};
        source.max_speed = 1234;
        source.collision_speed_multipliers = {4096, 4097, 4095, 1, -1, -3, 0, 2048, 4096, 4096, 4096, 4096};
        const auto p = kinoko::assets::apply_character_surface_factor(source, {2048, 0});
        require(p.collision_speed_multipliers == std::array<std::int32_t, 12>{4096, 4097, 2048, 1, 0, -1, 0, 1024, 4096, 4096, 4096, 4096});
        require(source.collision_speed_multipliers[2] == 4095 && p.max_speed == 1234);
        require(p.collision_velocity_multipliers == source.collision_velocity_multipliers);
        source.collision_speed_multipliers[0] = std::numeric_limits<std::int32_t>::min();
        const auto wrapped = kinoko::assets::apply_character_surface_factor(source, {std::numeric_limits<std::int32_t>::min(), 0});
        require(wrapped.collision_speed_multipliers[0] == 0);
        std::cout << "surface factor checks passed\n";
    } catch (const std::exception& e) { std::cerr << e.what() << '\n'; return 1; }
}
