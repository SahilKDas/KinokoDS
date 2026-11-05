#pragma once
#include "kinoko/assets/parameters.hpp"
#include "kinoko/assets/selection.hpp"

namespace kinoko::assets {
struct InitializationContext {
    ParameterScene scene = ParameterScene::race;
    // Raw value read from race-config +0x10: 0 => 0xB33/-40,
    // 1 => 0xD9A/-20, all other values => unity/0.
    std::uint32_t engine_class_raw = 2;
};
struct PreparedParameters {
    KartParameters kart;
    CharacterParameters character;
    ParameterSelection selection;
    std::int32_t driver_field_3f4_raw;
};
PreparedParameters prepare_parameters(std::span<const KartParameters> karts,
    std::span<const CharacterParameters> characters, std::size_t character,
    std::size_t kart, InitializationContext context);
}
