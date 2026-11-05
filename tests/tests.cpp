#include "kinoko/replay/trace.hpp"
#include "kinoko/sim/world.hpp"
#include <iostream>
#include <sstream>
#include <stdexcept>

void require(bool condition) { if (!condition) throw std::runtime_error("test failed"); }
int main() {
    try {
        kinoko::WorldState state;
        kinoko::step(state, {}, {true});
        const auto saved = state;
        kinoko::step(state, {}, {true});
        auto restored = saved;
        kinoko::step(restored, {}, {true});
        require(state == restored && state.position == 9 && state.speed == 6);
        kinoko::Trace a{"synthetic-accel-v1", {{1, true, 3, 3}, {2, true, 9, 6}}};
        std::stringstream stream;
        kinoko::write_trace(stream, a);
        auto b = kinoko::read_trace(stream);
        require(!kinoko::first_difference(a, b));
        b.rows[1].speed_raw = 7;
        require(kinoko::first_difference(a, b) == "tick 2 field speed_raw: expected 6, actual 7");
        b = a; b.rows.pop_back(); require(kinoko::first_difference(a, b).has_value());
        b = a; b.profile = "other"; require(kinoko::first_difference(a, b).has_value());
        for (const auto* row : {"1,2,3,3", "2,1,3,3", "1,1,3x,3", "1,1,3,3,5", "1,1,3,999999999999"}) {
            std::stringstream bad;
            bad << "kinoko-trace-v1\nprofile=test\ntick,accelerate,position_raw,speed_raw\n" << row << '\n';
            bool rejected = false;
            try { (void)kinoko::read_trace(bad); } catch (const std::runtime_error&) { rejected = true; }
            require(rejected);
        }
        std::cout << "all checks passed\n";
    } catch (const std::exception& e) { std::cerr << e.what() << '\n'; return 1; }
}
