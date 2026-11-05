#include "kinoko/assets/parameters.hpp"
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <vector>

std::vector<std::byte> load(const char* path) {
    std::ifstream in(path, std::ios::binary | std::ios::ate);
    const auto size = in.tellg();
    if (!in || size < 0 || size > 65536) throw std::runtime_error("cannot read small parameter table");
    std::vector<std::byte> data(static_cast<std::size_t>(size));
    in.seekg(0);
    in.read(reinterpret_cast<char*>(data.data()), size);
    if (!in) throw std::runtime_error("parameter read failed");
    return data;
}
int main(int argc, char** argv) {
    if (argc != 3) { std::cerr << "usage: kinoko_parameters KART_TABLE CHARACTER_TABLE\n"; return 2; }
    try {
        const auto karts = kinoko::assets::read_kart_parameters(load(argv[1]));
        const auto characters = kinoko::assets::read_character_parameters(load(argv[2]));
        std::cout << "Raw parameter import; runtime semantics UNVERIFIED\nkart_id,max_speed_raw,base_acceleration_raw\n";
        for (std::size_t i = 0; i < karts.size(); ++i)
            std::cout << i << ',' << karts[i].max_speed << ',' << karts[i].base_acceleration << '\n';
        std::cout << "character_id,unknown_00_raw,weight_raw\n";
        for (std::size_t i = 0; i < characters.size(); ++i)
            std::cout << i << ',' << characters[i].unknown_00 << ',' << characters[i].weight << '\n';
    } catch (const std::exception& e) { std::cerr << e.what() << '\n'; return 2; }
}
