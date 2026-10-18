// This file was generated with the help of Claude Code.
//
// EXPERIMENT BASELINE: app/market_data/book.cpp with the cached top of book
// removed. AddLiquidity and RemoveLiquidity only update the ladders, and top()
// scans them on every call: bids from the highest price in the ladder down,
// asks from the lowest price up, each stopping at the first non-empty level.
// Everything else is unchanged.

#include "app/market_data/book.h"

#include <stdexcept>

namespace app {

namespace {

constexpr std::size_t kLadderSize = kMaxPrice / sim::kTickSize;

std::size_t TickIndex(sim::Price price) {
    return static_cast<std::size_t>(price / sim::kTickSize);
}

}  // namespace

Book::Book() : orders_(kMaxOrderRefs) {
    bids_.shares_at_tick.assign(kLadderSize, 0);
    asks_.shares_at_tick.assign(kLadderSize, 0);
}

Book::Order& Book::Lookup(sim::OrderRef ref) {
    if (ref >= orders_.size()) {
        throw std::out_of_range("app::Book: order ref exceeds kMaxOrderRefs");
    }
    return orders_[ref];
}

void Book::Apply(const sim::md::AddOrder& msg) {
    if (msg.price <= 0 || msg.price >= kMaxPrice) {
        throw std::out_of_range("app::Book: price outside the ladder");
    }
    Order& order = Lookup(msg.order_ref);
    order.price = msg.price;
    order.shares = msg.shares;
    order.side = msg.side;
    order.live = true;
    // `own` may already be set if our Accepted arrived before this Add.
    if (!order.own) {
        AddLiquidity(order);
    }
}

void Book::Apply(const sim::md::OrderExecuted& msg) { Reduce(msg.order_ref, msg.executed_shares); }

void Book::Apply(const sim::md::OrderCancel& msg) { Reduce(msg.order_ref, msg.canceled_shares); }

void Book::Apply(const sim::md::OrderDelete& msg) {
    Reduce(msg.order_ref, Lookup(msg.order_ref).shares);
}

void Book::Apply(const sim::md::OrderReplace& msg) {
    const Order& original = Lookup(msg.original_order_ref);
    const sim::Side side = original.side;
    // A replacement of one of our orders is ours, known now rather than when
    // the Replaced report arrives.
    if (original.own) {
        Lookup(msg.new_order_ref).own = true;
    }
    Reduce(msg.original_order_ref, original.shares);

    sim::md::AddOrder add{};
    add.order_ref = msg.new_order_ref;
    add.side = side;
    add.shares = msg.shares;
    add.price = msg.price;
    Apply(add);
}

void Book::MarkOwn(sim::OrderRef ref) {
    Order& order = Lookup(ref);
    if (order.own) {
        return;
    }
    if (order.live) {
        RemoveLiquidity(order, order.shares, true);
    }
    order.own = true;
}

void Book::Reduce(sim::OrderRef ref, std::uint32_t shares) {
    Order& order = Lookup(ref);
    if (!order.live) {
        return;
    }
    const bool gone = shares >= order.shares;
    if (!order.own) {
        RemoveLiquidity(order, gone ? order.shares : shares, gone);
    }
    if (gone) {
        order.shares = 0;
        order.live = false;
    } else {
        order.shares -= shares;
    }
}

void Book::AddLiquidity(const Order& order) {
    Ladder& ladder = order.side == sim::Side::Buy ? bids_ : asks_;
    ladder.shares_at_tick[TickIndex(order.price)] += order.shares;
    ++ladder.order_count;
}

void Book::RemoveLiquidity(const Order& order, std::uint32_t shares, bool order_gone) {
    Ladder& ladder = order.side == sim::Side::Buy ? bids_ : asks_;
    ladder.shares_at_tick[TickIndex(order.price)] -= shares;
    if (order_gone) {
        --ladder.order_count;
    }
}

BookTop Book::top() const {
    BookTop top;
    if (bids_.order_count > 0) {
        for (std::size_t i = kLadderSize - 1;; --i) {
            if (bids_.shares_at_tick[i] != 0) {
                top.bid_price = static_cast<sim::Price>(i) * sim::kTickSize;
                top.bid_size = bids_.shares_at_tick[i];
                break;
            }
        }
    }
    if (asks_.order_count > 0) {
        for (std::size_t i = 0;; ++i) {
            if (asks_.shares_at_tick[i] != 0) {
                top.ask_price = static_cast<sim::Price>(i) * sim::kTickSize;
                top.ask_size = asks_.shares_at_tick[i];
                break;
            }
        }
    }
    return top;
}

}  // namespace app
