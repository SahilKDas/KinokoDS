#include "kinoko/sim/movement.hpp"
#include "kinoko/math/fixed.hpp"

namespace kinoko::sim {
namespace {
std::uint64_t square_sum(RawVector v) {
    std::uint64_t sum = 0;
    for (auto component : v) sum += static_cast<std::uint64_t>(static_cast<std::int64_t>(component) * component);
    return sum;
}
// Integer square root with a division comparison to avoid squaring overflow.
std::uint32_t isqrt(std::uint64_t value) {
    std::uint64_t lo = 0, hi = 0x100000000ULL;
    while (lo + 1 < hi) {
        auto mid = (lo + hi) / 2;
        if (mid <= value / mid) lo = mid;
        else hi = mid;
    }
    return static_cast<std::uint32_t>(lo);
}
}
NormalizedMovement normalize_movement(RawVector displacement, RawVector direction, std::int32_t scale) {
    for (auto& component : displacement) component = math::fx_mul(component, scale);
    const auto squared = square_sum(displacement);
    std::int32_t magnitude = 0;
    // SMLAL accumulation wraps at 64 bits; signed comparison is intentional.
    if (std::bit_cast<std::int64_t>(squared) >= 16) {
        const auto root = isqrt(squared << 2);
        const auto quotient = 0x0100000000000000ULL / squared;
        const auto factor = quotient * static_cast<std::uint64_t>(static_cast<std::int64_t>(math::wrap(root)));
        for (unsigned i = 0; i < 3; ++i) {
            const auto product = factor * static_cast<std::uint64_t>(static_cast<std::int64_t>(displacement[i]));
            const auto high = static_cast<std::uint32_t>(product >> 32) + 0x1000U;
            direction[i] = math::wrap(high) >> 13;
        }
        magnitude = math::wrap(root + 1U) >> 1;
    }
    if (magnitude > 0xd000) {
        magnitude = 0xd000;
        for (unsigned i = 0; i < 3; ++i) displacement[i] = math::fx_mul(direction[i], magnitude);
    }
    return {displacement, direction, magnitude};
}
std::int32_t approach_cap(std::int32_t current, std::int32_t target) {
    // Literal at 0x01FFBE6C is 0xF37; signed truncating Q12 multiply.
    if (current <= target) return target;
    const auto decayed = math::fx_mul(current, 0xf37);
    return decayed < target ? target : decayed;
}
CapTargetOutput resolve_cap_target(const CapTargetInput& in) {
    auto field = in.field_dc;
    auto target = math::fx_mul(math::fx_mul(in.kart_max_speed, field), math::fx_mul(in.field_d4, in.field_d8));
    if (in.flags_7c & 0x402000) { target = in.kart_max_speed; field = 4096; }
    if (in.flags_48 & 0x10000000) { target = in.field_4c4; field = 4096; }
    if (in.flags_48 & 0x20) {
        if ((in.flags_4c & 0x10000040) || (in.flags_48 & 0x20000000)) {
            target = in.kart_max_speed; field = 4096;
        }
        target = math::fx_mul(target, 0x14cd);
        if ((in.flags_48 & 0x400001) && target < 0x8800) { target = 0x8800; field = 4096; }
    } else if (in.flags_4c & 0x10000040) {
        target = math::fx_mul(in.kart_max_speed, 0x1333); field = 4096;
    }
    return {target, field};
}
std::int32_t apply_direction_penalty(std::int32_t scalar, std::uint32_t mode,
    std::uint32_t flags, std::int32_t field, std::int32_t coefficient) {
    if (mode != 0 || (flags & 8) || !(flags & 16) || scalar <= 0x3000) return scalar;
    const auto absolute = field > 0 ? field : math::sub(0, field);
    return math::sub(scalar, math::fx_mul(math::fx_mul(scalar, coefficient), absolute));
}
MovementFraction movement_fraction(std::int32_t magnitude, std::int32_t cap) {
    const auto fraction = math::fx_div(magnitude, cap);
    return fraction > 4096 ? MovementFraction{4096, cap}
                           : MovementFraction{fraction, magnitude};
}
FractionDirectionOutput update_fraction_direction(std::int32_t magnitude, std::int32_t cap,
    std::uint32_t flags, RawVector basis, RawVector normal, RawVector source) {
    auto direction = source;
    if (flags & 16) {
        for (unsigned i = 0; i < 3; ++i) {
            const auto j = (i + 1) % 3, k = (i + 2) % 3;
            const auto a = static_cast<std::uint64_t>(static_cast<std::int64_t>(basis[j]) * normal[k]);
            const auto b = static_cast<std::uint64_t>(static_cast<std::int64_t>(basis[k]) * normal[j]);
            direction[i] = math::wrap(static_cast<std::uint32_t>((a - b) >> 12));
        }
    }
    return {movement_fraction(magnitude, cap), direction};
}
RawVector blend_direction(RawVector direction, RawVector target, std::uint32_t flags44,
    std::uint32_t flags4c, std::int32_t factor) {
    if ((flags44 & 0x90) || (flags4c & 0x10000000)) {
        for (unsigned i = 0; i < 3; ++i)
            direction[i] = math::add(direction[i], math::fx_mul(math::sub(target[i], direction[i]), factor));
        direction[1] = target[1];
    }
    return direction;
}
DisplacementOutput assemble_displacement(const DisplacementInput& in) {
    DisplacementOutput out;
    for (unsigned i = 0; i < 3; ++i) {
        out.displacement_a4[i] = math::fx_mul(in.direction_68[i], in.scalar);
        out.signed_direction_5c[i] = in.scalar >= 0 ? in.direction_50[i]
                                                  : math::sub(0, in.direction_50[i]);
    }
    if (in.collision_mode_180 == 6) out.displacement_a4[1] = 0;
    for (unsigned i = 0; i < 3; ++i) {
        auto value = math::add(out.displacement_a4[i], in.field_374[i]);
        if (i == 1) value = math::add(value, in.field_260);
        out.displacement_a4[i] = math::add(value, math::fx_mul(in.field_274, in.field_268[i]));
    }
    if (!(in.flags_44 & 0x10) && in.field_380 > 5 && out.displacement_a4[1] < -0x6000)
        out.displacement_a4[1] = -0x6000;
    for (unsigned i = 0; i < 3; ++i) {
        out.displacement_a4[i] = math::add(out.displacement_a4[i], in.field_2f0[i]);
        out.displacement_a4[i] = math::add(out.displacement_a4[i], in.field_1fc[i]);
    }
    return out;
}
PositionOutput add_displacement(RawVector position, RawVector displacement,
    std::uint32_t flags, std::int32_t field) {
    if (!(flags & 0x20)) {
        for (unsigned i = 0; i < 3; ++i) position[i] = math::add(position[i], displacement[i]);
        field = 4096;
    }
    return {position, field};
}
MovementTailOutput update_movement_tail(const MovementTailInput& input) {
    const auto assembled = assemble_displacement(input.assembly);
    auto flags = input.assembly.flags_44;
    auto a = input.field_2b8, b = input.field_2bc;
    if (flags & 4) {
        a = math::add(a, input.field_c8);
        b = math::add(b, a);
        if (b < 0) {
            a = b = 0;
            flags &= 0xfffff7fbU;
        }
    }
    const auto movement = normalize_movement(assembled.displacement_a4, input.previous_direction_b0, input.scale_3f8);
    auto global = input.global_value_217ad10;
    auto field4d4 = input.field_4d4;
    if (input.flags_7c & 1) {
        std::uint64_t dot = 0;
        for (unsigned i = 0; i < 3; ++i)
            dot += static_cast<std::uint64_t>(static_cast<std::int64_t>(movement.displacement_a4[i]) * input.assembly.direction_50[i]);
        const auto projected = math::wrap(static_cast<std::uint32_t>(dot >> 12));
        global = math::fx_mul(projected, input.global_scale_217ad0c, true);
        if ((flags & 0x1000000) && field4d4 != 0) {
            field4d4 = math::fx_mul(field4d4, 0xfae);
            if (field4d4 < 0xcd) field4d4 = 0;
        }
    }
    return {movement, assembled.signed_direction_5c,
        add_displacement(input.position_80, movement.displacement_a4, input.flags_7c, input.field_38c), flags, a, b, global, field4d4};
}
}
