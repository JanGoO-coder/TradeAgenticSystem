
import unittest
from decimal import Decimal
from datetime import datetime
from src.models import OHLCV, BiasValue
from src.tools import (
    identify_swing_points,
    detect_fvg,
    check_kill_zone,
    calculate_ote_fib,
    get_market_structure,
    detect_displacement,
    to_decimal
)

class TestTools(unittest.TestCase):
    def setUp(self):
        pass

    def create_candle(self, i, open_p, high_p, low_p, close_p):
        return OHLCV(
            timestamp=datetime(2024, 1, 1, 10, i),
            open=Decimal(str(open_p)),
            high=Decimal(str(high_p)),
            low=Decimal(str(low_p)),
            close=Decimal(str(close_p)),
            volume=Decimal("100")
        )

    def test_precision_math(self):
        """Test that Decimal math is working as expected."""
        d1 = to_decimal(0.1)
        d2 = to_decimal(0.2)
        # Check standard float error is avoided
        self.assertEqual(d1 + d2, Decimal("0.3"))

    def test_identify_swing_points(self):
        """Test swing high/low detection."""
        # Create a clearer swing high pattern: 10, 11, 12, 11, 10
        # Indices: 0, 1, 2, 3, 4. Lookback=1 implies index 2 is swing high.
        # But default lookback is 2.
        # Pattern: 10, 12, 11, 15, 11, 10, 10
        # Index 3 (15) > index 1,2 and 4,5.
        
        prices = [10, 11, 12, 15, 12, 11, 10]
        candles = []
        for i, p in enumerate(prices):
            candles.append(self.create_candle(i, p, p, p, p))
            
        # Manually set Highs/Lows to ensure swing integrity
        # Index 3 is absolute peak
        candles[3].high = Decimal("15")
        
        swings = identify_swing_points(candles, lookback=2)
        
        # We expect index 3 to be a swing high
        highs = swings["swing_highs"]
        self.assertEqual(len(highs), 1, "Should find exactly 1 swing high")
        self.assertEqual(highs[0][0], 3)
        self.assertEqual(highs[0][1], Decimal("15"))

    def test_detect_fvg_bullish(self):
        """Test Bullish Fair Value Gap detection."""
        # Candle 1: High = 100
        # Candle 2: Momentum up (102 -> 108)
        # Candle 3: Low = 104
        # Gap is 100 to 104.
        
        c1 = self.create_candle(0, 95, 100, 95, 98)
        c2 = self.create_candle(1, 102, 109, 102, 108) # Momentum
        c3 = self.create_candle(2, 106, 110, 104, 109) # Low is 104
        
        candles = [c1, c2, c3]
        fvgs = detect_fvg(candles)
        
        self.assertEqual(len(fvgs), 1)
        fvg = fvgs[0]
        self.assertEqual(fvg["type"], "BULLISH_FVG")
        self.assertEqual(fvg["bottom"], Decimal("100"))
        self.assertEqual(fvg["top"], Decimal("104"))
        self.assertEqual(fvg["midpoint"], Decimal("102"))

    def test_check_kill_zone(self):
        """Test Kill Zone time checks."""
        # London KZ: 07:00 - 10:00 UTC
        # NY KZ: 12:00 - 15:00 UTC
        
        # 08:30 UTC -> London
        t1 = datetime(2024, 1, 1, 8, 30)
        res1 = check_kill_zone(t1)
        self.assertTrue(res1["in_kill_zone"])
        self.assertEqual(res1["session"], "London")
        
        # 11:00 UTC -> No KZ
        t2 = datetime(2024, 1, 1, 11, 0)
        res2 = check_kill_zone(t2)
        self.assertFalse(res2["in_kill_zone"])
        
        # 13:00 UTC -> NY
        t3 = datetime(2024, 1, 1, 13, 0)
        res3 = check_kill_zone(t3)
        self.assertTrue(res3["in_kill_zone"])
        # self.assertEqual(res3["session"], "NY") # Note: Logic in tool uses "NY"

    def test_ote_calculation(self):
        """Test OTE fib levels."""
        # Bullish retracement: Low=0, High=100
        # OTE should be:
        # 0.62 retracement level = 100 - 61.8 = 38.2
        # Wait, OTE is deep retracement.
        # tools.py says: 
        # ote_62 = swing_high - (range_size * 0.618)
        # If range is 100 (0 to 100)
        # ote_62 = 100 - 61.8 = 38.2.
        
        # Usually OTE is measured from the bottom for a long?
        # "Retracement from high to low for bullish OTE"
        # If we are bullish, we expect price to come DOWN to the OTE zone.
        # So we draw fib from Low to High.
        # 0 is at High, 1 is at Low.
        # 0.62 retracement is 0.62 down from High? Or 0.62 up from Low?
        # Standard fib: 0 at Low, 1 at High. Retracement of 62% means price drops 62% of the move.
        # Price = High - (Range * 0.62).
        
        res = calculate_ote_fib(Decimal("100"), Decimal("0"), "BULLISH")
        
        # Expected:
        # 61.8% retracement level = 100 - 61.8 = 38.2
        # 79% retracement level = 100 - 79 = 21
        
        self.assertEqual(res["ote_zone_top"], Decimal("38.2"))
        self.assertEqual(res["ote_zone_bottom"], Decimal("21.0"))

if __name__ == '__main__':
    unittest.main()
