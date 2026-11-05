#include "kinoko/replay/trace.hpp"
#include <fstream>
#include <iostream>
#include <stdexcept>

int main(int argc, char** argv) {
    if (argc != 3) { std::cerr << "usage: kinoko_compare EXPECTED ACTUAL\n"; return 2; }
    try {
        std::ifstream expected(argv[1]), actual(argv[2]);
        if (!expected || !actual) throw std::runtime_error("cannot open trace");
        const auto a = kinoko::read_trace(expected), b = kinoko::read_trace(actual);
        if (const auto diff = kinoko::first_difference(a, b)) {
            std::cout << *diff << '\n'; return 1;
        }
        std::cout << "match: " << a.rows.size() << " ticks (captured fields only)\n";
        return 0;
    } catch (const std::exception& e) { std::cerr << e.what() << '\n'; return 2; }
}
