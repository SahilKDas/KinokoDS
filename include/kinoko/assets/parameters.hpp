#pragma once
#include <array>
#include <cstddef>
#include <cstdint>
#include <span>
#include <vector>

namespace kinoko::assets {
// Raw signed integers: no implicit scaling, host struct packing, or floats.
// Field names follow research headers; runtime semantics remain unverified.
struct KartParameters {
    std::int32_t collision_sphere_size, collision_sphere_z_offset, unknown_08;
    std::int16_t weight, drift_boost_time;
    std::int32_t max_speed, base_acceleration, unknown_18, unknown_1c;
    std::int32_t drift_base_acceleration, unknown_24, unknown_28, deceleration;
    std::int16_t handling, drift;
    std::int32_t drift_turning_compensation;
    std::array<std::int32_t, 12> collision_velocity_multipliers;
    std::array<std::int32_t, 12> collision_speed_multipliers;
    bool operator==(const KartParameters&) const = default;
};
struct CharacterParameters { std::int32_t unknown_00, weight; };
std::vector<KartParameters> read_kart_parameters(std::span<const std::byte> bytes);
std::vector<CharacterParameters> read_character_parameters(std::span<const std::byte> bytes);
std::array<std::byte, 0x98> encode_kart_parameters(const KartParameters& value);
std::array<std::byte, 8> encode_character_parameters(const CharacterParameters& value);
// Confirmed surface adjustment only; not the full mode-dependent initialization.
// Always pass the original record, not an already-adjusted copy.
KartParameters apply_character_surface_factor(const KartParameters& original,
                                              const CharacterParameters& character);
}
