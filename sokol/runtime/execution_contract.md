# Sokol Execution Contract

## State Model Architecture (STRICT NORMALIZATION)

### Two State Layers (Mathematically Separated)

**1. Execution State (Temporary)**
- During pipeline execution
- Intermediate states (THINKING, EXECUTING, WAITING_CONFIRM)
- Can have intermediate commits for error recovery
- NOT final until commit_state()
- Gate: Ends at final commit_state() call

**2. Committed State (Final)**
- After commit_state() call
- Reflects completed execution only
- Single final commit point per execution
- Cannot be rolled back
- Gate: Begins at final commit_state() call

### Safety Model (NOT a State Layer)

**Safety = Interrupt → Abort Pipeline → No Commit**
- Emergency stop: interrupt execution, cancel tasks, NO state mutation
- Watchdog: monitor for stuck states, cancel tasks, NO state mutation
- Safety does NOT use rollback_state() or state transitions
- Safety is NOT a state layer - it's an interrupt mechanism
- State mutation ONLY through commit_state()

### State Mutation Gates

**Execution Gate:** Where Execution State ends
- Final commit_state() call in orchestrator
- Line 5475 in orchestrator.py (successful execution)
- Transitions from Execution State to Committed State

**Commit Gate:** Where Committed State begins
- After final commit_state() succeeds
- Before response formatting
- State is now immutable for this execution

**Single Mutation Gate:**
- commit_state() is the ONLY state mutation point
- No rollback_state() (removed - breaks determinism)
- No safety state transitions (safety is interrupt only)

## Single Execution Flow Contract

### Required Execution Flow
```
Input
  ↓
Router (Result[ProposedAction])
  ↓
State pre-check (Result[bool])
  ↓
Execution (Result[AgentResponse])
  ↓
State commit (commit_state() → Result[bool])
  ↓
Response return (Result[AgentResponse])
```

### Contract Rules

**No Callbacks in Execution Path**
- Response delivery via return values only
- No side effects in execution path
- Single controlled flow

**No None Runtime**
- All functions must return Result[T]
- No Optional returns in execution path
- Structured errors only

**State = Reality (CORE INVARIANT)**
- State must reflect actual system state
- No state mutation outside commit_state()
- State commit happens exactly once per execution

**No Hidden Behavior**
- No silent failures
- No implicit defaults
- No fallback execution on error

## State Commit Point

### Definition
`commit_state(result: Result[AgentResponse]) → Result[bool]` is the ONLY function that can change state.

### Rules
- No state mutation allowed outside commit_state()
- State commit happens exactly once per execution
- State commit happens AFTER execution, BEFORE response
- State is NOT committed on error

### Implementation Location
File: `runtime/state.py`
Function: `def commit_state(result: Result[AgentResponse]) -> Result[bool]`

## Failure Contract Path

### Error Handling Rules
- Any `Result.error()` stops execution pipeline immediately
- No fallback execution allowed on error
- State is NOT committed on error
- Response contains error info, no execution continues
- No silent error recovery

### Error Flow
```
Router error → stop, return error response
State error → stop, return error response, no commit
Execution error → stop, return error response, no commit
Response error → return error response, no commit
```

## Callback Bridge Rules (PHASE A Only)

### Bridge Mode Definition
- Callbacks are READ-ONLY mirrors of Result stream
- Result stream is source of truth
- Callbacks exist only for PHASE A compatibility with UI layer
- Callbacks MUST be removed in PHASE C
- No new data flow through callbacks in PHASE A

### Bridge Implementation
- Callbacks call Result channel functions
- Result channel functions return Result[T]
- UI layer reads from Result channel in PHASE C
- Callbacks deprecated in PHASE A, removed in PHASE C

## Execution Guarantees

### Invariant Block - Always True

1. **Exactly one router result per input**
   - Single router decision per user input
   - No parallel routing paths

2. **Exactly one state commit per execution**
   - State commits exactly once
   - No partial commits
   - No rollback commits

3. **No state mutation outside commit_state()**
   - Only commit_state() can change state
   - No direct state._state assignments
   - No bypass methods

4. **No response after state commit**
   - Response returned after state commit
   - No post-response state changes
   - No post-response execution

5. **No execution after error**
   - Result.error() stops pipeline immediately
   - No fallback execution
   - No silent error recovery

6. **No None returns in execution path**
   - All functions return Result[T]
   - No Optional returns
   - Structured errors only

7. **No side effects in execution path**
   - Response delivery via return values only
   - No callback side effects
   - No external emission

8. **Single output sink for responses**
   - All responses go through single channel
   - No dual emission paths
   - No parallel output streams

## Phase 5 Verification Results (STRICT NORMALIZATION)

### Linear Execution Pipeline Verified ✅

**Execution Flow:**
```
Input → Router → Execution → (SUCCESS → commit_state → RESPONSE) → (FAILURE → abort, NO commit)
```

**commit_state() Locations:**
1. Line 2643: Intermediate commit (Execution State) - confirmation flow
2. Line 5475: FINAL commit (Committed State) - after successful execution
3. Line 5505: Error handling commit - error recovery path

**State Mutations:**
- commit_state() is the ONLY state mutation point ✅
- rollback_state() REMOVED (was breaking determinism)
- No direct state._state assignments in execution path
- force_transition() REMOVED from execution path (safety is interrupt only)

**Safety Model (NOT State Layer):**
- emergency_stop: interrupt execution, cancel tasks, NO state mutation ✅
- watchdog: monitor for stuck states, cancel tasks, NO state mutation ✅
- Safety does NOT use rollback_state() or state transitions ✅
- Safety = interrupt → abort pipeline → no commit ✅

**Event Emissions:**
- USER_INPUT event moved to post-commit observer (line 5479)
- CONFIRM_REQUEST events remain in execution path (UI flow requirement)
- EMERGENCY_STOP event as safety interrupt (no state mutation)
- No event emissions during critical execution path that could cause side effects

**Response Emissions:**
- All responses go through Result channels (single output sink)
- No callback emissions in execution path
- Response formatting happens after state commit
- No response emissions before final commit

**Single Mutation Gate Verified:**
- commit_state() is the ONLY state mutation point ✅
- No rollback_state() (removed) ✅
- No safety state transitions (safety is interrupt only) ✅
- No force_transition() in execution path ✅
