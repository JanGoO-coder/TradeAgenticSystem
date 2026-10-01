from app.hub.risk_engine import PropFirmRiskEngine


def test_daily_loss_and_drawdown_halts_trigger_vetoes() -> None:
    engine = PropFirmRiskEngine()

    base = engine.evaluate_cycle(symbol="EURUSD", account_balance=10_000.0, open_trades=[])
    assert base.allowed

    daily_halt = engine.evaluate_cycle(symbol="EURUSD", account_balance=9_500.0, open_trades=[])
    assert not daily_halt.allowed
    assert "daily_loss_limit_halt" in daily_halt.vetoes

    dd_halt = engine.evaluate_cycle(symbol="EURUSD", account_balance=9_200.0, open_trades=[])
    assert not dd_halt.allowed
    assert "global_drawdown_limit_halt" in dd_halt.vetoes


def test_correlated_pairs_count_as_single_concurrency_group() -> None:
    engine = PropFirmRiskEngine()

    correlated_only = [
        {"symbol": "EURUSD"},
        {"symbol": "USDJPY"},
    ]
    eval_correlated = engine.evaluate_cycle(
        symbol="EURUSD",
        account_balance=10_000.0,
        open_trades=correlated_only,
    )
    assert eval_correlated.current_concurrent_trades == 1
    assert "max_concurrent_trades_reached" not in eval_correlated.vetoes

    grouped_two = [
        {"symbol": "EURUSD"},
        {"symbol": "USDJPY"},
        {"symbol": "GBPCHF"},
    ]
    eval_two_groups = engine.evaluate_cycle(
        symbol="EURUSD",
        account_balance=10_000.0,
        open_trades=grouped_two,
    )
    assert eval_two_groups.current_concurrent_trades == 2
    assert "max_concurrent_trades_reached" in eval_two_groups.vetoes
