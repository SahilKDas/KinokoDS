#include "kinoko/replay/trace.hpp"
#include "kinoko/sim/world.hpp"
#include <fstream>
#include <iostream>
#include <stdexcept>

int main(int argc, char** argv) {
    if (argc != 3) { std::cerr << "usage: kinoko_accel INPUT_TRACE OUTPUT_TRACE\n"; return 2; }
    try {
        std::ifstream input(argv[1]);
        if (!input) throw std::runtime_error("cannot open input trace");
        auto trace = kinoko::read_trace(input);
        if (trace.profile != "synthetic-accel-v1")
            throw std::runtime_error("only synthetic-accel-v1 is implemented; no MKDS physics yet");
        kinoko::WorldState state;
        for (auto& row : trace.rows) {
            kinoko::step(state, {}, {row.accelerate});
            row = {state.tick, row.accelerate, state.position, state.speed};
        }
        std::ofstream output(argv[2]);
        kinoko::write_trace(output, trace);
    } catch (const std::exception& e) { std::cerr << e.what() << '\n'; return 2; }
}
