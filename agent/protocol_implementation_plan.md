# Implementation Plan - Protocol Reliability Upgrade

**Goal**: Enhance `agent/src/protocol.py` to support robust, reliable inter-agent communication capable of handling failures, retries, and accurate message tracking.

## Proposed Changes

### 1. Update `MessageEnvelope`
- **Add `response_to`**: Explicit field for request-response pairing (replacing or aliasing `reply_to` for clarity).
- **Add Metadata Fields**:
    - `timeout_ms` (int): Expected processing time before sender gives up.
    - `retry_count` (int): Number of times this message has been retried.
    - `meta` (Dict): For extensible metadata (headers).
- **Enforce `correlation_id`**: Ensure it's always present (already has default factory, but will emphasize propagation).

### 2. Standardized Payloads
- **`ErrorPayload`**: Standard structure for error details (code, message, stack, retryable flag).
- **`ReceiptPayload`**: Standard structure for Acknowledgements (original_msg_id, status).

### 3. ActionType Updates
- Add `ACK` (Acknowledgement) and `NACK` (Negative Acknowledgement) to `ActionType`.
- Define explicit `REQUEST_RESPONSE_MAP` to validate which actions expect which results.

### 4. Helper Updates
- Update `create_reply` to automatically handle `response_to` and `correlation_id` propagation.
- Add `create_ack` and `create_nack` helpers.

## Verification
- **Static Analysis**: Verify Pydantic models validate correctly.
- **Unit Tests**: Create a test script to verify:
    - Envelope creation and defaults.
    - Reply creation propagates correlation_id.
    - ACK/NACK helpers work.
    - Strict mapping validation works.

## Backward Compatibility
- Existing fields will remain (or use aliases).
- Default values will ensure existing code doesn't break immediately, though full reliability requires updating call sites (which is out of scope for *this* specific file update, but the protocol file itself will change).
