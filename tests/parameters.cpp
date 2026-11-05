#include "kinoko/assets/parameters.hpp"
#include <iostream>
#include <stdexcept>

void require(bool condition) { if (!condition) throw std::runtime_error("parameter test failed"); }
int main() {
    try {
        std::array<std::byte, 0x98 * 2> bytes{};
        bytes[12] = std::byte{0xfe}; bytes[13] = std::byte{0xff};
        bytes[16] = std::byte{0x78}; bytes[17] = std::byte{0x56};
        bytes[18] = std::byte{0x34}; bytes[19] = std::byte{0x12};
        bytes[52] = std::byte{0xff}; bytes[53] = std::byte{0xff};
        bytes[54] = std::byte{0xff}; bytes[55] = std::byte{0xff};
        bytes[0x98 + 16] = std::byte{42}; bytes[0x94] = std::byte{7};
        const auto p = kinoko::assets::read_kart_parameters(bytes);
        require(p.size() == 2 && p[0].weight == -2 && p[0].max_speed == 0x12345678);
        require(p[0].drift_turning_compensation == -1 && p[0].collision_speed_multipliers[11] == 7);
        require(p[1].max_speed == 42);
        // Exercise every serialized byte, including negative and unknown fields.
        std::array<std::byte, 0x98> patterned{};
        for (std::size_t i = 0; i < patterned.size(); ++i)
            patterned[i] = static_cast<std::byte>((i * 37 + 129) & 255);
        require(kinoko::assets::encode_kart_parameters(kinoko::assets::read_kart_parameters(patterned)[0]) == patterned);
        std::array<std::byte, 8> character{};
        character[4] = std::byte{0xff}; character[5] = std::byte{0xff};
        character[6] = std::byte{0xff}; character[7] = std::byte{0x7f};
        require(kinoko::assets::read_character_parameters(character)[0].weight == 2147483647);
        require(kinoko::assets::encode_character_parameters(kinoko::assets::read_character_parameters(character)[0]) == character);
        bool rejected = false;
        try { (void)kinoko::assets::read_kart_parameters(character); }
        catch (const std::invalid_argument&) { rejected = true; }
        require(rejected);
        rejected = false;
        try { (void)kinoko::assets::read_character_parameters({}); }
        catch (const std::invalid_argument&) { rejected = true; }
        require(rejected);
        std::cout << "parameter checks passed\n";
    } catch (const std::exception& e) { std::cerr << e.what() << '\n'; return 1; }
}
