"""
ICT Agentic Trading System - Hierarchical Agent Architecture.

This package implements a three-agent hierarchy:
- MainAgent: Orchestrator with state machine and clock control
- StrategyAgent: Market context analysis (bias, environment, levels)
- WorkerAgent: Pattern detection and trade execution

Usage:
    from src import MainAgent, load_rules

    # Load rules configuration
    load_rules("rules/config.yaml")

    # Create main agent
    agent = MainAgent()

    # Initialize session
    agent.initialize_session(
        symbol="EURUSD",
        mode="BACKTEST",
        start_time=datetime(2024, 1, 1),
        end_time=datetime(2024, 12, 31)
    )

    # Run tick
    result = agent.run_tick(timeframe_bars, economic_calendar)
"""

# Core agents
from .main_agent import MainAgent
from .strategy_agent import StrategyAgent
from .worker_agent import WorkerAgent

# State models
from .state import (
    SessionState, SessionPhase, MarketContext, TradeSetup,
    Position, ClosedTrade, VirtualClock,
    BiasDirection, EnvironmentStatus, OrderDirection, TradingSession
)

# Protocol
from .protocol import (
    MessageEnvelope, MessageLog, TickLog, TickEvent,
    ActionType, AgentRole
)

# Rules configuration
from .rules_config import (
    RulesConfig, RulesManager,
    load_rules, get_rules, reload_rules, get_rules_manager
)

__all__ = [
    # Agents
    "MainAgent",
    "StrategyAgent",
    "WorkerAgent",

    # State
    "SessionState",
    "SessionPhase",
    "MarketContext",
    "TradeSetup",
    "Position",
    "ClosedTrade",
    "VirtualClock",
    "BiasDirection",
    "EnvironmentStatus",
    "OrderDirection",
    "TradingSession",

    # Protocol
    "MessageEnvelope",
    "MessageLog",
    "TickLog",
    "TickEvent",
    "ActionType",
    "AgentRole",

    # Rules
    "RulesConfig",
    "RulesManager",
    "load_rules",
    "get_rules",
    "reload_rules",
    "get_rules_manager",
]
