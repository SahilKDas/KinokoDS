#include "kinoko/sim/longitudinal.hpp"
#include "kinoko/assets/preparation.hpp"
#include "kinoko/math/fixed.hpp"
#include <iostream>
#include <stdexcept>

void require(bool x) { if (!x) throw std::runtime_error("longitudinal test failed"); }
int main() {
    using namespace kinoko;
    try {
        assets::KartParameters p{};
        p.collision_sphere_size = 32768; p.max_speed = 30720;
        p.drift = 220; p.base_acceleration = 237; p.unknown_18 = 98;
        p.unknown_1c = 2867; p.deceleration = 4030;
        p.collision_speed_multipliers.fill(4096);
        const std::array karts{p}; const std::array chars{assets::CharacterParameters{3891, 2048}};
        const auto original = p;
        const auto prepared = assets::prepare_parameters(karts, chars, 0, 0, {});
        require(prepared.kart == original && karts[0] == original);
        const auto slow = assets::prepare_parameters(karts, chars, 0, 0, {assets::ParameterScene::race, 0});
        require(slow.kart.max_speed == math::fx_mul(30720, 0xb33) && slow.kart.drift == 180);
        require(sim::update_longitudinal({}, p, {true, 0}, 30720).speed_raw == 237);
        require(sim::update_longitudinal({30720, false}, p, {true, 4096}, 30720).speed_raw == 30720);
        require(sim::update_longitudinal({410, false}, p, {false, 0}, 30720) == sim::LongitudinalState{0, true});
        bool rejected = false;
        try { (void)sim::update_longitudinal({}, p, {true, 0, false}, 30720); }
        catch (const std::invalid_argument&) { rejected = true; }
        require(rejected);
        for (auto conditions : {sim::LongitudinalInput{true, 0, true, true, false},
                                sim::LongitudinalInput{true, 0, true, false, true}}) {
            rejected = false;
            try { (void)sim::update_longitudinal({}, p, conditions, 30720); }
            catch (const std::invalid_argument&) { rejected = true; }
            require(rejected);
        }
        require(math::fx_div(1, 3) == 1365 && math::fx_div(-1, 3) == -1365);
        require(math::fx_mul(-1, 2048) == -1 && math::fx_mul(-1, 2048, true) == 0);
        require(math::add(2147483647, 1) == (-2147483647 - 1));
        p.unknown_1c = 1843; // Several real kart records have a switch below 0x800.
        require(sim::update_longitudinal({}, p, {true, 0}, 30720).speed_raw == 237);
        require(sim::update_longitudinal({}, p, {true, 2048}, 30720).speed_raw == 98);
        p.unknown_1c = 2048; // Equality reaches the hardware zero-divisor behavior.
        require(sim::update_longitudinal({}, p, {true, 2048}, 30720).speed_raw == 237);
        std::cout << "initialization/longitudinal checks passed\n";
    } catch (const std::exception& e) { std::cerr << e.what() << '\n'; return 1; }
}
