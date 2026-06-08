# Plan Tool Specification

## Storage & Format

- File Path: `~/plan.txt` (UTF-8 encoding).
- Initialization: If the file does not exist, it is automatically created upon the first write operation.
- Line Format: `☐|☒ <number> "<description>"\n`
- Escaping: Double quotes (`"`) and backslashes (`\`) within descriptions must be escaped as `\"` and `\\`.
- Ordering: Lines are stored and maintained in strict ascending numeric order of `<number>`.
- Visuals: Hierarchy is conveyed purely by numbering. No indentation or ASCII fallback is permitted; the specific Unicode checkboxes (☐ and ☒) are required.
- Empty Lines: Empty or whitespace-only lines within the storage file are silently ignored during parsing.

## Hierarchy & Numbering

- Format: Dot-separated positive integers with no leading zeros (e.g., `1.2.10`).
- Continuity: Gaps are strictly invalid at all times, including the root level. An empty file must begin with task `1`. Within any sibling set, segments must be strictly consecutive (e.g., `1.1`, `1.2`, `1.3`).
- Tree Shifting: When a task's number shifts due to insertion or deletion, its entire subtree shifts uniformly. For example, if task `1.2` is renumbered to `1.3`, its child `1.2.1` becomes `1.3.1`.

### State Management

- State Initialization: All newly added or inserted tasks default to incomplete (☐).
- Derived Upward State: A parent task does not store its own independent state. Its state is dynamically derived: a parent is complete *if and only if* all of its children are complete. (Consequently, adding a new incomplete child to a completed parent renders the parent incomplete).
- Explicit Downward State: Whenever a task is set to be complete/incomplete via CLI, that state is applied to the task and every descendant in its subtree.
- Childless Deletion (Snapshot Rule): If deleting a task leaves its parent entirely childless, the parent keeps the state it held immediately prior to the deletion.

## Commands

- `plan`: Prints the entire file.
- `plan <n>`: Prints task `<n>` and all its descendants.
- `plan <n> "<d>" …`: Adds or replaces one or more tasks. The entire invocation is atomic (validates all pairs before writing). Multiple pairs can be provided in any order; the tool mathematically sorts them before processing (e.g., `1` is processed before `1.1`) so parents are safely created before their children. A parent must exist to add a child. If `<n>` already exists, its description is updated and its state is reset to incomplete (☐).
- `plan complete <n>`: Marks `<n>` complete and applies this state to all its descendants.
- `plan incomplete <n>`: Marks `<n>` incomplete and applies this state to all its descendants.
- `plan insert <n> "<d>"`: Inserts a new task at `<n>`. The existing `<n>` and all subsequent siblings are renumbered by +1 on their final segment.
- `plan delete <n>`: Deletes `<n>` and its descendants. All subsequent siblings are renumbered by -1 on their final segment to close the gap.
- `plan --help`: Prints a concise synopsis of this specification.

## Exit Codes & Errors

- `0`: Success
- `1`: Usage error (bad CLI arguments)
- `2`: Validation error (missing parent, gap detected, invalid number)
- `3`: I/O error (file unreadable/unwritable, or contains malformed lines failing the strict format, aborting to prevent data corruption).

*Note: All error messages must be printed to standard error and prefixed strictly with `error:` (e.g., `error: sibling gap - expected 1.4`).*
