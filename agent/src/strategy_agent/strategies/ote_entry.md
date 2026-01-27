# Optimal Trade Entry (OTE) Strategy

## Overview
The Optimal Trade Entry (OTE) strategy uses Fibonacci retracement levels to find high-probability entry points during retracements in trending markets.

The "OTE Zone" is the sweet spot between the 62% and 79% Fibonacci retracement levels where price often finds support/resistance before continuing the trend.

---

## The OTE Zone

| Level | Significance |
|-------|-------------|
| 61.8% | Bottom of OTE zone (Golden Ratio) |
| 70.5% | Sweet Spot (ideal entry) |
| 78.6% | Top of OTE zone (maximum retracement) |

**Rule**: Entries are taken within the 62%-79% zone. The 70.5% level is considered the optimal entry point.

---

## Trading Sessions
- **Preferred:** New York session (7:00 AM - 4:00 PM EST)
- **Acceptable:** London session (2:00 AM - 11:00 AM EST)
- **Avoid:** Asian session (setups less reliable due to lower volume)

---

## Bias Determination

Use the **1-Hour (1H) timeframe** to determine trend direction.

### Bullish Bias (OTE Long)
- 1H shows Higher Highs and Higher Lows
- Market is in an uptrend
- Look for retracements to the OTE zone

### Bearish Bias (OTE Short)
- 1H shows Lower Highs and Lower Lows
- Market is in a downtrend
- Look for retracements to the OTE zone

### No Bias (No Trade)
- Structure is unclear or mixed
- Market is ranging/consolidating
- Insufficient data to determine trend

---

## Entry Criteria

### For BULLISH OTE (Long)

1. **Establish Bullish Trend**
   - 1H structure shows HH/HL
   - Most recent impulse move is upward

2. **Wait for Retracement**
   - Price pulls back from a recent swing high
   - Retracement begins

3. **OTE Zone Entry**
   - Price enters the 62%-79% retracement zone
   - Ideal entry at the 70.5% level

4. **Confluence (Optional but Preferred)**
   - A Bullish FVG exists within the OTE zone
   - Or an Order Block aligns with the OTE zone

5. **Entry Execution**
   - Place limit order at 70.5% level
   - Or wait for bullish rejection candle within the zone

6. **Stop Loss**
   - Below the 79% level (structure invalidation)
   - Or below the recent swing low + buffer

7. **Take Profit**
   - -27% Fibonacci extension (1:2 RR minimum)
   - Or previous swing high
   - Or next resistance level

---

### For BEARISH OTE (Short)

1. **Establish Bearish Trend**
   - 1H structure shows LH/LL
   - Most recent impulse move is downward

2. **Wait for Retracement**
   - Price pulls back from a recent swing low
   - Retracement begins (price rallies)

3. **OTE Zone Entry**
   - Price enters the 62%-79% retracement zone (measured from high to low)
   - Ideal entry at the 70.5% level

4. **Confluence (Optional but Preferred)**
   - A Bearish FVG exists within the OTE zone
   - Or an Order Block aligns with the OTE zone

5. **Entry Execution**
   - Place limit order at 70.5% level
   - Or wait for bearish rejection candle within the zone

6. **Stop Loss**
   - Above the 79% level (structure invalidation)
   - Or above the recent swing high + buffer

7. **Take Profit**
   - -27% Fibonacci extension (1:2 RR minimum)
   - Or previous swing low
   - Or next support level

---

## Filters (Trade Blockers)

Do NOT take a trade if ANY of these apply:

1. **Trend Unclear**
   - 1H structure does not show clear HH/HL or LH/LL
   - Market is ranging

2. **Already Past OTE Zone**
   - Price has already moved beyond the 79% level
   - Structure may now be invalidated

3. **No Impulse Move**
   - There's no clear swing to measure Fibonacci from
   - Market is choppy

4. **News Risk**
   - High-impact news within 30 minutes
   
5. **Weekend/Off-Hours**
   - Avoid trading during low-liquidity periods

---

## Confidence Scoring

| Condition | Confidence |
|-----------|------------|
| Clear trend + Price in OTE zone + FVG confluence | 90% |
| Clear trend + Price in OTE zone | 75% |
| Clear trend + Price approaching OTE zone | 60% (MONITOR) |
| Trend unclear | 20% (WAIT) |
| Price beyond 79% level | 10% (WAIT - structure invalid) |

---

## Example Decision Flow

```
IF 1H shows clear trend (HH/HL or LH/LL):
    Calculate OTE zone (62%-79% of last impulse)
    
    IF current price is WITHIN the OTE zone:
        IF there is FVG or OB confluence:
            → ACTION: TRADE
            → Entry: 70.5% level or FVG midpoint
            → SL: Beyond 79% level
            → TP: -27% extension or swing extreme
        ELSE:
            → ACTION: TRADE (lower confidence)
    
    ELSE IF current price is ABOVE the OTE zone (for longs):
        → ACTION: MONITOR (wait for pullback)
    
    ELSE IF current price is BELOW the OTE zone (for longs):
        → ACTION: WAIT (structure may have changed)
ELSE:
    → ACTION: WAIT (no clear trend)
```

---

## Key Reminders

1. **Trend is Your Friend**: OTE works best in trending markets
2. **The 70.5% Sweet Spot**: This is statistically the most reliable entry level
3. **Don't Force It**: If price blasts through the OTE zone, the structure has changed
4. **Add Confluence**: FVGs or Order Blocks in the OTE zone increase probability
5. **Minimum 1:2 RR**: Always ensure proper risk/reward before entering
