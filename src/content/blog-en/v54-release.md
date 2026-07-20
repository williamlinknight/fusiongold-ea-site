---
title: "FusionGold M5 v54: Official Release Announcement"
pubDate: 2026-07-17
description: "v54 is here with ADX overheat block, loss streak filter, recovery mode, and more."
author: "William"
tags: ["Release", "Update"]
---

## What's New in v54

FusionGold M5 v54 has been officially released. Here are the key updates.

### ADX Overheat Block (ADX_MaxBlock = 45)

When ADX exceeds 45, the EA automatically blocks new orders, identifying the trend as exhausted. This reduces the risk of buying at the top after an overheated market move.

### Loss Streak Filter (3 consecutive losses → 60min pause)

If three consecutive losses occur in the same direction, trading in that direction is paused for 60 minutes. Prevents emotional revenge trading.

### Recovery Mode (HALTED)

If the previous day's loss exceeds 5%, the first 3 trades of the next day automatically have their risk halved. Supports risk management after significant losses.

### H4 Direction Filter Improvements

Buy/sell direction filtering is now based on H4 EMA consistency. The consensus threshold (H4_EMA_ConsensusMin) is configurable, allowing more flexible direction determination.

## Performance

Backtest results (June 1 – July 2, 2026):

| Metric | Value |
|:-------|:------|
| Total Trades | 145 |
| Win Rate | 74.48% |
| Net Profit | +$912.56 |
| PF | 1.54 |
| Max DD | 8.61% |

SELL trades showed strong stability with a 79.31% win rate.

## How to Get It

This EA is available exclusively through barter (物々交換). If you're interested in trading for Japanese products, please contact us from the inquiry page.
