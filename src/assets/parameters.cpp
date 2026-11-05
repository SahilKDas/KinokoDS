#include "kinoko/assets/parameters.hpp"
#include <bit>
#include <stdexcept>

namespace kinoko::assets {
namespace {
std::int16_t s16(std::span<const std::byte> b, std::size_t offset) {
    const auto v = static_cast<std::uint16_t>(std::to_integer<unsigned>(b[offset]) |
        (std::to_integer<unsigned>(b[offset + 1]) << 8));
    return std::bit_cast<std::int16_t>(v);
}
std::int32_t s32(std::span<const std::byte> b, std::size_t offset) {
    std::uint32_t v = 0;
    for (unsigned i = 0; i < 4; ++i)
        v |= std::to_integer<std::uint32_t>(b[offset + i]) << (i * 8);
    return std::bit_cast<std::int32_t>(v);
}
void validate(std::span<const std::byte> bytes, std::size_t stride) {
    if (bytes.empty() || bytes.size() % stride || bytes.size() / stride > 256)
        throw std::invalid_argument("invalid parameter table length");
}
}
std::vector<KartParameters> read_kart_parameters(std::span<const std::byte> bytes) {
    validate(bytes, 0x98);
    std::vector<KartParameters> result;
    for (std::size_t i = 0; i < bytes.size(); i += 0x98) {
        const auto b = bytes.subspan(i, 0x98);
        KartParameters p{s32(b, 0), s32(b, 4), s32(b, 8), s16(b, 12), s16(b, 14),
            s32(b, 16), s32(b, 20), s32(b, 24), s32(b, 28), s32(b, 32),
            s32(b, 36), s32(b, 40), s32(b, 44), s16(b, 48), s16(b, 50),
            s32(b, 52), {}, {}};
        for (std::size_t n = 0; n < 12; ++n) {
            p.collision_velocity_multipliers[n] = s32(b, 0x38 + n * 4);
            p.collision_speed_multipliers[n] = s32(b, 0x68 + n * 4);
        }
        result.push_back(p);
    }
    return result;
}
std::vector<CharacterParameters> read_character_parameters(std::span<const std::byte> bytes) {
    validate(bytes, 8);
    std::vector<CharacterParameters> result;
    for (std::size_t i = 0; i < bytes.size(); i += 8)
        result.push_back({s32(bytes, i), s32(bytes, i + 4)});
    return result;
}
KartParameters apply_character_surface_factor(const KartParameters& original,
                                              const CharacterParameters& character) {
    auto result = original;
    for (auto& value : result.collision_speed_multipliers) {
        if (value >= 4096) continue;
        const auto product = static_cast<std::int64_t>(value) * character.unknown_00;
        // ARM SMULL + ADDS/ADC + extraction of bits [12..43]. Use unsigned
        // extraction and bit_cast to preserve the result without signed shifts
        // or implementation-defined narrowing, including wraparound cases.
        const auto shifted = static_cast<std::uint64_t>(product + 2048) >> 12;
        value = std::bit_cast<std::int32_t>(static_cast<std::uint32_t>(shifted));
    }
    return result;
}
std::array<std::byte, 0x98> encode_kart_parameters(const KartParameters& p) {
    std::array<std::byte, 0x98> result{};
    const auto put = [&](std::size_t offset, auto value) {
        const auto bits = static_cast<std::uint32_t>(value);
        for (std::size_t i = 0; i < sizeof(value); ++i)
            result[offset + i] = static_cast<std::byte>((bits >> (i * 8)) & 255);
    };
    put(0, p.collision_sphere_size); put(4, p.collision_sphere_z_offset); put(8, p.unknown_08);
    put(12, p.weight); put(14, p.drift_boost_time); put(16, p.max_speed);
    put(20, p.base_acceleration); put(24, p.unknown_18); put(28, p.unknown_1c);
    put(32, p.drift_base_acceleration); put(36, p.unknown_24); put(40, p.unknown_28);
    put(44, p.deceleration); put(48, p.handling); put(50, p.drift);
    put(52, p.drift_turning_compensation);
    for (std::size_t i = 0; i < 12; ++i) {
        put(0x38 + i * 4, p.collision_velocity_multipliers[i]);
        put(0x68 + i * 4, p.collision_speed_multipliers[i]);
    }
    return result;
}
std::array<std::byte, 8> encode_character_parameters(const CharacterParameters& p) {
    std::array<std::byte, 8> result{};
    for (std::size_t field = 0; field < 2; ++field) {
        const auto bits = static_cast<std::uint32_t>(field ? p.weight : p.unknown_00);
        for (std::size_t i = 0; i < 4; ++i)
            result[field * 4 + i] = static_cast<std::byte>((bits >> (i * 8)) & 255);
    }
    return result;
}
}
