#include "kinoko/sim/movement.hpp"
#include <iostream>
#include <sstream>
#include <string>
#include <stdexcept>

template<class T> void read(std::istream& in, T& value) {
    if (!(in >> value)) throw std::runtime_error("invalid movement input");
}
void read(std::istream& in, kinoko::sim::RawVector& v) {
    for (auto& value : v) read(in, value);
}
void print(const kinoko::sim::RawVector& v) {
    for (auto value : v) std::cout << ' ' << value;
}
void read(std::istream& in, kinoko::sim::DisplacementInput& input) {
    read(in, input.scalar); read(in, input.direction_68); read(in, input.direction_50);
    read(in, input.collision_mode_180); read(in, input.flags_44); read(in, input.field_380);
    read(in, input.field_374); read(in, input.field_260); read(in, input.field_274);
    read(in, input.field_268); read(in, input.field_2f0); read(in, input.field_1fc);
}
int main() {
    using namespace kinoko::sim;
    try {
        std::string line;
        while (std::getline(std::cin, line)) {
            std::istringstream in(line);
            char command; read(in, command);
            if (command == 'C' || command == 'F') {
                std::int32_t a, b; read(in, a); read(in, b);
                if (command == 'C') std::cout << "C " << approach_cap(a, b);
                else {
                    auto result = movement_fraction(a, b);
                    std::cout << "F " << result.fraction_2a0 << ' ' << result.magnitude_2a4;
                }
            } else if (command == 'G') {
                std::int32_t magnitude, cap; std::uint32_t flags; RawVector basis, normal, source;
                read(in, magnitude); read(in, cap); read(in, flags);
                read(in, basis); read(in, normal); read(in, source);
                const auto result = update_fraction_direction(magnitude, cap, flags, basis, normal, source);
                std::cout << "G " << result.ratio.fraction_2a0 << ' ' << result.ratio.magnitude_2a4;
                print(result.direction_278);
            } else if (command == 'H') {
                RawVector direction, target; std::uint32_t flags44, flags4c; std::int32_t factor;
                read(in, direction); read(in, target); read(in, flags44); read(in, flags4c); read(in, factor);
                std::cout << 'H'; print(blend_direction(direction, target, flags44, flags4c, factor));
            } else if (command == 'B') {
                CapTargetInput input;
                read(in, input.kart_max_speed); read(in, input.field_dc); read(in, input.field_d4);
                read(in, input.field_d8); read(in, input.field_4c4); read(in, input.flags_7c);
                read(in, input.flags_48); read(in, input.flags_4c);
                const auto result = resolve_cap_target(input);
                std::cout << "B " << result.target_cc << ' ' << result.field_dc;
            } else if (command == 'R') {
                std::int32_t scalar, field, coefficient; std::uint32_t mode, flags;
                read(in, scalar); read(in, mode); read(in, flags); read(in, field); read(in, coefficient);
                std::cout << "R " << apply_direction_penalty(scalar, mode, flags, field, coefficient);
            } else if (command == 'N') {
                RawVector delta, direction; std::int32_t scale;
                read(in, delta); read(in, direction); read(in, scale);
                auto result = normalize_movement(delta, direction, scale);
                std::cout << 'N'; print(result.displacement_a4); print(result.direction_b0);
                std::cout << ' ' << result.magnitude_2a4;
            } else if (command == 'D') {
                DisplacementInput input;
                read(in, input);
                auto result = assemble_displacement(input);
                std::cout << 'D'; print(result.displacement_a4); print(result.signed_direction_5c);
            } else if (command == 'T') {
                MovementTailInput input;
                read(in, input.assembly); read(in, input.position_80); read(in, input.previous_direction_b0);
                read(in, input.flags_7c); read(in, input.field_38c); read(in, input.scale_3f8);
                read(in, input.field_2b8); read(in, input.field_2bc); read(in, input.field_c8);
                read(in, input.global_scale_217ad0c); read(in, input.global_value_217ad10); read(in, input.field_4d4);
                const auto out = update_movement_tail(input);
                std::cout << 'T'; print(out.movement.displacement_a4); print(out.signed_direction_5c);
                print(out.movement.direction_b0); std::cout << ' ' << out.movement.magnitude_2a4;
                print(out.position.position_80); std::cout << ' ' << out.position.field_38c
                    << ' ' << out.flags_44 << ' ' << out.field_2b8 << ' ' << out.field_2bc
                    << ' ' << out.global_value_217ad10 << ' ' << out.field_4d4;
            } else if (command == 'P') {
                RawVector pos, delta; std::uint32_t flags; std::int32_t field;
                read(in, pos); read(in, delta); read(in, flags); read(in, field);
                auto result = add_displacement(pos, delta, flags, field);
                std::cout << 'P'; print(result.position_80); std::cout << ' ' << result.field_38c;
            } else throw std::runtime_error("unknown movement command");
            std::string extra;
            if (in >> extra) throw std::runtime_error("extra input");
            std::cout << '\n';
        }
    } catch (const std::exception& e) { std::cerr << e.what() << '\n'; return 2; }
}
