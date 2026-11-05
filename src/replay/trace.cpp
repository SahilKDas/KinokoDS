#include "kinoko/replay/trace.hpp"
#include <array>
#include <charconv>
#include <istream>
#include <ostream>
#include <stdexcept>
#include <string_view>

namespace kinoko {
namespace {
bool line(std::istream& in, std::string& s) {
    if (!std::getline(in, s)) return false;
    if (!s.empty() && s.back() == '\r') s.pop_back();
    return true;
}
template<class T> T number(std::string_view s) {
    T value{};
    const auto [end, error] = std::from_chars(s.data(), s.data() + s.size(), value);
    if (error != std::errc{} || end != s.data() + s.size())
        throw std::runtime_error("invalid trace integer");
    return value;
}
}
Trace read_trace(std::istream& in) {
    std::string s;
    if (!line(in, s) || s != "kinoko-trace-v1") throw std::runtime_error("unsupported trace version");
    if (!line(in, s) || !s.starts_with("profile=") || s.size() == 8)
        throw std::runtime_error("missing profile");
    Trace trace{s.substr(8), {}};
    if (!line(in, s) || s != "tick,accelerate,position_raw,speed_raw")
        throw std::runtime_error("invalid trace header");
    while (line(in, s)) {
        std::array<std::string_view, 4> fields;
        std::string_view rest = s;
        for (std::size_t i = 0; i < fields.size(); ++i) {
            const auto split = rest.find(',');
            if ((i < 3 && split == rest.npos) || (i == 3 && split != rest.npos))
                throw std::runtime_error("expected four trace columns");
            fields[i] = rest.substr(0, split);
            if (i < 3) rest.remove_prefix(split + 1);
        }
        const auto button = number<unsigned>(fields[1]);
        if (button > 1) throw std::runtime_error("accelerate must be 0 or 1");
        TraceRow row{number<std::uint64_t>(fields[0]), button != 0,
                     number<std::int64_t>(fields[2]), number<std::int32_t>(fields[3])};
        if (row.tick != trace.rows.size() + 1) throw std::runtime_error("ticks must be contiguous starting at 1");
        trace.rows.push_back(row);
    }
    if (in.bad()) throw std::runtime_error("trace read failed");
    if (trace.rows.empty()) throw std::runtime_error("empty trace");
    return trace;
}
void write_trace(std::ostream& out, const Trace& trace) {
    out << "kinoko-trace-v1\nprofile=" << trace.profile
        << "\ntick,accelerate,position_raw,speed_raw\n";
    for (const auto& r : trace.rows)
        out << r.tick << ',' << r.accelerate << ',' << r.position_raw << ',' << r.speed_raw << '\n';
    if (!out) throw std::runtime_error("trace write failed");
}
std::optional<std::string> first_difference(const Trace& a, const Trace& b) {
    if (a.profile != b.profile) return "profile mismatch: " + a.profile + " vs " + b.profile;
    const auto n = a.rows.size() < b.rows.size() ? a.rows.size() : b.rows.size();
    for (std::size_t i = 0; i < n; ++i) {
        const auto& x = a.rows[i]; const auto& y = b.rows[i];
        const auto mismatch = [&](const char* field, auto expected, auto actual) {
            return "tick " + std::to_string(x.tick) + " field " + field +
                ": expected " + std::to_string(expected) + ", actual " + std::to_string(actual);
        };
        if (x.tick != y.tick) return mismatch("tick", x.tick, y.tick);
        if (x.accelerate != y.accelerate) return mismatch("accelerate", x.accelerate, y.accelerate);
        if (x.position_raw != y.position_raw) return mismatch("position_raw", x.position_raw, y.position_raw);
        if (x.speed_raw != y.speed_raw) return mismatch("speed_raw", x.speed_raw, y.speed_raw);
    }
    if (a.rows.size() != b.rows.size()) return "trace length mismatch at tick " + std::to_string(n + 1);
    return std::nullopt;
}
}
