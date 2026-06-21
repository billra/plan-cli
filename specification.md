# Plan Tool Specification

## Storage & Format

- File Path: `~/plan.txt` (UTF-8 encoding).
- Initialization: Created on the first write operation if it does not exist.
- Line Format: `☐|☒ <number> <description>`
- Ordering: Lines are maintained in ascending numeric order.
- Visuals: Hierarchy is conveyed by numbering and Unicode checkboxes (`☐` and `☒`).
- Empty Lines: Whitespace-only lines are ignored during parsing.
- Validation: Loading the file checks for orphaned tasks (a child existing
  without its parent) and raises an error if found to prevent state corruption.

## Task Numbering

- Task numbers are dot-separated integers without leading zeros (e.g., `1`, `1.2`, `1.2.10`).
- Gaps are permitted (e.g., `1` and `3` without `2`).
- A parent task must exist before adding a child task.

### Task States

- All newly added tasks default to incomplete (`☐`).
- Marking a task complete or incomplete applies only to that specific task, not parents or children.
- Editing a task's description maintains its current completion state.

## Commands

- `plan` show entire plan (or act like `--help` if plan is empty)
- `plan ls [<id>]` show entire plan, or task `<id>` and its descendants
- `plan add <id> <text...>` add task `<id>`
- `plan rm <id>` remove task `<id>` and all its descendants
- `plan edit <id> <text...>` replace description of task `<id>`, keeping current state
- `plan done <id>` mark task `<id>` complete
- `plan todo <id>` mark task `<id>` incomplete
- `plan --help` show help

### Argument Parsing

`<text...>` (Auto-joining): Task descriptions do not require quotes. All
arguments provided after the `<id>` are automatically joined with a single
space. For example, `plan add 1 Buy groceries and cook` is parsed as
`<id>="1"` and `<text...>="Buy groceries and cook"`.

### Error Semantics

- `add`: error if the ID already exists or if the description is empty.
- `edit`: error if the ID does not exist or if the new description is empty.
- `rm|done|todo|ls <id>`: error if the ID does not exist.
- Any other malformed usage gives an error.

## Exit Codes & Errors

- `0`: Success
- `1`: Error (details printed to standard error, prefixed with `error:`)
