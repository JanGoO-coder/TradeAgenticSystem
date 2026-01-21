To build an agentic bot in LangChain or LangGraph based on your rulebook, you need to translate these hierarchical rules into specific **"Trade Logic Blocks"**.

An AI agent operates best when complex decisions are broken down into **State Checks** (Global Filters) and **Execution Logic** (Specific Trade Setups).

Here is the complete list of valid trades derived from your rulebook, structured for an automation architect.

---

### Part 1: The "Gatekeepers" (Global Pre-Conditions)

*Before the agent looks for any specific trade setup, it must pass these checks. If any fail, the agent is in a `WAIT` state.*

1. **Time Filter (Rule 8.1, 8.4)**
* **Check:** Is current time inside defined London or New York Kill Zone?
* **Check:** Is there High Impact News scheduled? (If yes, `PAUSE` trading).


2. **HTF Bias Lock (Rule 1.1)**
* **Check:** Analyze 1H Chart.
* **Condition:** Is there a clear Swing High/Low sequence?
* **Output:** `BIAS = BULLISH` OR `BIAS = BEARISH`. (If ranging/unclear, `BIAS = NULL` -> `WAIT`).



---

### Part 2: Bullish Trade Setups (Longs)

*The agent only activates these logic blocks if `BIAS = BULLISH`.*

#### 1. Bullish Trend Continuation (OTE Model)

*Best for: Joining an existing trend after a standard pullback.*

* **Rule Ref:** 6.1, 5.1, 1.2
* **Logic Sequence:**
1. **Context:** 1H Bias is Bullish. 15M structure is aligned (making HH/HL).
2. **Trigger:** Price retraces into a **Discount** zone (below 0.5 of the current dealing range).
3. **Confluence:** Price taps into a Bullish Order Block (OB) or FVG within the OTE zone (62-79% retracement).
4. **Entry Trigger:** 15M or 5M candle closes bullishly confirming rejection of the level.
5. **Stop Loss:** Below the Swing Low (Invalidation Point).
6. **Take Profit:** Upcoming 1H Swing High or liquidity pool.



#### 2. Bullish ICT 2022 Model (Reversal/Expansion)

*Best for: Catching the start of a move after liquidity is raided.*

* **Rule Ref:** 6.5, 2.3, 3.4
* **Logic Sequence:**
1. **Liquidity Sweep:** Price sweeps a Short-Term Low (Sell-Side Liquidity) *counter* to the 1H Bias.
2. **Displacement:** Immediate impulsive move UP.
3. **MSS (Market Structure Shift):** The displacement breaks the nearest Swing High with a body close.
4. **FVG Creation:** The displacement leg leaves a Bullish Fair Value Gap (FVG).
5. **Entry:** Limit Buy at the top of the FVG (or consequent encroachment 50%).
6. **Stop Loss:** Below the swing low that swept liquidity.
7. **Take Profit:** 1:2 R:R minimum or next Buy-Side Liquidity.



#### 3. Bullish Power of Three (PO3)

*Best for: Daily bias expansion trades.*

* **Rule Ref:** 4.2, 6.6
* **Logic Sequence:**
1. **Accumulation:** Identify a ranging period (usually Asian Session or pre-NY).
2. **Manipulation (Judas Swing):** Wait for price to drop *below* the accumulation range opening price (Sell-side sweep).
3. **Confirmation:** Price reclaims the range low and displaces up.
4. **Entry:** On the retest of the accumulation range low or an FVG created during the reclaim.
5. **Stop Loss:** Below the Manipulation low.
6. **Take Profit:** Projected distribution target (Standard deviations or liquidity above range).



---

### Part 3: Bearish Trade Setups (Shorts)

*The agent only activates these logic blocks if `BIAS = BEARISH`.*

#### 4. Bearish Trend Continuation (OTE Model)

* **Rule Ref:** 6.1, 5.1, 1.2
* **Logic Sequence:**
1. **Context:** 1H Bias is Bearish. 15M structure is making LH/LL.
2. **Trigger:** Price retraces into a **Premium** zone (above 0.5 of the current dealing range).
3. **Confluence:** Price taps into a Bearish Order Block (OB) or FVG within the OTE zone.
4. **Entry Trigger:** 15M or 5M candle closes bearishly.
5. **Stop Loss:** Above the Swing High.
6. **Take Profit:** Upcoming 1H Swing Low.



#### 5. Bearish ICT 2022 Model (Reversal/Expansion)

* **Rule Ref:** 6.5, 2.3, 3.4
* **Logic Sequence:**
1. **Liquidity Sweep:** Price sweeps a Short-Term High (Buy-Side Liquidity).
2. **Displacement:** Immediate impulsive move DOWN.
3. **MSS:** The displacement breaks the nearest Swing Low with a body close.
4. **FVG Creation:** The displacement leg leaves a Bearish FVG.
5. **Entry:** Limit Sell at the bottom of the FVG.
6. **Stop Loss:** Above the swing high that swept liquidity.
7. **Take Profit:** 1:2 R:R minimum or next Sell-Side Liquidity.



#### 6. Bearish Power of Three (PO3)

* **Rule Ref:** 4.2, 6.6
* **Logic Sequence:**
1. **Accumulation:** Identify a ranging period.
2. **Manipulation:** Wait for price to rally *above* the accumulation range (Buy-side sweep).
3. **Confirmation:** Price falls back into the range and displaces down.
4. **Entry:** On the retest of the accumulation range high or created FVG.
5. **Stop Loss:** Above the Manipulation high.



---

### Part 4: Special Case Trade (Counter-Trend)

*Requires Strict Adherence to Rule 1.2.2*

#### 7. The Turtle Soup / Liquidity Raid (High Risk)

* **Rule Ref:** 6.7, 1.2.2
* **Logic Sequence:**
1. **Context:** Price is at a Major Higher Timeframe (HTF) Level (e.g., Weekly/Daily High).
2. **Sweep:** Price pierces the HTF level.
3. **Rejection:** Price fails to close above/below the level and closes back inside the range immediately.
4. **1H Confirmation:** **CRITICAL:** Wait for a 1H Candle to close reversing the move (1H MSS). *Do not trade on lower timeframes without 1H MSS as per Rule 1.2.2.*
5. **Entry:** Retracement to the Order Block formed by the rejection.



---

### Part 5: Agent Logic Flow for LangGraph

To implement this in LangGraph, you can structure your nodes as follows:

1. **Node 1: Market_Scanner**
* Fetch 1H Data.
* Apply Rule 1.1 (Structure check).
* Determine Bias.
* *Output:* `{"bias": "bullish", "status": "active"}`


2. **Node 2: Filter_Check**
* Check Time (Rule 8.1).
* Check News (Rule 8.4).
* *If Pass:* Proceed to Node 3.
* *If Fail:* End Graph (Wait).


3. **Node 3: Pattern_Recognition (The "Brain")**
* Takes `bias` as input.
* Scans 15M/5M data for:
* IF `bias == bullish`: Scan for `Bullish_OTE`, `Bullish_2022`, `Bullish_PO3`.
* IF `bias == bearish`: Scan for `Bearish_OTE`, `Bearish_2022`, `Bearish_PO3`.


* Validates "Displacement" (Rule 2.2 - must be body close).
* *Output:* `{"setup_found": "Bearish_2022", "entry_price": 1.0500, "sl": 1.0520, "tp": 1.0450}`


4. **Node 4: Risk_Calculator**
* Apply Rule 7.1 (Fixed % Risk).
* Apply Rule 7.2 (Check R:R > 1:2).
* *Output:* Lot Size / Contract Size.


5. **Node 5: Execution_Agent**
* Place Order (Limit or Market).
* Monitor for Trade Management (Rule 7.4/7.5 - Break even logic).



### JSON Structure for an AI Prompt

If you are passing this to an LLM to evaluate a chart, use this exact prompt structure:

```json
{
  "task": "Analyze Trade Setup",
  "rules_reference": "ICT_Rulebook_V1",
  "inputs": {
    "htf_bias": "[Derived from Rule 1.1]",
    "current_session": "[London/NY/Asia]",
    "liquidity_status": "[Has Buy-side/Sell-side been swept?]",
    "displacement_check": "[Did candle close beyond structure?]"
  },
  "required_output": {
    "valid_setup_name": "[e.g., Bullish ICT 2022]",
    "confluence_score": "[1-10 based on rules]",
    "invalidation_point": "[Price level]",
    "is_counter_trend": "[True/False - if True check Rule 1.2.2]"
  }
}

```