"""
Liquidity Observation Tools.

Analyzes price action to identify liquidity pools, sweeps, and equal highs/lows.
Pure observation - no trading signals.
"""
from typing import List, Optional


def find_sweeps(candles: List[dict], swing_points: Optional[dict] = None) -> List[dict]:
    """
    Detect liquidity sweeps (stop hunts).

    A sweep occurs when price wicks beyond a swing point but closes back
    inside, indicating liquidity was taken and price rejected.

    Args:
        candles: List of OHLCV candles
        swing_points: Pre-computed swings (optional)

    Returns:
        [
            {
                "type": "SELL_SIDE_SWEEP" | "BUY_SIDE_SWEEP",
                "swing_price": float,
                "sweep_price": float,  # The extreme of the wick
                "candle_index": int,
                "rejection_strength": float,  # How far price rejected
                "time": str,
                "observation": str
            },
            ...
        ]
    """
    if swing_points is None:
        from app.tools.structure import get_swing_points
        swing_points = get_swing_points(candles)

    sweeps = []

    # Check last 5 candles for sweeps
    recent_candles = candles[-5:] if len(candles) >= 5 else candles
    start_idx = len(candles) - len(recent_candles)

    for i, candle in enumerate(recent_candles):
        actual_idx = start_idx + i

        # Check sell-side sweep (wick below swing low, close above)
        for swing in swing_points.get("swing_lows", [])[-5:]:
            swing_low = swing["price"]

            if candle["low"] < swing_low and candle["close"] > swing_low:
                rejection = candle["close"] - candle["low"]
                sweeps.append({
                    "type": "SELL_SIDE_SWEEP",
                    "swing_price": swing_low,
                    "sweep_price": candle["low"],
                    "candle_index": actual_idx,
                    "rejection_strength": round(rejection, 5),
                    "time": candle.get("time", str(actual_idx)),
                    "observation": (
                        f"Sell-side liquidity swept at {candle['low']:.5f} "
                        f"(below swing {swing_low:.5f}), rejected to {candle['close']:.5f}"
                    )
                })

        # Check buy-side sweep (wick above swing high, close below)
        for swing in swing_points.get("swing_highs", [])[-5:]:
            swing_high = swing["price"]

            if candle["high"] > swing_high and candle["close"] < swing_high:
                rejection = candle["high"] - candle["close"]
                sweeps.append({
                    "type": "BUY_SIDE_SWEEP",
                    "swing_price": swing_high,
                    "sweep_price": candle["high"],
                    "candle_index": actual_idx,
                    "rejection_strength": round(rejection, 5),
                    "time": candle.get("time", str(actual_idx)),
                    "observation": (
                        f"Buy-side liquidity swept at {candle['high']:.5f} "
                        f"(above swing {swing_high:.5f}), rejected to {candle['close']:.5f}"
                    )
                })

    return sweeps


def find_equal_highs_lows(candles: List[dict], tolerance_pips: float = 5.0) -> dict:
    """
    Detect equal highs and equal lows (liquidity pools).

    Multiple swing points at similar prices indicate resting liquidity
    that smart money may target.

    Args:
        candles: List of OHLCV candles
        tolerance_pips: Price difference tolerance in pips

    Returns:
        {
            "equal_highs": [
                {"prices": [p1, p2, ...], "average": float, "count": int, "observation": str},
                ...
            ],
            "equal_lows": [
                {"prices": [p1, p2, ...], "average": float, "count": int, "observation": str},
                ...
            ]
        }
    """
    from app.tools.structure import get_swing_points

    swing_points = get_swing_points(candles)

    # Convert tolerance to price (assuming forex with 4 decimal places)
    tolerance = tolerance_pips * 0.0001

    def cluster_prices(swings: List[dict], tolerance: float) -> List[dict]:
        """Group nearby prices into clusters."""
        if not swings:
            return []

        prices = [s["price"] for s in swings]
        prices.sort()

        clusters = []
        current_cluster = [prices[0]]

        for price in prices[1:]:
            if price - current_cluster[-1] <= tolerance:
                current_cluster.append(price)
            else:
                if len(current_cluster) >= 2:
                    avg = sum(current_cluster) / len(current_cluster)
                    clusters.append({
                        "prices": current_cluster,
                        "average": round(avg, 5),
                        "count": len(current_cluster)
                    })
                current_cluster = [price]

        # Don't forget last cluster
        if len(current_cluster) >= 2:
            avg = sum(current_cluster) / len(current_cluster)
            clusters.append({
                "prices": current_cluster,
                "average": round(avg, 5),
                "count": len(current_cluster)
            })

        return clusters

    equal_highs = cluster_prices(swing_points["swing_highs"], tolerance)
    equal_lows = cluster_prices(swing_points["swing_lows"], tolerance)

    # Add observations
    for eh in equal_highs:
        eh["observation"] = (
            f"Equal highs cluster: {eh['count']} highs near {eh['average']:.5f} "
            f"(buy-side liquidity pool)"
        )

    for el in equal_lows:
        el["observation"] = (
            f"Equal lows cluster: {el['count']} lows near {el['average']:.5f} "
            f"(sell-side liquidity pool)"
        )

    return {
        "equal_highs": equal_highs,
        "equal_lows": equal_lows
    }


def identify_liquidity_pools(candles: List[dict]) -> dict:
    """
    Comprehensive liquidity analysis.

    Identifies:
    - Recent swing highs/lows as liquidity targets
    - Equal highs/lows clusters
    - Previous session highs/lows
    - Obvious stop loss zones

    Args:
        candles: List of OHLCV candles

    Returns:
        {
            "buy_side_liquidity": [{"price": float, "type": str, "strength": str}, ...],
            "sell_side_liquidity": [{"price": float, "type": str, "strength": str}, ...],
            "observation": str
        }
    """
    from app.tools.structure import get_swing_points

    swing_points = get_swing_points(candles)
    equal_levels = find_equal_highs_lows(candles)

    buy_side = []
    sell_side = []

    # Add swing highs as buy-side liquidity
    for swing in swing_points.get("swing_highs", [])[-5:]:
        buy_side.append({
            "price": swing["price"],
            "type": "swing_high",
            "strength": "medium"
        })

    # Add swing lows as sell-side liquidity
    for swing in swing_points.get("swing_lows", [])[-5:]:
        sell_side.append({
            "price": swing["price"],
            "type": "swing_low",
            "strength": "medium"
        })

    # Equal highs are stronger buy-side liquidity
    for cluster in equal_levels.get("equal_highs", []):
        buy_side.append({
            "price": cluster["average"],
            "type": "equal_highs",
            "strength": "high" if cluster["count"] >= 3 else "medium"
        })

    # Equal lows are stronger sell-side liquidity
    for cluster in equal_levels.get("equal_lows", []):
        sell_side.append({
            "price": cluster["average"],
            "type": "equal_lows",
            "strength": "high" if cluster["count"] >= 3 else "medium"
        })

    # Sort by price
    buy_side.sort(key=lambda x: x["price"], reverse=True)
    sell_side.sort(key=lambda x: x["price"])

    # Build observation
    current_price = candles[-1]["close"]
    nearest_buy = buy_side[0] if buy_side else None
    nearest_sell = sell_side[0] if sell_side else None

    obs_parts = []
    if nearest_buy:
        dist = nearest_buy["price"] - current_price
        obs_parts.append(
            f"Nearest buy-side liquidity: {nearest_buy['price']:.5f} "
            f"({nearest_buy['type']}, {dist:.5f} above)"
        )
    if nearest_sell:
        dist = current_price - nearest_sell["price"]
        obs_parts.append(
            f"Nearest sell-side liquidity: {nearest_sell['price']:.5f} "
            f"({nearest_sell['type']}, {dist:.5f} below)"
        )

    return {
        "buy_side_liquidity": buy_side,
        "sell_side_liquidity": sell_side,
        "observation": "; ".join(obs_parts) if obs_parts else "No significant liquidity pools identified"
    }
