// This file was generated with the help of Claude Code.
//
// EXPERIMENT BASELINE: the app's Book (app/market_data/book.h) with the cached
// top of book removed. Identical except:
//   * there is no top_ member and no RecomputeBest;
//   * top() searches the price ladders on every call (see book.cpp).
//
// It lives at full_scan/app/market_data/book.h so that building with
// `-I app/experiments/top_of_book/full_scan` ahead of `-I .` makes every
// `#include "app/market_data/book.h"` in the app pick up this version.
#pragma once

#include <cstdint>
#include <vector>

#include "app/strategy/pricing.h"
#include "sim/messages/market_data.h"

namespace app {

class Book {
public:
    Book();

    void Apply(const sim::md::AddOrder& msg);
    void Apply(const sim::md::OrderExecuted& msg);
    void Apply(const sim::md::OrderCancel& msg);
    void Apply(const sim::md::OrderDelete& msg);
    void Apply(const sim::md::OrderReplace& msg);

    void MarkOwn(sim::OrderRef ref);

    // No cache: finds the best bid and ask by scanning the ladders.
    BookTop top() const;

private:
    struct Order {
        sim::Price price = 0;
        std::uint32_t shares = 0;
        sim::Side side = sim::Side::Buy;
        bool live = false;
        bool own = false;
    };

    struct Ladder {
        std::vector<std::uint64_t> shares_at_tick;  // indexed by price / kTickSize
        std::uint64_t order_count = 0;              // live market (non-own) orders
    };

    Order& Lookup(sim::OrderRef ref);
    void Reduce(sim::OrderRef ref, std::uint32_t shares);
    void AddLiquidity(const Order& order);
    void RemoveLiquidity(const Order& order, std::uint32_t shares, bool order_gone);

    std::vector<Order> orders_;
    Ladder bids_;
    Ladder asks_;
};

}  // namespace app
