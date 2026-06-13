#!/usr/bin/env python3
"""
plan - A hierarchical, fixed-ID task manager.
Maintains an ordered structure of independent tasks in ~/plan.txt.
"""

import sys
import re
import copy
from pathlib import Path

class PlanError(Exception): pass

# Global pattern for validation
PATH_RE = re.compile(r'^[1-9]\d*(\.[1-9]\d*)*$')

# ==========================================
# Tuple Utilities
# ==========================================

def parse_num(s):
    """Validates and converts a dot-separated string into a tuple of integers."""
    if not PATH_RE.match(s):
        raise PlanError(
            f"invalid task number format: '{s}' "
            f"(expected positive dot-separated integers like '1' or '1.2')"
        )
    return tuple(map(int, s.split('.')))

def stringify(tup):
    """Converts a tuple of integers back into a dot-separated string."""
    return '.'.join(map(str, tup))

def is_descendant(target, candidate):
    """Returns True if the candidate is the target itself or a descendant."""
    return len(candidate) >= len(target) and candidate[:len(target)] == target


# ==========================================
# Core Engine & Storage Layer
# ==========================================

class PlanManager:
    """Handles disk I/O and atomic dictionary state mutations."""

    def __init__(self, filepath):
        self.filepath = filepath
        # Tasks stored as: { path_tuple: {"desc": str, "is_done": bool} }
        self.tasks = {}
        self.load()

    def load(self):
        """Parses the storage file directly into the flat dictionary."""
        if not self.filepath.exists():
            return

        for idx, line in enumerate(self.filepath.read_text(encoding='utf-8').splitlines(), 1):
            if not line.strip():
                continue

            parts = line.split(maxsplit=2)
            if len(parts) != 3 or parts[0] not in ('☐', '☒'):
                raise OSError(
                    f"malformed line {idx} in plan.txt: '{line.strip()}' "
                    f"(expected format: ☐|☒ <number> <description>)"
                )

            state_char, path_str, raw_desc = parts
            path = parse_num(path_str)
            desc = raw_desc.strip()

            if not desc:
                raise OSError(f"malformed line {idx} in plan.txt: task description cannot be empty")

            # Strict orphan validation
            if (parent := path[:-1]) and parent not in self.tasks:
                raise OSError(
                    f"hierarchy broken at line {idx} in plan.txt: "
                    f"parent task '{stringify(parent)}' missing for '{stringify(path)}'"
                )

            self.tasks[path] = {"desc": desc, "is_done": state_char == '☒'}

    def save(self):
        """Writes the sorted dictionary back to disk."""
        lines = [
            f"{'☒' if task['is_done'] else '☐'} {stringify(path)} {task['desc']}"
            for path, task in sorted(self.tasks.items())
        ]
        self.filepath.write_text('\n'.join(lines) + '\n' if lines else '', encoding='utf-8')

    def transaction(self, action):
        """Wraps operations in an atomic transaction."""
        original_tasks = self.tasks
        self.tasks = copy.deepcopy(self.tasks)
        try:
            action()
        except Exception:
            self.tasks = original_tasks
            raise

    def add_or_replace(self, path, desc):
        """Assigns a description to a path, resetting state to incomplete."""
        if not (desc := desc.strip()):
            raise PlanError("task description cannot be empty")

        if (parent := path[:-1]) and parent not in self.tasks:
            raise PlanError(f"cannot add '{stringify(path)}': parent task '{stringify(parent)}' does not exist")

        self.tasks[path] = {"desc": desc, "is_done": False}

    def delete(self, target_path):
        """Wipes out a task and its descendants."""
        if target_path not in self.tasks:
            raise PlanError(f"task '{stringify(target_path)}' not found")

        self.tasks = {
            path: task for path, task in self.tasks.items()
            if not is_descendant(target_path, path)
        }

    def set_state(self, target_path, is_done):
        """Modifies the state of a specific task only."""
        if target_path not in self.tasks:
            raise PlanError(f"task '{stringify(target_path)}' not found")

        self.tasks[target_path]["is_done"] = is_done

    def display(self, target_path=None):
        """Prints the tasks in a flat layout."""
        visible = sorted(
            (path, task) for path, task in self.tasks.items()
            if target_path is None or is_descendant(target_path, path)
        )

        if target_path and not visible:
            raise PlanError(f"task '{stringify(target_path)}' not found")

        for path, task in visible:
            print(f"{'☒' if task['is_done'] else '☐'} {stringify(path)} {task['desc']}")


# ==========================================
# CLI Dispatcher
# ==========================================

HELP_TEXT = """plan - A Hierarchical Task Manager

Task Numbering:
  • Use dot-separated integers without leading zeros (e.g., 1, 1.2, 1.2.10).
  • Gaps in numbering are permitted (e.g., 1 and 3 without 2).
  • A parent task must exist before adding a child task.

Commands:
  plan                    Show the entire plan.
  plan <n>                Show task <n> and its descendants.
  plan <n> "<desc>" ...   Add or replace tasks.
  plan complete <n>       Mark task <n> complete.
  plan incomplete <n>     Mark task <n> incomplete.
  plan delete <n>         Remove task <n> and all its descendants.
  plan --help             Show this help.
"""

def dispatch(plan_file, args):
    manager = PlanManager(plan_file)

    match args:
        case []:
            manager.display()
            return

        case ["--help"]:
            print(HELP_TEXT, end="")
            return

        case ["complete" | "incomplete" as cmd, target]:
            manager.transaction(lambda: manager.set_state(parse_num(target), cmd == "complete"))

        case ["delete", target]:
            manager.transaction(lambda: manager.delete(parse_num(target)))

        case ["complete" | "incomplete" | "delete" as cmd, *_]:
            raise PlanError(f"'{cmd}' requires exactly 1 argument: a task number")

        case [n] if PATH_RE.match(n):
            manager.display(parse_num(n))
            return

        case _ if len(args) % 2 == 0 and len(args) > 0:
            pairs = sorted(
                ((parse_num(args[i]), args[i+1]) for i in range(0, len(args), 2)),
                key=lambda pair: pair[0]
            )
            manager.transaction(
                lambda: [manager.add_or_replace(path, desc) for path, desc in pairs]
            )

        case _:
            raise PlanError(f"unrecognized command or invalid arguments: '{' '.join(args)}'")

    manager.save()

def main():
    try:
        dispatch(Path('~/plan.txt').expanduser(), sys.argv[1:])
    except (PlanError, OSError) as e:
        sys.exit(f"error: {e}")

if __name__ == '__main__':
    main()
