#!/usr/bin/env python3
"""
plan - A hierarchical task manager.
Maintains an ordered, tree-like structure of tasks in ~/plan.txt.
"""

import sys
import re
from pathlib import Path

# --- Constants & Configuration ---
PLAN_FILE = Path('~/plan.txt').expanduser()
CHECK_INCOMPLETE = '☐'
CHECK_COMPLETE = '☒'

# Exit codes
EXIT_SUCCESS = 0
EXIT_USAGE = 1
EXIT_VALIDATION = 2
EXIT_IO = 3


# --- Error Handling ---
class UsageError(Exception):
    """Raised for invalid CLI arguments."""

class ValidationError(Exception):
    """Raised for invalid data state (gaps, missing parents, invalid numbers)."""

def abort(code, message):
    """Prints an error to stderr and exits with the specified code."""
    print(f"error: {message}", file=sys.stderr)
    sys.exit(code)


# --- Helper Functions ---
def parse_num(num_str):
    """
    Validates and converts a string number (e.g., '1.2.10') into a tuple of ints.
    Enforces positive integers and no leading zeros.
    """
    if not re.match(r'^[1-9]\d*(?:\.[1-9]\d*)*$', num_str):
        raise ValidationError(f"invalid task number format: {num_str}")
    return tuple(int(x) for x in num_str.split('.'))

def format_num(num_tuple):
    """Converts a tuple of ints back to a string."""
    return '.'.join(str(x) for x in num_tuple)

def is_descendant(child, parent):
    """Returns True if 'child' is a descendant of 'parent' in the hierarchy."""
    return len(child) > len(parent) and child[:len(parent)] == parent

def is_child(child, parent):
    """Returns True if 'child' is an immediate child of 'parent'."""
    return len(child) == len(parent) + 1 and child[:-1] == parent


# --- Core Data Models ---
class Task:
    __slots__ = ('num', 'desc', 'is_complete')

    def __init__(self, num, desc, is_complete=False):
        self.num = num
        self.desc = desc
        self.is_complete = is_complete

    def to_line(self):
        """Serializes the task to the strict file format."""
        box = CHECK_COMPLETE if self.is_complete else CHECK_INCOMPLETE
        num_str = format_num(self.num)
        desc_esc = self.desc.replace('\\', '\\\\').replace('"', '\\"')
        return f'{box} {num_str} "{desc_esc}"\n'

    def __str__(self):
        """Console-friendly representation (same as file format without newline)."""
        return self.to_line().rstrip('\n')


# --- Task Manager ---
class PlanManager:
    """Handles the state, mutations, and file I/O for the plan hierarchy."""

    def __init__(self):
        self.tasks = []
        self.task_map = {}
        self.load()

    def _rebuild_map(self):
        """Sorts tasks ascendingly and rebuilds the fast-lookup dictionary."""
        self.tasks.sort(key=lambda t: t.num)
        self.task_map = {t.num: t for t in self.tasks}

    def load(self):
        """Reads ~/plan.txt and parses lines into Task objects."""
        if not PLAN_FILE.exists():
            return

        try:
            content = PLAN_FILE.read_text(encoding='utf-8')
        except OSError:
            abort(EXIT_IO, f"unable to read file {PLAN_FILE}")

        pattern = re.compile(rf'^({CHECK_INCOMPLETE}|{CHECK_COMPLETE}) ([\d\.]+) "(.*)"$')

        for line_idx, line in enumerate(content.splitlines(), 1):
            if not line.strip():
                continue

            match = pattern.match(line)
            if not match:
                abort(EXIT_IO, f"malformed line {line_idx} in plan.txt")

            box, num_str, raw_desc = match.groups()
            num = parse_num(num_str)
            desc = raw_desc.replace('\\"', '"').replace('\\\\', '\\')

            self.tasks.append(Task(num, desc, is_complete=(box == CHECK_COMPLETE)))

        self._rebuild_map()

    def save(self):
        """Validates the state and flushes atomically to disk."""
        self.validate()
        try:
            lines = [t.to_line() for t in self.tasks]
            PLAN_FILE.write_text(''.join(lines), encoding='utf-8')
        except OSError:
            abort(EXIT_IO, f"unable to write to file {PLAN_FILE}")

    def validate(self):
        """
        Enforces specification rules:
        - Blank slates start at 1.
        - No sibling gaps (segments must be strictly consecutive).
        - Parents must exist.
        """
        if not self.tasks:
            return

        if (1,) not in self.task_map:
            raise ValidationError("blank slate must start at 1")

        for t in self.tasks:
            parent = t.num[:-1]

            # Ensure parent exists
            if parent and parent not in self.task_map:
                raise ValidationError(f"parent {format_num(parent)} does not exist")

            # Ensure consecutive sequence (no gaps)
            if t.num[-1] > 1:
                prev_sibling = parent + (t.num[-1] - 1,)
                if prev_sibling not in self.task_map:
                    raise ValidationError(f"sibling gap - expected {format_num(prev_sibling)}")

    # --- Print Operations ---
    def print_all(self):
        """Prints the entire file."""
        for t in self.tasks:
            print(t)

    def print_subtree(self, num_str):
        """Prints a specific node and its descendants."""
        num = parse_num(num_str)
        if num not in self.task_map:
            raise ValidationError(f"task {num_str} does not exist")

        for t in self.tasks:
            if t.num == num or is_descendant(t.num, num):
                print(t)

    # --- Bubble & Propagation Rules ---
    def _propagate_complete(self, num):
        """Propagates completeness down (all descendants) and up (ancestors if criteria met)."""
        # Propagate down
        for t in self.tasks:
            if t.num == num or is_descendant(t.num, num):
                t.is_complete = True

        # Propagate up
        parent = num[:-1]
        while parent:
            children = [t for t in self.tasks if is_child(t.num, parent)]
            if all(c.is_complete for c in children):
                self.task_map[parent].is_complete = True
                parent = parent[:-1]
            else:
                break

    def _propagate_incomplete(self, num):
        """Propagates incompleteness down (all descendants) and up (all ancestors unconditionally)."""
        # Propagate down
        for t in self.tasks:
            if t.num == num or is_descendant(t.num, num):
                t.is_complete = False

        # Propagate up
        parent = num[:-1]
        while parent:
            self.task_map[parent].is_complete = False
            parent = parent[:-1]

    # --- Command Implementations ---
    def complete(self, num_str):
        num = parse_num(num_str)
        if num not in self.task_map:
            raise ValidationError(f"task {num_str} does not exist")
        self._propagate_complete(num)

    def incomplete(self, num_str):
        num = parse_num(num_str)
        if num not in self.task_map:
            raise ValidationError(f"task {num_str} does not exist")
        self._propagate_incomplete(num)

    def add_or_replace(self, pairs):
        """Adds or replaces tasks atomically based on pairs of [number, description]."""
        for num_str, desc in pairs:
            num = parse_num(num_str)
            if num in self.task_map:
                # Replace existing, reset state, and bubble up
                t = self.task_map[num]
                t.desc = desc
                self._propagate_incomplete(num)
            else:
                # Add new
                new_task = Task(num, desc)
                self.tasks.append(new_task)
                self.task_map[num] = new_task

        self._rebuild_map()

    def insert(self, num_str, desc):
        """Inserts a task at <n>, shifting existing and subsequent siblings right by 1."""
        num = parse_num(num_str)
        parent = num[:-1]
        target_idx = num[-1]

        # Shift relevant siblings and their subtrees
        for t in self.tasks:
            if t.num[:len(parent)] == parent and len(t.num) >= len(num):
                if t.num[len(parent)] >= target_idx:
                    shifted_num = list(t.num)
                    shifted_num[len(parent)] += 1
                    t.num = tuple(shifted_num)

        self.tasks.append(Task(num, desc))
        self._rebuild_map()

    def delete(self, num_str):
        """Deletes <n> + descendants, shifting subsequent siblings left by 1."""
        num = parse_num(num_str)
        if num not in self.task_map:
            raise ValidationError(f"task {num_str} does not exist")

        # Filter out the node and its subtree
        self.tasks = [t for t in self.tasks if t.num != num and not is_descendant(t.num, num)]

        # Shift subsequent siblings left
        parent = num[:-1]
        target_idx = num[-1]

        for t in self.tasks:
            if t.num[:len(parent)] == parent and len(t.num) >= len(num):
                if t.num[len(parent)] > target_idx:
                    shifted_num = list(t.num)
                    shifted_num[len(parent)] -= 1
                    t.num = tuple(shifted_num)

        self._rebuild_map()


# --- CLI Setup & Help Text ---
HELP_TEXT = """Plan Tool Specification Synopsis

Storage:
  • File: ~/plan.txt (UTF-8)
  • Tasks are strictly ordered by ascending task numbers.
  • Formatting: ☐|☒ <number> "<description>"

Hierarchy:
  • Positive, dot-separated integers with no leading zeros (e.g., 1.2.10).
  • Gaps are invalid at all times. Sibling sets must be consecutive.

Commands:
  plan                      → Print entire file
  plan <n>                  → Print <n> and its descendants
  plan <n> "<d>" ...        → Add/replace each pair. Atomic. Resets replacements to incomplete.
  plan complete <n>         → Mark <n> + descendants complete. Bubbles up to complete ancestors if all siblings complete.
  plan incomplete <n>       → Mark <n> + descendants incomplete. Bubbles up, making all ancestors incomplete.
  plan insert <n> "<d>"     → Insert task at <n>. Existing <n> and following siblings shift right (+1).
  plan delete <n>           → Delete <n> + descendants. Following siblings shift left (-1).
  plan --help               → Print this spec synopsis
"""

def main():
    manager = PlanManager()

    try:
        match sys.argv[1:]:
            case []:
                manager.print_all()
                sys.exit(EXIT_SUCCESS)

            case ["--help"]:
                print(HELP_TEXT, end="")
                sys.exit(EXIT_SUCCESS)

            case ["complete", n]:
                manager.complete(n)

            case ["incomplete", n]:
                manager.incomplete(n)

            case ["insert", n, desc]:
                manager.insert(n, desc)

            case ["delete", n]:
                manager.delete(n)

            case [n] if '.' in n or n.isdigit():
                manager.print_subtree(n)
                sys.exit(EXIT_SUCCESS)

            case args if len(args) >= 2 and len(args) % 2 == 0:
                pairs = list(zip(args[0::2], args[1::2]))
                manager.add_or_replace(pairs)

            case _:
                raise UsageError("unrecognized command or invalid arguments")

        # Atomic validate & write for any mutating command
        manager.save()

    except UsageError as e:
        abort(EXIT_USAGE, str(e))
    except ValidationError as e:
        abort(EXIT_VALIDATION, str(e))


if __name__ == "__main__":
    main()
