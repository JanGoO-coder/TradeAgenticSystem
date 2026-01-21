"""LangGraph Workflow for ICT Trading System."""
from typing import Dict, Any
from langgraph.graph import StateGraph, END

from src.models import GraphState, TradeStatus
from src.nodes import (
    macro_analyst_node,
    gatekeeper_node,
    sniper_node,
    risk_calculator_node,
    executor_node
)


def should_continue_after_gatekeeper(state: GraphState) -> str:
    """Router: Continue to Sniper if gatekeeper passes, else go to Executor."""
    if state.gatekeeper_status == "WAIT":
        return "executor"
    return "sniper"


def should_continue_after_sniper(state: GraphState) -> str:
    """Router: Continue to Risk Calculator if setup found, else go to Executor."""
    if state.detected_setup is None:
        return "executor"
    return "risk_calculator"


def build_trading_graph() -> StateGraph:
    """
    Build the LangGraph workflow for ICT trading analysis.
    
    Flow:
    1. Macro_Analyst -> Determine HTF Bias (Rule 1.1)
    2. Gatekeeper -> Check Kill Zones & News (Rules 8.1, 8.4)
    3. Sniper -> Pattern Recognition on LTF (Rules 6.*)
    4. Risk_Calculator -> Position sizing (Rules 7.1, 7.2)
    5. Executor -> Final checklist & output (Rule 10)
    """
    # Create the graph with our state type
    workflow = StateGraph(GraphState)
    
    # Add nodes (agents)
    workflow.add_node("macro_analyst", macro_analyst_node)
    workflow.add_node("gatekeeper", gatekeeper_node)
    workflow.add_node("sniper", sniper_node)
    workflow.add_node("risk_calculator", risk_calculator_node)
    workflow.add_node("executor", executor_node)
    
    # Set the entry point
    workflow.set_entry_point("macro_analyst")
    
    # Add edges
    workflow.add_edge("macro_analyst", "gatekeeper")
    
    # Conditional edge after gatekeeper
    workflow.add_conditional_edges(
        "gatekeeper",
        should_continue_after_gatekeeper,
        {
            "sniper": "sniper",
            "executor": "executor"
        }
    )
    
    # Conditional edge after sniper
    workflow.add_conditional_edges(
        "sniper",
        should_continue_after_sniper,
        {
            "risk_calculator": "risk_calculator",
            "executor": "executor"
        }
    )
    
    # Direct edges to executor
    workflow.add_edge("risk_calculator", "executor")
    
    # End after executor
    workflow.add_edge("executor", END)
    
    return workflow


def compile_graph():
    """Compile the graph for execution."""
    workflow = build_trading_graph()
    return workflow.compile()


def run_analysis(snapshot_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run the complete ICT trading analysis pipeline.
    
    Args:
        snapshot_data: Market snapshot matching the input contract
        
    Returns:
        Trade Setup Response JSON
    """
    from src.models import MarketSnapshot
    
    # Parse input
    snapshot = MarketSnapshot(**snapshot_data)
    
    # Initialize state
    initial_state = GraphState(
        snapshot=snapshot,
        nodes_triggered=[]
    )
    
    # Compile and run graph
    app = compile_graph()
    # LangGraph returns state as dict
    final_state_dict = app.invoke(initial_state)
    
    # Build response directly from dict
    response = build_response_from_dict(final_state_dict, snapshot)
    return response


def build_response_from_dict(state: dict, snapshot) -> dict:
    """Build the Trade Setup Response from final state dict."""
    
    # Extract values with defaults
    htf_bias = state.get("htf_bias")
    ltf_alignment = state.get("ltf_alignment")
    detected_setup = state.get("detected_setup")
    risk_params = state.get("risk_params")
    checklist = state.get("checklist")
    
    # Default values for missing components
    if htf_bias is None:
        htf_bias = {"value": "NEUTRAL", "rule_refs": ["1.1"]}
    elif hasattr(htf_bias, 'model_dump'):
        htf_bias = htf_bias.model_dump()
    
    if ltf_alignment is None:
        ltf_alignment = {"timeframe": "15M", "alignment": "NOT_ALIGNED", "rule_refs": ["1.2"]}
    elif hasattr(ltf_alignment, 'model_dump'):
        ltf_alignment = ltf_alignment.model_dump()
    
    if detected_setup is None:
        setup = {
            "name": "None",
            "type": "None",
            "entry_price": None,
            "entry_type": None,
            "stop_loss": None,
            "take_profit": None,
            "invalidation_point": None,
            "is_counter_trend": False,
            "confluence_score": 0,
            "rule_refs": []
        }
    elif hasattr(detected_setup, 'model_dump'):
        setup = detected_setup.model_dump()
    else:
        setup = detected_setup
    
    if risk_params is None:
        risk = {
            "account_balance": snapshot.account_balance,
            "risk_pct": snapshot.risk_pct,
            "position_size": 0,
            "rr": None
        }
    elif hasattr(risk_params, 'model_dump'):
        risk = risk_params.model_dump()
    else:
        risk = risk_params
    
    if checklist is None:
        checklist_data = {
            "htf_bias_exists": False,
            "ltf_mss": False,
            "pd_alignment": False,
            "liquidity_sweep_detected": False,
            "session_ok": False,
            "news_ok": True,
            "rr_minimum_met": False
        }
    elif hasattr(checklist, 'model_dump'):
        checklist_data = checklist.model_dump()
    else:
        checklist_data = checklist
    
    # Get status
    final_status = state.get("final_status")
    if hasattr(final_status, 'value'):
        status_value = final_status.value
    elif final_status:
        status_value = str(final_status)
    else:
        status_value = "NO_TRADE"
    
    response = {
        "symbol": snapshot.symbol,
        "timestamp": snapshot.timestamp,
        "status": status_value,
        "reason_short": state.get("reason_short", ""),
        "htf_bias": htf_bias,
        "ltf_alignment": ltf_alignment,
        "setup": setup,
        "risk": risk,
        "checklist": checklist_data,
        "explanation": state.get("explanation", ""),
        "graph_nodes_triggered": state.get("nodes_triggered", []),
        "confidence": state.get("confidence", 0.0)
    }
    
    return response


def build_response(state: GraphState) -> dict:
    """Build the Trade Setup Response from final state."""
    from src.models import BiasValue, AlignmentStatus, TradeStatus, EntryType
    
    # Default values for missing components
    htf_bias = state.htf_bias or {
        "value": "NEUTRAL",
        "rule_refs": ["1.1"]
    }
    
    ltf_alignment = state.ltf_alignment or {
        "timeframe": "15M",
        "alignment": "NOT_ALIGNED",
        "rule_refs": ["1.2"]
    }
    
    setup = state.detected_setup or {
        "name": "None",
        "type": "None",
        "entry_price": None,
        "entry_type": None,
        "stop_loss": None,
        "take_profit": None,
        "invalidation_point": None,
        "is_counter_trend": False,
        "confluence_score": 0,
        "rule_refs": []
    }
    
    risk = state.risk_params or {
        "account_balance": state.snapshot.account_balance,
        "risk_pct": state.snapshot.risk_pct,
        "position_size": 0,
        "rr": None
    }
    
    checklist = state.checklist or {
        "htf_bias_exists": False,
        "ltf_mss": False,
        "pd_alignment": False,
        "liquidity_sweep_detected": False,
        "session_ok": False,
        "news_ok": True,
        "rr_minimum_met": False
    }
    
    # Convert to dict format
    if hasattr(htf_bias, 'model_dump'):
        htf_bias = htf_bias.model_dump()
    if hasattr(ltf_alignment, 'model_dump'):
        ltf_alignment = ltf_alignment.model_dump()
    if hasattr(setup, 'model_dump'):
        setup = setup.model_dump()
    if hasattr(risk, 'model_dump'):
        risk = risk.model_dump()
    if hasattr(checklist, 'model_dump'):
        checklist = checklist.model_dump()
    
    response = {
        "symbol": state.snapshot.symbol,
        "timestamp": state.snapshot.timestamp,
        "status": state.final_status.value if state.final_status else "NO_TRADE",
        "reason_short": state.reason_short,
        "htf_bias": htf_bias,
        "ltf_alignment": ltf_alignment,
        "setup": setup,
        "risk": risk,
        "checklist": checklist,
        "explanation": state.explanation,
        "graph_nodes_triggered": state.nodes_triggered,
        "confidence": state.confidence
    }
    
    return response
