// This file was generated with the help of Claude Code.
//
// Corrected latency report: tick-to-trade per order.
//
// Tick-to-trade is defined per trade, as in the STAC-T1 benchmark: "the
// egress time of the trade message minus the ingress time of the market data
// message triggering the trade". Here both timestamps come from the capture
// tap: the order's Send time, and the entry time of the delivery that was
// being handled when it was sent.
//
// Unlike analysis.h, this iterates over orders rather than deliveries:
//   * a delivery that sends two orders yields two latencies, each ending at
//     its own Send, not one latency ending when the handler returns;
//   * a delivery that sends nothing (an ordinary timer tick, or a message that
//     leaves our quotes unchanged) yields none.
// Every order is a trading decision and is counted, whatever triggered it:
// market data, an execution report, or the timer (the loss-limit halt's
// cancels).
#pragma once

#include <algorithm>
#include <cmath>
#include <ostream>
#include <vector>

#include "sim/runtime/capture.h"

namespace app {

inline void PrintTickToTradeReport(const sim::Capture& capture, std::ostream& out) {
    std::vector<double> latencies;
    for (const sim::SendRecord& s : capture.sends) {
        if (s.delivery_index >= capture.deliveries.size()) {
            continue;  // only if a callback threw before its delivery was recorded
        }
        const sim::DeliveryRecord& d = capture.deliveries[s.delivery_index];
        latencies.push_back(static_cast<double>(s.time - d.entry));
    }

    out << "corrected tick-to-trade: " << latencies.size() << " orders";
    if (!latencies.empty()) {
        const double n = static_cast<double>(latencies.size());
        double total = 0;
        for (const double l : latencies) {
            total += l;
        }
        const double mean = total / n;
        double squares = 0;
        for (const double l : latencies) {
            squares += (l - mean) * (l - mean);
        }
        // Sample standard deviation (n - 1); 0 for a single order.
        const double stddev = latencies.size() > 1 ? std::sqrt(squares / (n - 1)) : 0.0;
        std::sort(latencies.begin(), latencies.end());
        const std::size_t mid = latencies.size() / 2;
        const double median = latencies.size() % 2 == 1
                                  ? latencies[mid]
                                  : (latencies[mid - 1] + latencies[mid]) / 2;
        out << ", mean " << mean << " ns, median " << median << " ns, std dev " << stddev << " ns";
    }
    out << '\n';
}

}  // namespace app
