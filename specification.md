# Plan Tool Specification

## Storage & Format

- File Path: `~/plan.txt` (UTF-8 encoding).
- Initialization: Created on the first write operation if it does not exist.
- Line Format: `☐|☒ <number> <description>\n`
- Ordering: Lines are maintained in ascending numeric order.
- Visuals: Hierarchy is conveyed by numbering and Unicode checkboxes (☐ and ☒).
- Empty Lines: Whitespace-only lines are ignored during parsing.

## Task Numbering

- Task numbers are dot-separated integers without leading zeros (e.g., `1`, `1.2`, `1.2.10`).
- Gaps are permitted (e.g., `1` and `3` without `2`).
- A parent task must exist before adding a child task.

### Task States

- All newly added tasks default to incomplete (☐).
- Marking a task complete or incomplete applies only to that specific task, not parents or children.
- Adding or replacing a task sets it to incomplete (☐).

## Old Commands

- `plan`: Prints the entire plan.
- `plan <n>`: Prints task `<n>` and its descendants.
- `plan <n> "<d>" …`: Adds or replaces tasks atomically.
  Pairs are sorted by number before processing so parents are created before children.
- `plan complete <n>`: Marks task `<n>` complete.
- `plan incomplete <n>`: Marks task `<n>` incomplete.
- `plan delete <n>`: Remove task `<n>` and all its descendants.
- `plan --help`: Prints a synopsis of this specification.

## New Commands

- `plan` show entire plan, or act like --help if plan is empty
- `plan ls [id]` show entire plan, or task {id} and its descendants
- `plan add {id} {text...}` add task {id}
- `plan rm {id}` remove task {id} and all its descendants
- `plan edit {id} {new text...}` replace description of task {id}, keep state
- `plan done {id}` mark task {id} complete
- `plan todo {id}` mark task {id} incomplete
- `plan --help` show help

### Argument Parsing

`{text...}` (Auto-joining): Task descriptions do not require quotes. All
arguments provided after the `{id}` are automatically joined with a single
space. For example, `plan add 1 Buy groceries and cook` is parsed as
`{id}="1"` and `{text}="Buy groceries and cook"`.

### Error Semantics

- `add`: error if the ID already exists
- `rm|edit|done|todo|ls <id>`: error if the ID does not exist
- any other malformed usage gives an error

## Exit Codes & Errors

- `0`: Success
- `1`: Error (details printed to standard error, prefixed with `error:`)
