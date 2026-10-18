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

#include <cstdint>
#include <ostream>

#include "sim/runtime/capture.h"

namespace app {

inline void PrintTickToTradeReport(const sim::Capture& capture, std::ostream& out) {
    double total_ns = 0;
    std::uint64_t count = 0;
    for (const sim::SendRecord& s : capture.sends) {
        if (s.delivery_index >= capture.deliveries.size()) {
            continue;  // only if a callback threw before its delivery was recorded
        }
        const sim::DeliveryRecord& d = capture.deliveries[s.delivery_index];
        total_ns += static_cast<double>(s.time - d.entry);
        ++count;
    }

    out << "corrected tick-to-trade: " << count << " orders, mean "
        << (count > 0 ? total_ns / static_cast<double>(count) : 0.0) << " ns\n";
}

}  // namespace app
