#!/usr/bin/env python3
"""
plan - A hierarchical, fixed-ID task manager.
Maintains an ordered structure of independent tasks in ~/plan.txt.
"""

import sys
import re
import copy
from pathlib import Path
from dataclasses import dataclass
from typing import Dict, Tuple, List, Callable

class UsageError(Exception): pass
class ValidationError(Exception): pass


# ==========================================
# Data Model & Tuple Utilities
# ==========================================

@dataclass
class Task:
    """A strictly explicit task. No derived state, no child tracking."""
    desc: str
    is_done: bool = False

def parse_num(s: str) -> Tuple[int, ...]:
    """Validates and converts a dot-separated string into a tuple of integers."""
    if not re.match(r'^[1-9]\d*(\.[1-9]\d*)*$', s):
        raise ValidationError(
            f"invalid task number format: '{s}' "
            f"(expected positive dot-separated integers like '1' or '1.2')"
        )
    return tuple(map(int, s.split('.')))

def stringify(tup: Tuple[int, ...]) -> str:
    """Converts a tuple of integers back into a dot-separated string."""
    return '.'.join(map(str, tup))

def is_descendant(target: Tuple[int, ...], candidate: Tuple[int, ...]) -> bool:
    """
    Returns True if the candidate is the target itself or a descendant.
    Because tuples match exactly by index, prefix slicing is perfectly accurate.
    """
    return candidate[:len(target)] == target

def get_parent_path(tup: Tuple[int, ...]) -> Tuple[int, ...]:
    """Returns the parent tuple, or an empty tuple if it's a root node."""
    return tup[:-1]


# ==========================================
# Core Engine & Storage Layer
# ==========================================

class PlanManager:
    """Handles disk I/O and atomic dictionary state mutations."""

    def __init__(self, filepath: Path):
        self.filepath = filepath
        self.tasks: Dict[Tuple[int, ...], Task] = {}
        self.load()

    def load(self):
        """Parses the storage file directly into the flat dictionary."""
        if not self.filepath.exists():
            return

        lines = self.filepath.read_text(encoding='utf-8').splitlines()
        for idx, line in enumerate(lines, 1):
            if not line.strip():
                continue

            match = re.match(r'^([☐☒])\s+([1-9]\d*(?:\.[1-9]\d*)*)\s+"(.*)"$', line)
            if not match:
                raise OSError(
                    f"malformed line {idx} in plan.txt: '{line.strip()}' "
                    f"(expected format: ☐|☒ <number> \"<description>\")"
                )

            state_char, path_str, raw_desc = match.groups()
            path = parse_num(path_str)
            desc = raw_desc.replace('\\"', '"').replace('\\\\', '\\')

            # Strict Orphan Validation (Protects against manual file corruption)
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
        # Python natively sorts tuples mathematically (e.g., (1, 2) before (1, 10))
        for path, task in sorted(self.tasks.items()):
            state_char = '☒' if task.is_done else '☐'
            desc_esc = task.desc.replace('\\', '\\\\').replace('"', '\\"')
            lines.append(f'{state_char} {stringify(path)} "{desc_esc}"')

        text = '\n'.join(lines) + '\n' if lines else ''
        self.filepath.write_text(text, encoding='utf-8')

    def transaction(self, action: Callable[[], None]):
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

    def add_or_replace(self, path: Tuple[int, ...], desc: str):
        """
        Assigns a description to a path. Overwrites existing text and
        resets the state to incomplete if the path already exists.
        """
        parent_path = get_parent_path(path)
        if parent_path and parent_path not in self.tasks:
            raise ValidationError(
                f"cannot add '{stringify(path)}': "
                f"parent task '{stringify(parent_path)}' does not exist"
            )

        self.tasks[path] = Task(desc=desc, is_done=False)

    def delete(self, target_path: Tuple[int, ...]):
        """Wipes out a task and strictly removes all descendants to prevent orphans."""
        if target_path not in self.tasks:
            raise ValidationError(f"task '{stringify(target_path)}' not found")

        to_delete = [
            path for path in self.tasks
            if is_descendant(target_path, path)
        ]
        for path in to_delete:
            del self.tasks[path]

    def set_state(self, target_path: Tuple[int, ...], is_done: bool):
        """Modifies the state of a specific task only (no automagic cascading)."""
        if target_path not in self.tasks:
            raise ValidationError(f"task '{stringify(target_path)}' not found")

        self.tasks[target_path].is_done = is_done

    def display(self, target_path: Tuple[int, ...] = None):
        """Prints the tasks in a calculated hierarchical layout."""
        visible_tasks = sorted(
            (path, task) for path, task in self.tasks.items()
            if target_path is None or is_descendant(target_path, path)
        )

        if target_path and not visible_tasks:
            raise ValidationError(f"task '{stringify(target_path)}' not found")

        for path, task in visible_tasks:
            state_char = '☒' if task.is_done else '☐'
            indent = '  ' * (len(path) - 1)
            print(f'{indent}{state_char} {stringify(path)} "{task.desc}"')


# ==========================================
# CLI Dispatcher
# ==========================================

HELP_TEXT = """plan - A Hierarchical Task Manager

Structure & Continuity:
  • Numbering uses dot-separated integers without leading zeros (e.g., 1, 1.2, 1.2.10).
  • Gaps are completely legal (e.g., you can have 1 and 3 without a 2).
  • A parent task must exist before you can add a child task.

Task States:
  • State is entirely decoupled. Completing a parent does not complete its children.
  • Marking a task complete or incomplete applies ONLY to that exact task.
  • Adding or replacing a task sets it to incomplete.
  • Deleting a task structurally wipes out that task and all of its descendants.

Commands:
  plan                  Print the entire plan.
  plan <n>              Print task <n> and its descendants.
  plan <n> "<desc>" ... Add or replace tasks. (Use \\" and \\\\ to escape text).
  plan complete <n>     Mark exactly <n> complete.
  plan incomplete <n>   Mark exactly <n> incomplete.
  plan delete <n>       Delete <n> and strictly wipe all of its descendants.
  plan --help           Print this help text.
"""

def dispatch(plan_file: Path, args: List[str]):
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
            raise UsageError(f"'{cmd}' requires exactly 1 argument: a task number")

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
            raise UsageError(f"unrecognized command or invalid arguments: '{' '.join(args)}'")

    manager.save()

def main():
    try:
        dispatch(Path('~/plan.txt').expanduser(), sys.argv[1:])
    except (UsageError, ValidationError, OSError) as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit({UsageError: 1, ValidationError: 2, OSError: 3}.get(type(e), 1))

if __name__ == '__main__':
    main()
