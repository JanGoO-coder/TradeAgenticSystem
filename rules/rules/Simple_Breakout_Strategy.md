# Simple Breakout Strategy

## 1. Strategy Overview

A minimal breakout strategy based on 5-minute candle structure.

### 1.1 Previous Candle Breakout Rule

**What**: Trade breakouts of the previous 5-minute candle's high or low.

**Logic**:
- If the current 5-minute candle breaks the **previous candle's high** → **Go SHORT**
- If the current 5-minute candle breaks the **previous candle's low** → **Go LONG**

**Why**: This is a counter-trend fading strategy. Breaking the previous candle's high often indicates exhaustion and potential reversal. Breaking the previous candle's low indicates bearish exhaustion and potential bullish reversal.

**Timeframe**: 5-minute chart only.

**When Valid**:
- Clear break (close beyond the level, not just a wick)
- During active trading sessions (London, New York)

**When Invalid**:
- During low volatility periods (Asian session lows)
- During major news events
- When price is in a strong trend (multiple consecutive breaks in same direction)

### 1.2 Entry Conditions

**Short Entry**:
1. Wait for 5-minute candle to close
2. Current candle close is above previous candle high
3. Enter SHORT at market or on pullback to previous high

**Long Entry**:
1. Wait for 5-minute candle to close
2. Current candle close is below previous candle low
3. Enter LONG at market or on pullback to previous low

### 1.3 Exit Conditions

**Stop Loss**:
- For shorts: Above the breakout candle high
- For longs: Below the breakout candle low

**Take Profit**:
- 1:1 risk-reward ratio minimum
- Or trail stop using subsequent candle structure
