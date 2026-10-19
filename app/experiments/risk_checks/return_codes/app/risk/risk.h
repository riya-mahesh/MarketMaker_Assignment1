// This file was generated with the help of Claude Code.
//
// EXPERIMENT FIX (return codes): app/risk/risk.h with the checks returning a result instead of
// throwing. The checks and their conditions are unchanged; a failed check is
// now an ordinary return value, so failing costs a compare and a branch rather
// than allocating and unwinding an exception. [[nodiscard]] keeps the original
// safety property: the compiler warns if a caller ignores a result.
//
// It lives at return_codes/app/risk/risk.h so that building with
// `-I app/experiments/risk_checks/return_codes` ahead of `-I .` picks up this version.
#pragma once

#include <cstdint>

#include "app/config.h"
#include "app/strategy/pricing.h"

namespace app {

enum class RiskCheck : std::uint8_t {
    Ok,
    BookInvalid,        // per tick: a side is empty or the book is crossed
    SequenceGap,        // standing, latched: a feed message was missed
    PositionLimit,      // per order: this side would exceed the position limit
    LossLimitBreached,  // standing, latched: detected on the timer
};

// The text the original exceptions carried; Halt() writes it to the decision log.
inline const char* Describe(RiskCheck check) {
    switch (check) {
        case RiskCheck::Ok:
            return "ok";
        case RiskCheck::BookInvalid:
            return "book side empty or crossed";
        case RiskCheck::SequenceGap:
            return "market data sequence gap";
        case RiskCheck::PositionLimit:
            return "position limit";
        case RiskCheck::LossLimitBreached:
            return "loss limit breached";
    }
    return "?";
}

class RiskGate {
public:
    void LatchSequenceGap() { sequence_gap_ = true; }
    void LatchLossLimit() { loss_limit_breached_ = true; }
    bool Halted() const { return sequence_gap_ || loss_limit_breached_; }

    // Standing conditions: once latched, nothing is quoted for the rest of the run.
    [[nodiscard]] RiskCheck CheckStanding() const {
        if (sequence_gap_) {
            return RiskCheck::SequenceGap;
        }
        if (loss_limit_breached_) {
            return RiskCheck::LossLimitBreached;
        }
        return RiskCheck::Ok;
    }

    // Also guards the division in CalcMicroprice.
    [[nodiscard]] static RiskCheck CheckBook(const BookTop& top) {
        return top.Valid() ? RiskCheck::Ok : RiskCheck::BookInvalid;
    }

    // A new or replacement quote of kQuoteShares on `side` must not be able to
    // take the position past the limit. With one order per side, the order
    // being replaced is superseded, so it isn't counted.
    [[nodiscard]] static RiskCheck CheckPosition(sim::Side side, std::int64_t position) {
        const bool breach = side == sim::Side::Buy ? position + kQuoteShares > kPositionLimit
                                                   : position - kQuoteShares < -kPositionLimit;
        return breach ? RiskCheck::PositionLimit : RiskCheck::Ok;
    }

private:
    bool sequence_gap_ = false;
    bool loss_limit_breached_ = false;
};

}  // namespace app
