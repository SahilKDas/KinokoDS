#include "kinoko/assets/selection.hpp"
#include <stdexcept>

namespace kinoko::assets {
ParameterSelection select_parameter_records(std::size_t character, std::size_t kart,
                                           ParameterScene scene) {
    switch (scene) {
    case ParameterScene::award_or_staff_roll:
        return {0, 0};
    case ParameterScene::battle:
        if (character >= 13) throw std::out_of_range("character record");
        return {37 + character, character};
    case ParameterScene::race:
        if (character >= 13 || kart >= 50) throw std::out_of_range("parameter record");
        return {kart, character};
    }
    throw std::invalid_argument("unknown parameter scene");
}
}
