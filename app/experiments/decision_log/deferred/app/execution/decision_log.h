// This file was generated with the help of Claude Code.
//
// EXPERIMENT FIX: app/execution/decision_log.h with the text formatting moved off the hot
// path. Every order is still recorded *before* it is sent, but Record() only appends a small
// fixed-size binary record to a buffer reserved at startup: a few stores, no formatting and
// no stdio. The records are formatted into exactly the same text, in the same order, when
// the log is closed at the end of the run, so decisions.log is byte-for-byte unchanged.
//
// It lives at deferred/app/execution/decision_log.h so that building with
// `-I app/experiments/decision_log/deferred` ahead of `-I .` picks up this version.
#pragma once

#include <cstdint>
#include <cstdio>
#include <stdexcept>
#include <string>
#include <vector>

#include "sim/messages/types.h"

namespace app {

class DecisionLog {
public:
    explicit DecisionLog(const std::string& path) : file_(std::fopen(path.c_str(), "w")) {
        if (file_ == nullptr) {
            throw std::runtime_error("DecisionLog: cannot open " + path);
        }
        entries_.reserve(kCapacity);
    }
    ~DecisionLog() {
        for (const Entry& e : entries_) {
            if (e.note == kNoNote) {
                std::fprintf(file_, "%llu %s %c %lld.%04lld x %u token=%llu\n",
                             static_cast<unsigned long long>(e.now), e.action, e.side,
                             static_cast<long long>(e.price / sim::kPriceScale),
                             static_cast<long long>(e.price % sim::kPriceScale), e.shares,
                             static_cast<unsigned long long>(e.token));
            } else {
                std::fprintf(file_, "%llu %s\n", static_cast<unsigned long long>(e.now),
                             notes_[e.note].c_str());
            }
        }
        std::fclose(file_);
    }
    DecisionLog(const DecisionLog&) = delete;
    DecisionLog& operator=(const DecisionLog&) = delete;

    // Hot path: one binary record, no formatting. `action` is always a string literal.
    void Record(sim::Timestamp now, const char* action, sim::Side side, sim::Price price,
                std::uint32_t shares, sim::Token token) {
        entries_.push_back({now, price, token, action, shares, static_cast<char>(side), kNoNote});
    }

    // Rare (halt, reconcile): the text is copied, since it may not outlive the call.
    void Note(sim::Timestamp now, const char* text) {
        notes_.emplace_back(text);
        entries_.push_back({now, 0, 0, nullptr, 0, 0, static_cast<std::uint32_t>(notes_.size() - 1)});
    }

private:
    static constexpr std::size_t kCapacity = 1 << 16;
    static constexpr std::uint32_t kNoNote = UINT32_MAX;

    struct Entry {
        sim::Timestamp now;
        sim::Price price;
        sim::Token token;
        const char* action;
        std::uint32_t shares;
        char side;
        std::uint32_t note;  // index into notes_, or kNoNote for an order record
    };

    std::FILE* file_;
    std::vector<Entry> entries_;
    std::vector<std::string> notes_;
};

}  // namespace app
