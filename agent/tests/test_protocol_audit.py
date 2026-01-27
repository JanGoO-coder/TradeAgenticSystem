import sys
import os

# Ensure agent/src is in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from protocol import (
    MessageEnvelope, ActionType, AgentRole, 
    create_request, create_error_response, ErrorPayload, ReceiptPayload
)
from pydantic import ValidationError

def test_protocol_reliability():
    print("Testing Protocol Reliability Upgrade...")

    # 1. Test Envelope Defaults & Correlation
    msg = create_request(
        AgentRole.MAIN, AgentRole.WORKER, ActionType.SCAN_SETUPS, {}
    )
    assert msg.correlation_id.startswith("session_"), "Default correlation ID missing"
    assert msg.retry_count == 0, "Default retry count wrong"
    print("✅ Envelope Creation OK")

    # 2. Test Response Propagation
    reply = msg.create_reply(ActionType.SETUP_RESULT, {"patterns": []})
    assert reply.correlation_id == msg.correlation_id, "Correlation ID not propagated"
    assert reply.response_to == msg.id, "response_to not set correctly"
    assert reply.from_agent == AgentRole.WORKER, "Role swap failed"
    print("✅ Response Propagation OK")

    # 3. Test Backward Compatibility (Aliases)
    assert reply.reply_to == msg.id, "reply_to alias failed"
    print("✅ Backward Compatibility OK")

    # 4. Test Standard Payloads
    ack = msg.create_ack()
    assert ack.action == ActionType.ACK
    assert ack.payload["status"] == "RECEIVED"
    print("✅ ACK Helper OK")

    nack = msg.create_nack("Busy")
    assert nack.action == ActionType.NACK
    assert nack.payload["status"] == "REJECTED"
    print("✅ NACK Helper OK")

    # 5. Test Error Payload Structure
    err = create_error_response(msg, "Something bad", code="TEST_ERR", retryable=True)
    assert err.payload["code"] == "TEST_ERR"
    assert err.payload["retryable"] is True
    assert err.error == "Something bad", "Backward compat error property failed"
    print("✅ Error Helper OK")

    print("\nALL PROTOCOL TESTS PASSED")

if __name__ == "__main__":
    test_protocol_reliability()
