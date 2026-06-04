# Plan Tool Specification

## Storage & Format

- File Path: `~/plan.txt` (UTF-8 encoding).
- Initialization: If the file does not exist, it is automatically created upon the first write operation.
- Line Format: `☐|☒ <number> "<description>"\n`
- Escaping: Double quotes (`"`) and backslashes (`\`) within descriptions must be escaped as `\"` and `\\`.
- Ordering: Lines are stored and maintained in strict ascending numeric order of `<number>`.
- Visuals: Hierarchy is conveyed purely by numbering. No indentation or ASCII fallback is permitted; the specific Unicode checkboxes (☐ and ☒) are required.

## Hierarchy & Numbering

- Format: Dot-separated positive integers with no leading zeros (e.g., `1.2.10`).
- Continuity: Gaps are strictly invalid at all times, including the root level. An empty file must begin with task `1`. Within any sibling set, segments must be strictly consecutive (e.g., `1.1`, `1.2`, `1.3`).
- Tree Shifting: When a task's number shifts due to insertion or deletion, its entire subtree shifts uniformly. For example, if task `1.2` is renumbered to `1.3`, its child `1.2.1` becomes `1.3.1`.

## State Propagation (Bubble Rules)

- Marking Complete (☒): Propagates *down* (all descendants become complete) and *up* (ancestors become complete only if every one of their children is now complete).
- Marking Incomplete (☐): Propagates *down* (all descendants become incomplete) and *up* (all ancestors are immediately marked incomplete).

## Commands

- `plan`: Prints the entire file.
- `plan <n>`: Prints task `<n>` and all its descendants.
- `plan <n> "<d>" …`: Adds or replaces one or more tasks. The entire invocation is atomic (validates all pairs before writing). A parent must exist to add a child. If `<n>` already exists, its description is updated, its state is reset to incomplete (☐), and this incomplete state bubbles up to all ancestors.
- `plan complete <n>`: Marks `<n>` complete and applies the Complete State Propagation rules.
- `plan incomplete <n>`: Marks `<n>` incomplete and applies the Incomplete State Propagation rules.
- `plan insert <n> "<d>"`: Inserts a new task at `<n>`. The existing `<n>` and all subsequent siblings are renumbered by +1 on their final segment. Subtrees shift accordingly.
- `plan delete <n>`: Deletes `<n>` and its descendants. All subsequent siblings are renumbered by -1 on their final segment to close the gap. Subtrees shift accordingly.
- `plan --help`: Prints a concise synopsis of this specification.

## Exit Codes & Errors

- `0`: Success
- `1`: Usage error (bad CLI arguments)
- `2`: Validation error (missing parent, gap detected, invalid number)
- `3`: I/O error (file unreadable/unwritable, ignoring initial creation)

*Note: All error messages must be printed to standard error and prefixed strictly with `error:` (e.g., `error: sibling gap - expected 1.4`).*
