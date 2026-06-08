# Plan Tool Specification

## Storage & Format

- File Path: `~/plan.txt` (UTF-8 encoding).
- Initialization: Created on the first write operation if it does not exist.
- Line Format: `☐|☒ <number> "<description>"\n`
- Escaping: Double quotes (`"`) and backslashes (`\`) must be escaped as `\"` and `\\`.
- Ordering: Lines are maintained in ascending numeric order.
- Visuals: Hierarchy is conveyed by numbering and Unicode checkboxes (☐ and ☒).
- Empty Lines: Whitespace-only lines are ignored during parsing.

## Structure & Continuity

- Format: Dot-separated integers without leading zeros (e.g., `1`, `1.2`, `1.2.10`).
- Continuity: Gaps are invalid. Siblings must be consecutive. A blank plan starts at `1`.
- Shifting: Inserting or deleting a task shifts subsequent siblings and their subtrees uniformly (+1 or -1).

### Task States

- Initialization: All newly added or inserted tasks default to incomplete (☐).
- Downward: Marking a task complete or incomplete applies that state to all its descendants.
- Upward: The parent is derived. It is complete only if all its subtasks are complete.
- Mutations: Adding or replacing a task sets it to incomplete (☐).
- Deletion: Deleting a task's only child leaves the parent's state unchanged.

## Commands

- `plan`: Prints the entire plan.
- `plan <n>`: Prints task `<n>` and its descendants.
- `plan <n> "<d>" …`: Adds or replaces tasks atomically. Pairs are sorted by number before processing so parents are created before children. A parent must exist to add a child.
- `plan complete <n>`: Marks `<n>` and its descendants complete.
- `plan incomplete <n>`: Marks `<n>` and its descendants incomplete.
- `plan insert <n> "<d>"`: Inserts a task at `<n>`. Existing `<n>` and subsequent siblings shift right (+1).
- `plan delete <n>`: Deletes `<n>` and its descendants. Subsequent siblings shift left (-1).
- `plan --help`: Prints a synopsis of this specification.

## Exit Codes & Errors

- `0`: Success
- `1`: Usage error (bad CLI arguments)
- `2`: Validation error (missing parent, gap detected, invalid number)
- `3`: I/O error (file unreadable/unwritable, or format malformed)

*Note: Errors must print to standard error, prefixed with `error:`.*
