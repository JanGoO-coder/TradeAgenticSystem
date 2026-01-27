"""
Disaster Recovery Verification Script

Simulates a critical system crash (process death) and verification of:
1. State Persistence (Save after tick).
2. State Recovery (Load on restart).
3. Workflow Resumption (Picking up a pending reliable request).

Scenario:
- Main Agent sends EXECUTE request.
- Worker returns ACK (simulating async processing).
- System CRASHES (Main Agent dies).
- System RESTARTS (New Main Agent loads state from disk).
- Agent confirms it is still 'WAITING' for the pending request.
- Delayed RECEIPT is injected.
- Agent completes the flow successfully.
"""
import sys
import os
import logging
import uuid
import shutil
import json
from datetime import datetime
from pathlib import Path

# Setup Paths
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.abspath(os.path.join(current_dir, "../.."))) # agent root
sys.path.append(os.path.abspath(os.path.join(current_dir, "../../../backend"))) # backend root

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("DR_TEST")

# Imports
from agent.src.main_agent.agent import MainAgent
from agent.src.protocol import ActionType, MessageEnvelope, AgentRole
from agent.src.state import SessionPhase
from app.services.persistence import PersistenceManager

TEST_DATA_DIR = os.path.join(current_dir, "dr_test_data")

def print_separator(title):
    print(f"\n{'='*20} {title} {'='*20}")

def mock_worker_handle_ack(message: MessageEnvelope) -> MessageEnvelope:
    """Simulates a Worker receiving a request and returning ACK (processing)."""
    return message.create_reply(ActionType.ACK, {"status": "PROCESSING"})

def main():
    print_separator("PHASE 1: NORMAL OPERATIONS")
    
    # 1. Setup Persistence with Test Dir
    if os.path.exists(TEST_DATA_DIR):
        shutil.rmtree(TEST_DATA_DIR)
    
    persistence = PersistenceManager(data_dir=TEST_DATA_DIR)
    
    # 2. Initialize Agent
    agent = MainAgent()
    session_state = agent.initialize_session(
        symbol="EURUSD",
        mode="BACKTEST",
        start_time=datetime.utcnow()
    )
    session_id = agent._correlation_id # Using session_id as correlation_id for persistence key usually
    # Note: Engine uses session_id for file name. MainAgent uses _correlation_id. 
    # Validating usage: Engine saves with `self._session_id`. MainAgent exports state.
    # We will mimic Engine behavior here.
    
    print(f"Session Initialized: {session_id}")
    
    # 3. Simulate Workflow State (Waiting for Worker)
    # We manually inject a pending request to simulate 'Mid-Flight' state
    # independent of the logic loop to guarantee we capture the state.
    
    pending_msg_id = f"msg_{uuid.uuid4().hex[:8]}"
    pending_corr_id = f"corr_{uuid.uuid4().hex[:8]}"
    
    req_payload = {
        "symbol": "EURUSD", 
        "direction": "LONG", 
        "entry_price": 1.05, 
        "stop_loss": 1.04, 
        "take_profit": 1.06
    }
    
    outbound_msg = MessageEnvelope(
        id=pending_msg_id,
        correlation_id=pending_corr_id,
        from_agent=AgentRole.MAIN,
        to_agent=AgentRole.WORKER,
        action=ActionType.EXECUTE_ORDER,
        payload=req_payload
    )
    
    # Inject into ReliabilityState
    agent._rel_state.pending_request = outbound_msg
    agent._rel_state.last_sent_time = datetime.utcnow()
    agent._rel_state.retry_count = 1
    
    print(f"Injected Pending Request: {pending_msg_id} (Corr: {pending_corr_id})")
    
    # 4. Save State (Checkpoint)
    state_data = agent.export_state()
    success = persistence.save_session(session_id, state_data)
    
    if success:
        print("State Saved Successfully.")
    else:
        print("CRITICAL: Failed to save state.")
        return

    print_separator("PHASE 2: THE CRASH")
    
    # Kill the objects
    del agent
    del persistence
    # Verify file exists
    expected_file = os.path.join(TEST_DATA_DIR, f"{session_id}.json")
    if os.path.exists(expected_file):
        print(f"Agent Process Terminated. Persisted File Found: {expected_file}")
    else:
        print("CRITICAL: Persisted file missing after crash!")
        return

    print_separator("PHASE 3: THE RECOVERY")
    
    # 1. New Instance
    new_persistence = PersistenceManager(data_dir=TEST_DATA_DIR)
    recovered_agent = MainAgent()
    
    # 2. Load State
    saved_data = new_persistence.load_session(session_id)
    if not saved_data:
        print("CRITICAL: Failed to load session data.")
        return
        
    recovered_agent.import_state(saved_data)
    
    # 3. Assertions
    print(f"Recovered Agent ID: {recovered_agent._correlation_id}")
    
    rel_state = recovered_agent._rel_state
    if rel_state.pending_request:
        print("SUCCESS: Pending Request Recovered!")
        print(f"   ID: {rel_state.pending_request.id}")
        print(f"   Action: {rel_state.pending_request.action}")
        print(f"   Retry Count: {rel_state.retry_count}")
        
        if rel_state.pending_request.id == pending_msg_id:
            print("   INTEGRITY CHECK: PASSED (IDs Match)")
        else:
            print("   INTEGRITY CHECK: FAILED (ID Mismatch)")
    else:
        print("FAILURE: Pending Request LOST during recovery.")
        return

    print_separator("PHASE 4: RESOLUTION")
    
    # Simulate delayed response arriving
    print("Simulating arrival of delayed Worker Receipt...")
    
    receipt_payload = {
        "order_id": "ord_123",
        "status": "FILLED",
        "execution_price": 1.05,
        "execution_time": datetime.utcnow().isoformat()
    }
    
    # Create the inbound reply
    # Must match original correlation_id and be a response_to the pending msg
    receipt_msg = MessageEnvelope(
        id=f"msg_{uuid.uuid4().hex}",
        correlation_id=pending_corr_id,
        from_agent=AgentRole.WORKER,
        to_agent=AgentRole.MAIN,
        action=ActionType.EXECUTION_RECEIPT,
        payload=receipt_payload,
        response_to=pending_msg_id
    )
    
    # Process it using the internal reliable handler logic
    # (In real engine, this happens in run_tick -> _send_reliable_message loop)
    # We call _handle_response_logic directly to verify it clears the state
    
    # Mocking the tick event for logging
    class MockTick:
        def add_event(self, *args, **kwargs):
            print(f"   [Tick Log] Event Added: {args}")
            
    mock_tick = MockTick()
    
    # NOTE: _handle_response_logic checks if response matches pending. 
    # But usually it is called with the result of 'target_agent.handle_message'.
    # Here we are simulating that we just GOT the message effectively.
    
    # Let's see if we can use _handle_response_logic. 
    # It takes (response, tick).
    
    # First, verify we are still "Waiting"
    if recovered_agent._rel_state.pending_request is None:
        print("ERROR: Lost pending request before resolution?")
        return

    # Simulate processing
    # Note: _handle_response_logic verifies response validity? 
    # It mainly reset()s the state if success/nack/error.
    
    # However, create_reply usually sets 'response_to'. We manually set it above.
    
    recovered_agent._handle_response_logic(receipt_msg, mock_tick)
    
    if recovered_agent._rel_state.pending_request is None:
        print("SUCCESS: State cleared after processing Receipt.")
        print("Disaster Recovery Verification: PASSED")
    else:
        print("FAILURE: State stuck in Waiting after resolution.")
        print(f"Pending: {recovered_agent._rel_state.pending_request}")

    # Cleanup
    shutil.rmtree(TEST_DATA_DIR)

if __name__ == "__main__":
    main()
