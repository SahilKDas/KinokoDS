#pragma once
#include <cstddef>

namespace kinoko::assets {
enum class ParameterScene { race, battle, award_or_staff_roll };
struct ParameterSelection {
    std::size_t kart_record;
    std::size_t character_record;
    bool operator==(const ParameterSelection&) const = default;
};
// Independent reconstruction cross-checked against captured AMCE instructions
// at 0x0208AEA8..0x0208AF34. Does not enforce menu unlock restrictions.
ParameterSelection select_parameter_records(std::size_t character, std::size_t kart,
                                           ParameterScene scene);
}
