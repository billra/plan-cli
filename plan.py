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


# ==========================================
# Data Model & Tuple Utilities
# ==========================================

class Task:
    """A strictly explicit task. No derived state, no child tracking."""
    def __init__(self, desc, is_done=False):
        self.desc = desc
        self.is_done = is_done

def parse_num(s):
    """Validates and converts a dot-separated string into a tuple of integers."""
    if not re.match(r'^[1-9]\d*(\.[1-9]\d*)*$', s):
        raise PlanError(
            f"invalid task number format: '{s}' "
            f"(expected positive dot-separated integers like '1' or '1.2')"
        )
    return tuple(map(int, s.split('.')))

def stringify(tup):
    """Converts a tuple of integers back into a dot-separated string."""
    return '.'.join(map(str, tup))

def is_descendant(target, candidate):
    """
    Returns True if the candidate is the target itself or a descendant.
    Because tuples match exactly by index, prefix slicing is perfectly accurate.
    """
    return candidate[:len(target)] == target

def get_parent_path(tup):
    """Returns the parent tuple, or an empty tuple if it's a root node."""
    return tup[:-1]


# ==========================================
# Core Engine & Storage Layer
# ==========================================

class PlanManager:
    """Handles disk I/O and atomic dictionary state mutations."""

    def __init__(self, filepath):
        self.filepath = filepath
        self.tasks = {}
        self.load()

    def load(self):
        """Parses the storage file directly into the flat dictionary."""
        if not self.filepath.exists():
            return

        lines = self.filepath.read_text(encoding='utf-8').splitlines()
        for idx, line in enumerate(lines, 1):
            if not line.strip():
                continue

            # Split into exactly 3 parts: State, Path, and Description
            parts = line.split(maxsplit=2)

            if len(parts) != 3 or parts[0] not in ('☐', '☒'):
                raise OSError(
                    f"malformed line {idx} in plan.txt: '{line.strip()}' "
                    f"(expected format: ☐|☒ <number> <description>)"
                )

            state_char, path_str, raw_desc = parts

            # parse_num validates that the path string is strictly numeric
            path = parse_num(path_str)
            desc = raw_desc.strip()

            if not desc:
                raise OSError(f"malformed line {idx} in plan.txt: task description cannot be empty")

            # Strict orphan validation
            parent_path = get_parent_path(path)
            if parent_path and parent_path not in self.tasks:
                raise OSError(
                    f"hierarchy broken at line {idx} in plan.txt: "
                    f"parent task '{stringify(parent_path)}' missing for '{stringify(path)}'"
                )

            self.tasks[path] = Task(desc=desc, is_done=(state_char == '☒'))

    def save(self):
        """Writes the sorted dictionary back to disk."""
        lines = []
        for path, task in sorted(self.tasks.items()):
            state_char = '☒' if task.is_done else '☐'
            lines.append(f'{state_char} {stringify(path)} {task.desc}')

        text = '\n'.join(lines) + '\n' if lines else ''
        self.filepath.write_text(text, encoding='utf-8')

    def transaction(self, action):
        """
        Wraps operations in an atomic transaction. If validation fails halfway
        through a batch command, all changes are rolled back to prevent corruption.
        """
        original_tasks = self.tasks
        self.tasks = copy.deepcopy(self.tasks)
        try:
            action()
        except Exception:
            self.tasks = original_tasks
            raise

    # --- Mutations ---

    def add_or_replace(self, path, desc):
        """
        Assigns a description to a path. Overwrites existing text and
        resets the state to incomplete if the path already exists.
        """
        desc = desc.strip()
        if not desc:
            raise PlanError("task description cannot be empty")

        parent_path = get_parent_path(path)
        if parent_path and parent_path not in self.tasks:
            raise PlanError(
                f"cannot add '{stringify(path)}': "
                f"parent task '{stringify(parent_path)}' does not exist"
            )

        self.tasks[path] = Task(desc=desc, is_done=False)

    def delete(self, target_path):
        """Wipes out a task and strictly removes all descendants to prevent orphans."""
        if target_path not in self.tasks:
            raise PlanError(f"task '{stringify(target_path)}' not found")

        to_delete = [
            path for path in self.tasks
            if is_descendant(target_path, path)
        ]
        for path in to_delete:
            del self.tasks[path]

    def set_state(self, target_path, is_done):
        """Modifies the state of a specific task only (no automagic cascading)."""
        if target_path not in self.tasks:
            raise PlanError(f"task '{stringify(target_path)}' not found")

        self.tasks[target_path].is_done = is_done

    def display(self, target_path=None):
        """Prints the tasks in a flat layout, relying on numbers for hierarchy."""
        visible_tasks = sorted(
            (path, task) for path, task in self.tasks.items()
            if target_path is None or is_descendant(target_path, path)
        )

        if target_path and not visible_tasks:
            raise PlanError(f"task '{stringify(target_path)}' not found")

        for path, task in visible_tasks:
            state_char = '☒' if task.is_done else '☐'
            print(f'{state_char} {stringify(path)} {task.desc}')


# ==========================================
# CLI Dispatcher
# ==========================================

HELP_TEXT = """plan - A Hierarchical Task Manager

Task Numbering:
  • Use dot-separated integers without leading zeros (e.g., 1, 1.2, 1.2.10).
  • Gaps in numbering are permitted (e.g., 1 and 3 without 2).
  • A parent task must exist before adding a child task.

Task States:
  • All newly added tasks default to incomplete.
  • Marking a task as complete or incomplete applies only to that specific task.
  • Adding or replacing a task sets it to incomplete.

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
            return  # Skip saving if we just printed

        case ["--help"]:
            print(HELP_TEXT, end="")
            return

        case ["complete" | "incomplete" as cmd, target]:
            is_done = (cmd == "complete")
            manager.transaction(lambda: manager.set_state(parse_num(target), is_done))

        case ["delete", target]:
            manager.transaction(lambda: manager.delete(parse_num(target)))

        case ["complete" | "incomplete" | "delete" as cmd, *_]:
            raise PlanError(f"'{cmd}' requires exactly 1 argument: a task number")

        case [n] if re.match(r'^[1-9]\d*(\.[1-9]\d*)*$', n):
            manager.display(parse_num(n))
            return  # Skip saving if we just printed

        case _ if len(args) % 2 == 0 and len(args) > 0:
            # Batch Addition: Map pairs, then sort tuples mathematically so
            # parents are always constructed before children, preventing false orphans.
            pairs = [(parse_num(args[i]), args[i+1]) for i in range(0, len(args), 2)]
            pairs.sort(key=lambda x: x[0])

            def batch_upsert():
                for path, desc in pairs:
                    manager.add_or_replace(path, desc)

            manager.transaction(batch_upsert)

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
