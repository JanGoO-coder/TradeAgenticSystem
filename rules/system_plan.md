To build a fully autonomous agentic trading system for your ICT rules using **LangChain** and **LangGraph**, you need a modular architecture. You cannot find a single "ICT Python Library" that does everything; you must build **Custom Tools** that feed data to your **Agents**.

Here is the complete inventory of the Tools, Agents, and APIs you need to build.

---

### 1. The Core Infrastructure (Stack)

Before building agents, you need these foundational libraries:

* **Orchestration:** `LangGraph` (for state management and loops) and `LangChain` (for prompting).
* **LLM Logic:** `ChatOpenAI` (GPT-4o) or `Anthropic` (Claude 3.5 Sonnet - excellent for code/charts).
* **Data Processing:** `Pandas` / `NumPy` (for candle math).
* **Broker Connection:** `MetaTrader5` (Python package) OR `oandapyV20` (if using Oanda).

---

### 2. The Agent Team (LangGraph Nodes)

You will not have one single bot; you will have a team of specialized agents. In LangGraph, each of these is a **Node**.

#### Agent A: The "Macro Analyst" (Bias Engine)

* **Role:** Determines the 1H Directional Bias (Rule 1.1).
* **Input:** 1H OHLCV Data.
* **Output:** `BIAS: BULLISH`, `BIAS: BEARISH`, or `BIAS: NEUTRAL`.
* **Required Tools:**
1. `get_market_structure(timeframe="1H")`: A function that returns the last confirmed Higher High/Lower Low.
2. `check_displacement()`: A helper to confirm if a break was valid (Rule 2.2).



#### Agent B: The "Gatekeeper" (Risk & Time)

* **Role:** Enforces Rule 8 (Kill Zones) and Rule 9 (News).
* **Input:** Current Time, Economic Calendar.
* **Output:** `STATUS: GO` or `STATUS: WAIT`.
* **Required Tools:**
1. `check_kill_zone()`: Returns True if time is London (2-5 AM EST) or NY (7-10 AM EST).
2. `fetch_news_impact()`: Connects to an API (e.g., ForexFactory/Finnhub) to check for "High Impact" USD events in the next 60 mins.



#### Agent C: The "Sniper" (Pattern Recognition)

* **Role:** Scans 15M/5M for the specific entry models (OTE, 2022 Model) matching the Bias.
* **Input:** 15M/5M Data + Bias from Agent A.
* **Output:** `SETUP_FOUND: {Type: "Bearish 2022", Entry: 1.0500, SL: 1.0520}`.
* **Required Tools:**
1. `scan_fair_value_gaps(threshold=1.5)`: Identifies FVGs with displacement.
2. `scan_liquidity_sweeps()`: Checks if a recent candle wick purged a previous swing high/low.
3. `calculate_ote_fib()`: Returns the 62%, 70.5%, and 79% retracement levels of the current range.



#### Agent D: The "Executor" (Order Management)

* **Role:** sizes the position and sends it to the broker.
* **Input:** Setup details.
* **Required Tools:**
1. `calc_position_size(risk_pct=1.0)`: Calculates lot size based on account balance and Stop Loss distance.
2. `send_limit_order()`: Interacts with the Broker API.
3. `modify_order_breakeven()`: Trails the stop loss once price moves (Rule 7.5).



---

### 3. The Custom Tools List (Python Functions)

You must write these Python functions and bind them to your agents as `@tool`.

| Tool Name | Purpose | Logic Reference |
| --- | --- | --- |
| **`identify_swing_points`** | Returns indices of Swing Highs/Lows (fractals). | Rule 2.1 |
| **`detect_fvg`** | Finds 3-candle sequence where (High[1] < Low[3]) or (Low[1] > High[3]). | Rule 5.2 |
| **`detect_displacement`** | Checks if candle body size > 2x ATR (Average True Range). | Rule 2.2 |
| **`check_pd_array`** | Determines if current price is in Premium (>0.5) or Discount (<0.5). | Rule 5.1 |
| **`get_economic_events`** | Scrapes or fetches "Red Folder" news events. | Rule 8.4 |
| **`get_account_metrics`** | Fetches Balance, Equity, and current Open Positions. | Rule 7.1 |

---

### 4. Recommended External Data APIs

Do not rely on the LLM's internal knowledge for data; you must feed it real-time info.

1. **Market Data & Execution:**
* **MetaTrader 5 (MT5):** The gold standard for Forex.
* *Library:* `pip install MetaTrader5`
* *Why:* Free data, direct execution, works with most prop firms.


* **Oanda v20:** Good alternative if you are in a regulated region (USA/Europe).
* *Library:* `pip install oandapyV20` or `tpqoa`.




2. **News Data:**
* **Financial Modeling Prep API:** Has a specific "Economic Calendar" endpoint.
* **ForexFactory Scraper:** (Custom script) to parse the daily calendar csv.