# Audit of agent/src/protocol.py

**Date:** 2026-01-27
**Scope:** Deep scan of `agent/src/protocol.py` for reliability and robustness issues.

## Executive Summary
The current protocol definition provides a basic data structure for inter-agent communication but lacks critical features for a robust, production-grade distributed trading system. While the schema exists, the mechanisms to enforce reliability, traceability, and determinism are missing.

## Identified Weaknesses

### 1. Missing Message Acknowledgements
*   **Analysis**: The protocol relies on application-level responses (e.g., `SNAPSHOT_RESULT` in response to `GET_SNAPSHOT`). There is no transport-level or protocol-level acknowledgement (ACK) to confirm that a message was *received* and *enqueued* for processing.
*   **Impact**:
    *   **"Fire and Forget" Risk**: struct `ActionType` definitions imply a happy-path request-response. If a `EXECUTE_ORDER` message is dropped (network glitch, worker crash), the Sender (Main) has no immediate way to know it failed initiating.
    *   **Ambiguous State**: In `ADVANCE_TIME`, ignoring a dropped message leads to simulation desynchronization.

### 2. Missing Failure Responses
*   **Analysis**:
    *   The protocol defines a single generic `ERROR` action type.
    *   There are no specific failure types (e.g., `ORDER_REJECTED`, `TIMEOUT`, `INVALID_STATE`, `DATA_UNAVAILABLE`).
    *   `create_error_response` wraps the original action, but the receiver must parse the generic error string to decide logic.
*   **Impact**:
    *   Fragile error handling logic (string matching).
    *   Inability to distinguish between transient errors (retryable) and fatal errors (abort).

### 3. Weak Correlation ID Usage
*   **Analysis**:
    *   `correlation_id` field exists in `MessageEnvelope`, but `create_request` helper generates a **new** ID by default unless one is manually passed.
    *   There is no enforcement or automated context propagation. If a Strategy triggers a scan which triggers an order, the `EXECUTE_ORDER` will likely have a brand new `correlation_id` unrelated to the `SCAN_SETUPS` request.
*   **Impact**:
    *   **Broken Traceability**: Impossible to trace a specific Trade Execution back to the specific Market Signal that caused it in logs.
    *   **Orphaned Messages**: Responses cannot be reliably matched to requests if the ID chain is broken.

### 4. Lack of Timeouts or Retries
*   **Analysis**:
    *   The `MessageEnvelope` schema contains `timestamp` but lacks:
        *   `expiration` or `ttl` (Time To Live).
        *   `retry_count`.
        *   `timeout_ms` expectation.
*   **Impact**:
    *   **Deadlocks**: If a Worker hangs, the generic Main loop has no protocol-level signal to stop waiting.
    *   **Race Conditions**: A retried order (after a delay) might arrive alongside the original delayed order, causing double execution (duplicate trades) because there is no idempotency key or retry counter handling.

### 5. Ambiguous ActionType Usage
*   **Analysis**:
    *   `SCAN_SETUPS`: Categorized as "Main → Worker", implying the Worker performs strategy pattern matching. Typically, Pattern Recognition is a **Strategy** concern.
    *   `CLOSE_POSITION`: No explicit Result type defined (e.g., `POSITION_CLOSED` vs `EXECUTION_RECEIPT`). Behaving implicitly is risky.
    *   `ADVANCE_TIME`: A Simulation-only command exists alongside Live-critical commands (`EXECUTE_ORDER`) in the same enum.
*   **Impact**:
    *   **Safety Risk**: Sending `ADVANCE_TIME` to a Live Trading adapter could effectively act as a remote kill-switch or be ignored, leading to undefined behavior.

## Risk Assessment

### Risks During Live Trading
1.  **Ghost Orders**: Without ACKs + Timeouts, the Main agent might retry an `EXECUTE_ORDER` thinking the first was lost, potentially doubling position size.
2.  **Hang/Freeze**: A single unresponsive component (e.g., Data Vendor API down) causes the Main agent to wait indefinitely for `SNAPSHOT_RESULT`, missing market moves.
3.  **Fatal Logic Errors**: Generic `ERROR` responses might be treated as "no data" rather than "critical failure," causing the bot to trade on stale or empty data.

### Risks During Backtesting
1.  **Causality Violations**: If `ADVANCE_TIME` is not strictly acknowledged before the next step, the simulation might proceed before indicators are calculated, leading to "look-ahead bias" or non-deterministic results.
2.  **Audit Blindness**: In a 10-year backtest, finding *why* a specific bad trade happened is nearly impossible without strictly propagated Correlation IDs linking the specific Candle -> Signal -> Order -> Execution chain.
