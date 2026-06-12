# Plan Tool Specification

## Storage & Format

- File Path: `~/plan.txt` (UTF-8 encoding).
- Initialization: Created on the first write operation if it does not exist.
- Line Format: `☐|☒ <number> "<description>"\n`
- Escaping: Double quotes (`"`) and backslashes (`\`) must be escaped as `\"` and `\\`.
- Ordering: Lines are maintained in ascending numeric order.
- Visuals: Hierarchy is conveyed by numbering and Unicode checkboxes (☐ and ☒).
- Empty Lines: Whitespace-only lines are ignored during parsing.

## Task Numbering

- Task numbers are dot-separated integers without leading zeros (e.g., `1`, `1.2`, `1.2.10`).
- Gaps are permitted (e.g., `1` and `3` without `2`).

### Task States

- All newly added tasks default to incomplete (☐).
- Marking a task complete or incomplete applies only to that specific task, not parents or children.
- Adding or replacing a task sets it to incomplete (☐).

## Commands

- `plan`: Prints the entire plan.
- `plan <n>`: Prints task `<n>` and its descendants.
- `plan <n> "<d>" …`: Adds or replaces tasks atomically.
  Pairs are sorted by number before processing so parents are created before children.
  A parent must exist to add a child.
- `plan complete <n>`: Marks task `<n>` complete.
- `plan incomplete <n>`: Marks task `<n>` incomplete.
- `plan delete <n>`: Deletes task `<n>` and all its descendants.
- `plan --help`: Prints a synopsis of this specification.

## Exit Codes & Errors

- `0`: Success
- `1`: Usage error (bad CLI arguments)
- `2`: Validation error (missing parent, invalid number, task not found)
- `3`: I/O error (file unreadable/unwritable, or format malformed)

*Note: Errors must print to standard error, prefixed with `error:`.*
