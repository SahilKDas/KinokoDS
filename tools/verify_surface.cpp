#include "kinoko/assets/parameters.hpp"
#include <fstream>
#include <iostream>
#include <stdexcept>

std::vector<std::byte> load(const char* path) {
    std::ifstream in(path, std::ios::binary | std::ios::ate);
    const auto size = in.tellg();
    if (!in || size < 0 || size > 65536) throw std::runtime_error("invalid parameter file");
    std::vector<std::byte> data(static_cast<std::size_t>(size));
    in.seekg(0);
    in.read(reinterpret_cast<char*>(data.data()), size);
    if (!in) throw std::runtime_error("read failed");
    return data;
}
int main(int argc, char** argv) {
    if (argc != 4) { std::cerr << "usage: kinoko_verify_surface KART_TABLE CHAR_TABLE ACTIVE_KART_0\n"; return 2; }
    try {
        const auto k = kinoko::assets::read_kart_parameters(load(argv[1]));
        const auto c = kinoko::assets::read_character_parameters(load(argv[2]));
        const auto active = kinoko::assets::read_kart_parameters(load(argv[3]));
        if (k.size() != 50 || c.size() != 13 || active.size() != 1)
            throw std::runtime_error("expected pinned baseline table dimensions");
        const auto predicted = kinoko::assets::apply_character_surface_factor(k[0], c[0]);
        if (!(predicted == active[0])) { std::cout << "active kart differs from prediction\n"; return 1; }
        std::cout << "Mario/kart 0: all decoded fields match active 152-byte record after surface adjustment\n";
    } catch (const std::exception& e) { std::cerr << e.what() << '\n'; return 2; }
}
