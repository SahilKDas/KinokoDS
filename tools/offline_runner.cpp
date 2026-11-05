#include "kinoko/assets/preparation.hpp"
#include "kinoko/sim/longitudinal.hpp"
#include <fstream>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <string>

std::vector<std::byte> load(const char* path) {
    std::ifstream in(path, std::ios::binary | std::ios::ate);
    auto length = in.tellg();
    if (!in || length < 0 || length > 65536) throw std::runtime_error("invalid table");
    std::vector<std::byte> result(static_cast<std::size_t>(length));
    in.seekg(0); in.read(reinterpret_cast<char*>(result.data()), length);
    if (!in) throw std::runtime_error("read failure");
    return result;
}
template<class T> void hex(const T& bytes) {
    constexpr char digits[] = "0123456789abcdef";
    for (auto byte : bytes) {
        const auto value = std::to_integer<unsigned>(byte);
        std::cout << digits[value >> 4] << digits[value & 15];
    }
}
int main(int argc, char** argv) {
    if (argc != 3) return 2;
    using namespace kinoko;
    try {
        const auto karts = assets::read_kart_parameters(load(argv[1]));
        const auto chars = assets::read_character_parameters(load(argv[2]));
        if (karts.size() != 50 || chars.size() != 13) throw std::runtime_error("table dimensions");
        std::string line;
        while (std::getline(std::cin, line)) {
            std::istringstream input(line);
            char command; std::size_t ch, kart; int scene; std::uint32_t engine;
            if (!(input >> command >> ch >> kart >> scene >> engine)) return 2;
            try {
                if (scene < 0 || scene > 2) throw std::invalid_argument("scene");
                const auto prepared = assets::prepare_parameters(karts, chars, ch, kart,
                    {static_cast<assets::ParameterScene>(scene), engine});
                if (command == 'P') {
                    std::cout << "P " << prepared.selection.kart_record << ' ' << prepared.selection.character_record
                        << ' ' << prepared.driver_field_3f4_raw << ' ';
                    hex(assets::encode_kart_parameters(prepared.kart)); std::cout << ' ';
                    hex(assets::encode_character_parameters(prepared.character)); std::cout << '\n';
                } else if (command == 'L' || command == 'V') {
                    sim::LongitudinalState state; sim::LongitudinalInput controls; std::int32_t cap;
                    if (!(input >> state.speed_raw >> state.coasting >> controls.accelerate >> controls.speed_fraction_raw >> cap)) return 2;
                    if (command == 'V' && !(input >> controls.brake)) return 2;
                    const auto result = command == 'V' ? sim::update_grounded_drive(state, prepared.kart, controls, cap)
                                                       : sim::update_longitudinal(state, prepared.kart, controls, cap);
                    std::cout << command << ' ' << result.speed_raw << ' ' << result.coasting << '\n';
                } else return 2;
            } catch (const std::exception& e) { std::cout << "E " << e.what() << '\n'; }
        }
    } catch (const std::exception& e) { std::cerr << e.what() << '\n'; return 2; }
}
