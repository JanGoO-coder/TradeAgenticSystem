# ICT 2022 Model Strategy

## Overview
The ICT 2022 Model is a complete trade framework based on:
1. **Liquidity Sweep** (stop hunt)
2. **Market Structure Shift** (MSS/displacement)
3. **Entry on Fair Value Gap** (FVG)

This model identifies high-probability reversal points where retail traders get stopped out before the real move begins.

---

## Trading Sessions
- **Primary:** New York Kill Zone (7:00 AM - 10:00 AM EST)
- **Secondary:** London Kill Zone (2:00 AM - 5:00 AM EST)
- **NOT ALLOWED:** Asian session, off-hours, weekends

---

## Bias Determination

Use the **1-Hour (1H) timeframe** to establish directional bias:

### Bullish Bias
- Look for Higher Highs (HH) and Higher Lows (HL)
- The most recent swing low should be higher than the previous swing low
- The most recent swing high should be higher than the previous swing high

### Bearish Bias
- Look for Lower Highs (LH) and Lower Lows (LL)
- The most recent swing high should be lower than the previous swing high
- The most recent swing low should be lower than the previous swing low

### Neutral (No Trade)
- Mixed structure (e.g., higher high with lower low)
- Insufficient swing points to determine structure
- Ranging/consolidating market

---

## Entry Criteria

### For BULLISH Trades (Long)

1. **Establish Bullish Bias**
   - 1H structure shows HH/HL pattern

2. **Liquidity Sweep**
   - Price must sweep BELOW a recent swing low (sell-side liquidity)
   - This takes out retail stop losses
   
3. **Rejection**
   - Price must close back ABOVE the swept level
   - The candle should show a wick below and close bullish

4. **FVG Present**
   - A Bullish Fair Value Gap must form after the sweep
   - The gap should be on the 15M or 5M timeframe

5. **Entry**
   - Enter long at the TOP of the bullish FVG (most conservative)
   - Or enter at the 50% midpoint of the FVG

6. **Stop Loss**
   - Place stop below the sweep low
   - Add 5 pips (0.0005 for pairs) buffer

7. **Take Profit**
   - Minimum 1:2 Risk/Reward ratio
   - Target previous swing high
   - Or -27% Fibonacci extension

---

### For BEARISH Trades (Short)

1. **Establish Bearish Bias**
   - 1H structure shows LH/LL pattern

2. **Liquidity Sweep**
   - Price must sweep ABOVE a recent swing high (buy-side liquidity)
   - This takes out retail stop losses

3. **Rejection**
   - Price must close back BELOW the swept level
   - The candle should show a wick above and close bearish

4. **FVG Present**
   - A Bearish Fair Value Gap must form after the sweep
   - The gap should be on the 15M or 5M timeframe

5. **Entry**
   - Enter short at the BOTTOM of the bearish FVG (most conservative)
   - Or enter at the 50% midpoint of the FVG

6. **Stop Loss**
   - Place stop above the sweep high
   - Add 5 pips buffer

7. **Take Profit**
   - Minimum 1:2 Risk/Reward ratio
   - Target previous swing low
   - Or -27% Fibonacci extension

---

## Filters (Conditions that BLOCK a trade)

Do NOT take a trade if ANY of the following apply:

1. **Wrong Session**
   - We are outside of London KZ or NY KZ
   - Asian session is active
   - Weekend (Saturday/Sunday)

2. **News Interference**
   - High-impact news within 30 minutes
   - FOMC, NFP, CPI or similar announcements pending

3. **Structure Unclear**
   - 1H does not show clear HH/HL or LH/LL
   - Market is ranging/consolidating

4. **Missing Key Elements**
   - No liquidity sweep detected
   - No FVG present after the sweep

5. **Unfavorable Price Position**
   - For longs: Price already in premium (upper 50% of range)
   - For shorts: Price already in discount (lower 50% of range)

---

## Confidence Scoring

| Condition | Confidence Level |
|-----------|------------------|
| Sweep + FVG + NY Kill Zone | 90% |
| Sweep + FVG + London Kill Zone | 85% |
| Sweep + FVG + Wrong Session | 40% (WAIT) |
| Missing Sweep or FVG | 20% (WAIT) |
| Unclear Structure | 0% (WAIT) |

---

## Example Decision Flow

```
IF session is NY Kill Zone or London Kill Zone:
    IF 1H shows clear HH/HL:
        IF sell-side sweep detected:
            IF bullish FVG present:
                → ACTION: TRADE (Long)
                → Entry: Top of FVG
                → SL: Below sweep low
                → TP: Previous swing high
            ELSE:
                → ACTION: MONITOR (waiting for FVG)
        ELSE:
            → ACTION: WAIT (no sweep yet)
    ELSE:
        → ACTION: WAIT (unclear structure)
ELSE:
    → ACTION: WAIT (wrong session)
```

---

## Key Reminders

1. **Patience is Key**: Wait for ALL conditions to align
2. **Session Matters**: The best setups occur during high-volume sessions
3. **Sweep Confirmation**: Price must close back beyond the swept level
4. **FVG is Your Entry**: Don't chase; wait for price to return to the FVG
5. **Risk Management**: Never risk more than 1-2% per trade
