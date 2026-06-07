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

### Bubble Rules (State Propagation)

- State Initialization: All newly added or inserted tasks default to incomplete (☐).
- Downward Propagation: Whenever a task is explicitly marked complete/incomplete, or reset to incomplete during a text update, its entire subtree is forced uniformly into that same state.
- Upward Propagation: Whenever a task is mutated (state change, addition, or deletion), its parent's state is re-evaluated and cascaded up the ancestor chain:
  - Incomplete (☐): An ancestor becomes incomplete if *any* of its children are incomplete.
  - Complete (☒): An ancestor becomes complete if *all* of its children are complete.
  - Childless: An ancestor's state is preserved without change if it becomes childless due to a deletion.

## Commands

- `plan`: Prints the entire file.
- `plan <n>`: Prints task `<n>` and all its descendants.
- `plan <n> "<d>" …`: Adds or replaces one or more tasks. The entire invocation is atomic (validates all pairs before writing). Multiple pairs can be provided in any order; the tool mathematically sorts them before processing (e.g., `1` is processed before `1.1`) so parents are safely created before their children. A parent must exist to add a child. If `<n>` already exists, its description is updated, its state is reset to incomplete (☐), and this incomplete state applies the Incomplete Bubble Rules.
- `plan complete <n>`: Marks `<n>` complete and applies the Complete Bubble Rules.
- `plan incomplete <n>`: Marks `<n>` incomplete and applies the Incomplete Bubble Rules.
- `plan insert <n> "<d>"`: Inserts a new task at `<n>`. The existing `<n>` and all subsequent siblings are renumbered by +1 on their final segment.
- `plan delete <n>`: Deletes `<n>` and its descendants. All subsequent siblings are renumbered by -1 on their final segment to close the gap.
- `plan --help`: Prints a concise synopsis of this specification.

## Exit Codes & Errors

- `0`: Success
- `1`: Usage error (bad CLI arguments)
- `2`: Validation error (missing parent, gap detected, invalid number)
- `3`: I/O error (file unreadable/unwritable, or contains malformed lines failing the strict format, aborting to prevent data corruption).

*Note: All error messages must be printed to standard error and prefixed strictly with `error:` (e.g., `error: sibling gap - expected 1.4`).*
