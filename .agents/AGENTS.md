# Repository Rules & Constraints

## Database Purity & Testing Isolation Rules

To prevent contamination of clean trading and backtesting historical datasets, all coding agents and developers MUST strictly adhere to the following rules:

1. **Main Database Purity**:
   - The primary databases (`quant_db_prod` and `quant_db`) must be kept strictly pure. Only official, production-ready historical datasets downloaded from RiceQuant (RQData), TqSdk, or iFinD are allowed in these databases.
   - All contract symbols stored in the main database must conform to standard exchange naming conventions and must be in **uppercase** (e.g., `RB2610`, `AG88`, `CF99`).

2. **Testing & Simulation Data Isolation**:
   - **NO** test or simulation data (e.g., mock ticks, temporary bars generated during connection tests, or tick data from CTP gate test runs) should ever be written to the main database.
   - Any test data or symbol mappings containing test suffixes (e.g., `_TQ`, `_CTP`, `_RQ`, `_test`) or lowercase letters (e.g., `rb2610`, `ag00`) must be stored in a dedicated test database (`quant_db_test`) or a local mock database/table.
   - If a test script (such as a Jupyter Notebook or unit test) requires writing or modifying bar data, it must either:
     - Use a local file (e.g., csv, sqlite).
     - Connect to a temporary test database (e.g., `quant_db_test`).
     - Mock the database interface completely using `unittest.mock`.

## Subagent Resource Lifecycle Management Rules

To prevent host resource leaks, context concurrency limit exhaustion, or container crashes (which lead to server restarts and background task loss), all agents MUST strictly follow these subagent lifecycle guidelines:

1. **Explicit Termination**:
   - Subagents do not automatically reclaim resources immediately upon finishing their text response.
   - Once a subagent has completed its task and reported its results to the parent agent, the parent agent MUST immediately call the `manage_subagents` tool with `Action="kill"` and specify the subagent's `ConversationId`.
   
2. **Bulk Reclamation**:
   - At the end of a multi-step task or before concluding a session, the parent agent should verify if any orphan subagents are still active. If so, they must be proactively cleaned up using `manage_subagents` with `Action="kill_all"` or by targeted IDs.
   
3. **Avoid Unnecessary Fan-Out**:
   - Avoid creating excessive concurrent subagents (e.g., more than 3-5 subagents) unless absolutely necessary. Distribute the workload sequentially or use a single subagent for continuous sub-tasks where possible.
