#pragma once
#include <cstdint>
#include <iosfwd>
#include <optional>
#include <string>
#include <vector>

namespace kinoko {
// v1 is deliberately a flat-ground, longitudinal trace, not a full snapshot.
struct TraceRow {
    std::uint64_t tick;
    bool accelerate;
    std::int64_t position_raw;
    std::int32_t speed_raw;
};
struct Trace {
    std::string profile;
    std::vector<TraceRow> rows;
};
Trace read_trace(std::istream& input);
void write_trace(std::ostream& output, const Trace& trace);
// Exact integer comparison; empty means all captured fields match.
std::optional<std::string> first_difference(const Trace& expected, const Trace& actual);
}
