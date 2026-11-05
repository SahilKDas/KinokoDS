#pragma once
#include <bit>
#include <cstdint>
#include <limits>

namespace kinoko::math {
inline std::int32_t wrap(std::uint32_t x) { return std::bit_cast<std::int32_t>(x); }
inline std::int32_t add(std::int32_t a, std::int32_t b) { return wrap(static_cast<std::uint32_t>(a) + static_cast<std::uint32_t>(b)); }
inline std::int32_t sub(std::int32_t a, std::int32_t b) { return wrap(static_cast<std::uint32_t>(a) - static_cast<std::uint32_t>(b)); }
inline std::int32_t fx_mul(std::int32_t a, std::int32_t b, bool round = false) {
    const auto product = static_cast<std::int64_t>(a) * b + (round ? 2048 : 0);
    return wrap(static_cast<std::uint32_t>(static_cast<std::uint64_t>(product) >> 12));
}
// Nitro FX_Div: signed hardware (numerator * 2^32)/denominator, followed
// by +0x80000 and extraction of bits [20..51]. Division truncates toward zero.
inline std::int32_t fx_div(std::int32_t a, std::int32_t b) {
    const auto numerator = static_cast<std::int64_t>(a) * 4294967296LL;
    std::int64_t quotient;
    if (!b) quotient = numerator < 0 ? 1 : -1;
    else if (numerator == std::numeric_limits<std::int64_t>::min() && b == -1) quotient = numerator;
    else quotient = numerator / b;
    const auto bits = static_cast<std::uint64_t>(quotient) + 0x80000ULL;
    return wrap(static_cast<std::uint32_t>(bits >> 20));
}
}
