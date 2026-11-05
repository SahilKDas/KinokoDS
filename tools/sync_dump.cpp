#include "kinoko/assets/parameters.hpp"
#include "kinoko/assets/selection.hpp"
#include <fstream>
#include <iostream>
#include <stdexcept>

std::vector<std::byte> load(const char* path) {
    std::ifstream in(path, std::ios::binary | std::ios::ate);
    const auto size = in.tellg();
    if (!in || size < 0 || size > 65536) throw std::runtime_error("invalid table file");
    std::vector<std::byte> bytes(static_cast<std::size_t>(size));
    in.seekg(0); in.read(reinterpret_cast<char*>(bytes.data()), size);
    if (!in) throw std::runtime_error("table read failed");
    return bytes;
}
template<class T> void hex(const T& bytes) {
    constexpr char digits[] = "0123456789abcdef";
    for (auto b : bytes) {
        const auto n = std::to_integer<unsigned>(b);
        std::cout << digits[n >> 4] << digits[n & 15];
    }
}
int main(int argc, char** argv) {
    if (argc != 3) { std::cerr << "usage: kinoko_sync_dump KART_TABLE CHAR_TABLE\n"; return 2; }
    using namespace kinoko::assets;
    try {
        const auto k = read_kart_parameters(load(argv[1]));
        const auto c = read_character_parameters(load(argv[2]));
        if (k.size() != 50 || c.size() != 13) throw std::runtime_error("expected pinned table dimensions");
        for (std::size_t i = 0; i < k.size(); ++i) {
            std::cout << "kart," << i << ','; hex(encode_kart_parameters(k[i])); std::cout << '\n';
        }
        for (std::size_t i = 0; i < c.size(); ++i) {
            std::cout << "char," << i << ','; hex(encode_character_parameters(c[i])); std::cout << '\n';
        }
        for (int mode = 0; mode < 3; ++mode)
            for (std::size_t ch = 0; ch < c.size(); ++ch)
                for (std::size_t kart = 0; kart < k.size(); ++kart) {
                    const auto selection = select_parameter_records(ch, kart, static_cast<ParameterScene>(mode));
                    const auto prepared = apply_character_surface_factor(k[selection.kart_record], c[selection.character_record]);
                    std::cout << "case," << mode << ',' << ch << ',' << kart << ',' << selection.kart_record << ',' << selection.character_record << ',';
                    hex(encode_kart_parameters(prepared)); std::cout << ',';
                    hex(encode_character_parameters(c[selection.character_record])); std::cout << '\n';
                }
    } catch (const std::exception& e) { std::cerr << e.what() << '\n'; return 2; }
}
