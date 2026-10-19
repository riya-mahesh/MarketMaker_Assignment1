// This file was generated with the help of Claude Code.
//
// EXPERIMENT FIX (Cook's "slowpath removal", CppCon 2017 slide 16): app/risk/risk.h with the
// four checks returning one word of flags instead of throwing.

//
// Pre-trade risk checks.
//
// Safety first: a quote must never go out if anything is wrong, so every
// check throws on failure. An exception can't be ignored the way a return
// code can, and it unwinds straight out of the quoting code, so no path can
// accidentally carry on and send an order after a failed check. Exceptions
// are zero-cost when not thrown, so the checks cost nothing on the normal
// path.
#pragma once

#include <cstdint>

#include "app/config.h"
#include "app/strategy/pricing.h"

namespace app {

// Every risk condition is one bit of a single word, so the quoting path tests
// all of them with one branch (Cook: "if (!errorFlags) sendOrderToExchange();
// else HandleError(errorFlags);").
enum RiskFlag : std::uint32_t {
    kRiskSequenceGap = 1u << 0,   // standing, latched: a feed message was missed
    kRiskLossLimit = 1u << 1,     // standing, latched: detected on the timer
    kRiskBookInvalid = 1u << 2,   // per tick: a side is empty or the book is crossed
    kRiskBuyBlocked = 1u << 3,    // per order: a new buy could exceed the position limit
    kRiskSellBlocked = 1u << 4,   // per order: a new sell could exceed the position limit
};
inline constexpr std::uint32_t kRiskStanding = kRiskSequenceGap | kRiskLossLimit;

class RiskGate {
public:
    void LatchSequenceGap() { sequence_gap_ = true; }
    void LatchLossLimit() { loss_limit_breached_ = true; }
    bool Halted() const { return sequence_gap_ || loss_limit_breached_; }

    // All four checks at once, with the same conditions as the original. A new
    // or replacement quote of kQuoteShares on a side must not be able to take
    // the position past the limit; the order being replaced isn't counted.
    [[nodiscard]] std::uint32_t Flags(const BookTop& top, std::int64_t position) const {
        std::uint32_t flags = 0;
        flags |= sequence_gap_ ? kRiskSequenceGap : 0u;
        flags |= loss_limit_breached_ ? kRiskLossLimit : 0u;
        flags |= top.Valid() ? 0u : kRiskBookInvalid;
        flags |= position + kQuoteShares > kPositionLimit ? kRiskBuyBlocked : 0u;
        flags |= position - kQuoteShares < -kPositionLimit ? kRiskSellBlocked : 0u;
        return flags;
    }

private:
    bool sequence_gap_ = false;
    bool loss_limit_breached_ = false;
};

}  // namespace app
