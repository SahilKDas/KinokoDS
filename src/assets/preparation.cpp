#include "kinoko/assets/preparation.hpp"
#include "kinoko/math/fixed.hpp"
#include <bit>
#include <stdexcept>

namespace kinoko::assets {
PreparedParameters prepare_parameters(std::span<const KartParameters> karts,
    std::span<const CharacterParameters> characters, std::size_t character,
    std::size_t kart, InitializationContext context) {
    const auto selection = select_parameter_records(character, kart, context.scene);
    if (selection.kart_record >= karts.size() || selection.character_record >= characters.size())
        throw std::out_of_range("missing selected parameter record");
    auto value = karts[selection.kart_record];
    const auto driver = characters[selection.character_record];
    std::int32_t multiplier = 4096, drift_delta = 0;
    if (context.scene != ParameterScene::award_or_staff_roll) {
        if (context.engine_class_raw == 0) { multiplier = 0xb33; drift_delta = -40; }
        else if (context.engine_class_raw == 1) { multiplier = 0xd9a; drift_delta = -20; }
    }
    value.max_speed = math::fx_mul(value.max_speed, multiplier);
    value.drift = std::bit_cast<std::int16_t>(static_cast<std::uint16_t>(
        static_cast<std::uint32_t>(value.drift) + static_cast<std::uint32_t>(drift_delta)));
    const auto field_3f4 = math::fx_div(math::sub(4096, value.collision_speed_multipliers[4]),
                                      math::add(value.collision_sphere_size, value.collision_sphere_size));
    value = apply_character_surface_factor(value, driver);
    return {value, driver, selection, field_3f4};
}
}
