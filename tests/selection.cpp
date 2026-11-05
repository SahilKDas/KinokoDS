#include "kinoko/assets/selection.hpp"
#include <iostream>
#include <stdexcept>

void require(bool condition) { if (!condition) throw std::runtime_error("selection test failed"); }
int main() {
    using namespace kinoko::assets;
    try {
        for (std::size_t character = 0; character < 13; ++character) {
            for (std::size_t kart = 0; kart < 50; ++kart) {
                require(select_parameter_records(character, kart, ParameterScene::race) == ParameterSelection{kart, character});
                require(select_parameter_records(character, kart, ParameterScene::battle) == ParameterSelection{37 + character, character});
                require(select_parameter_records(character, kart, ParameterScene::award_or_staff_roll) == ParameterSelection{0, 0});
            }
        }
        bool rejected = false;
        try { (void)select_parameter_records(13, 0, ParameterScene::battle); }
        catch (const std::out_of_range&) { rejected = true; }
        require(rejected);
        rejected = false;
        try { (void)select_parameter_records(0, 50, ParameterScene::race); }
        catch (const std::out_of_range&) { rejected = true; }
        require(rejected);
        std::cout << "parameter scene selection checks passed\n";
    } catch (const std::exception& e) { std::cerr << e.what() << '\n'; return 1; }
}
