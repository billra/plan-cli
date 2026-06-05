#!/usr/bin/env python3
"""
plan - A hierarchical task manager.
Maintains an ordered, tree-like structure of tasks in ~/plan.txt.
"""

import sys
import re
from pathlib import Path
from enum import IntEnum

# --- Constants & Configuration ---
CHECK_INCOMPLETE = '☐'
CHECK_COMPLETE = '☒'


class ExitCode(IntEnum):
    SUCCESS = 0
    USAGE = 1
    VALIDATION = 2
    IO = 3


# --- Error Handling ---
class UsageError(Exception):
    """Raised for invalid CLI arguments."""

class ValidationError(Exception):
    """Raised for invalid data state (gaps, missing parents, invalid numbers)."""


# --- Helper Functions ---
def parse_num(num_str):
    """Validates and converts a string number (e.g., '1.2.10') into a tuple of ints."""
    if not re.match(r'^[1-9]\d*(?:\.[1-9]\d*)*$', num_str):
        raise ValidationError(f"invalid task number format: {num_str}")
    return tuple(int(x) for x in num_str.split('.'))

def format_num(num_tuple):
    """Converts a tuple of ints back to a string."""
    return '.'.join(str(x) for x in num_tuple)

def is_child(child, parent):
    """Returns True if 'child' is an immediate child of 'parent'."""
    return len(child) == len(parent) + 1 and child[:-1] == parent


# --- Core Data Models ---
class Task:
    def __init__(self, num, desc, is_complete=False):
        self.num = num
        self.desc = desc
        self.is_complete = is_complete

    def to_line(self):
        """Serializes the task to the strict file format."""
        box = CHECK_COMPLETE if self.is_complete else CHECK_INCOMPLETE
        desc_esc = self.desc.replace('\\', '\\\\').replace('"', '\\"')
        return f'{box} {format_num(self.num)} "{desc_esc}"\n'

    def __str__(self):
        return self.to_line().rstrip('\n')


# --- Task Manager ---
class PlanManager:
    """Handles the state, mutations, and file I/O for the plan hierarchy."""

    def __init__(self, plan_file):
        self.plan_file = plan_file
        self.tasks = {}
        self.load()

    def load(self):
        """Reads the plan file and parses lines into Task objects."""
        if not self.plan_file.exists():
            return

        try:
            content = self.plan_file.read_text(encoding='utf-8')
        except OSError as e:
            raise OSError(f"unable to read file {self.plan_file}") from e

        pattern = re.compile(rf'^({CHECK_INCOMPLETE}|{CHECK_COMPLETE}) ([\d\.]+) "(.*)"$')

        for line_idx, line in enumerate(content.splitlines(), 1):
            if not line.strip():
                continue

            match = pattern.match(line)
            if not match:
                raise OSError(f"malformed line {line_idx} in plan.txt")

            box, num_str, raw_desc = match.groups()
            num = parse_num(num_str)
            desc = raw_desc.replace('\\"', '"').replace('\\\\', '\\')
            self.tasks[num] = Task(num, desc, is_complete=(box == CHECK_COMPLETE))

        self.tasks = dict(sorted(self.tasks.items()))

    def save(self):
        """Validates the state and flushes atomically to disk."""
        self.validate()
        try:
            lines = [t.to_line() for t in self.tasks.values()]
            self.plan_file.write_text(''.join(lines), encoding='utf-8')
        except OSError as e:
            raise OSError(f"unable to write to file {self.plan_file}") from e

    def validate(self):
        """Enforces specification rules."""
        if not self.tasks:
            return

        if (1,) not in self.tasks:
            raise ValidationError("blank slate must start at 1")

        for num in self.tasks:
            parent = num[:-1]
            if parent and parent not in self.tasks:
                raise ValidationError(f"parent {format_num(parent)} does not exist")

            if num[-1] > 1:
                prev_sibling = parent + (num[-1] - 1,)
                if prev_sibling not in self.tasks:
                    raise ValidationError(f"sibling gap - expected {format_num(prev_sibling)}")

    # --- Print Operations ---
    def print_all(self):
        """Prints the entire file."""
        for t in self.tasks.values():
            print(t)

    def print_subtree(self, num_str):
        """Prints a specific node and its descendants."""
        num = parse_num(num_str)
        if num not in self.tasks:
            raise ValidationError(f"task {num_str} does not exist")

        for t in self.tasks.values():
            if t.num[:len(num)] == num:
                print(t)

    # --- Bubble & Propagation Rules ---
    def _propagate_complete(self, num):
        """Propagates completeness down (all descendants) and up (ancestors if criteria met)."""
        # Propagate down
        for t in self.tasks.values():
            if t.num[:len(num)] == num:
                t.is_complete = True

        # Propagate up
        parent = num[:-1]
        while parent:
            children = [t for t in self.tasks.values() if is_child(t.num, parent)]
            if all(c.is_complete for c in children):
                self.tasks[parent].is_complete = True
                parent = parent[:-1]
            else:
                break

    def _propagate_incomplete(self, num):
        """Propagates incompleteness down (all descendants) and up (all ancestors unconditionally)."""
        # Propagate down
        for t in self.tasks.values():
            if t.num[:len(num)] == num:
                t.is_complete = False

        # Propagate up
        parent = num[:-1]
        while parent:
            self.tasks[parent].is_complete = False
            parent = parent[:-1]

    # --- Command Implementations ---
    def complete(self, num_str):
        num = parse_num(num_str)
        if num not in self.tasks:
            raise ValidationError(f"task {num_str} does not exist")
        self._propagate_complete(num)

    def incomplete(self, num_str):
        num = parse_num(num_str)
        if num not in self.tasks:
            raise ValidationError(f"task {num_str} does not exist")
        self._propagate_incomplete(num)

    def add_or_replace(self, pairs):
        """Adds or replaces tasks atomically based on pairs of [number, description]."""
        for num_str, desc in pairs:
            num = parse_num(num_str)
            if num in self.tasks:
                self.tasks[num].desc = desc
                self._propagate_incomplete(num)
            else:
                self.tasks[num] = Task(num, desc)

        self.tasks = dict(sorted(self.tasks.items()))

    def insert(self, num_str, desc):
        """Inserts a task at <n>, shifting existing and subsequent siblings right by 1."""
        num = parse_num(num_str)
        parent = num[:-1]
        target_idx = num[-1]

        keys_to_shift = sorted(
            (k for k in self.tasks if k[:len(parent)] == parent and len(k) >= len(num) and k[len(parent)] >= target_idx),
            reverse=True
        )

        for k in keys_to_shift:
            shifted_k = k[:len(parent)] + (k[len(parent)] + 1,) + k[len(parent)+1:]
            self.tasks[shifted_k] = self.tasks.pop(k)
            self.tasks[shifted_k].num = shifted_k

        self.tasks[num] = Task(num, desc)
        self.tasks = dict(sorted(self.tasks.items()))

    def delete(self, num_str):
        """Deletes <n> + descendants, shifting subsequent siblings left by 1."""
        num = parse_num(num_str)
        if num not in self.tasks:
            raise ValidationError(f"task {num_str} does not exist")

        self.tasks = {k: v for k, v in self.tasks.items() if k[:len(num)] != num}
        parent = num[:-1]
        target_idx = num[-1]

        keys_to_shift = sorted(
            k for k in self.tasks if k[:len(parent)] == parent and len(k) >= len(num) and k[len(parent)] > target_idx
        )

        for k in keys_to_shift:
            shifted_k = k[:len(parent)] + (k[len(parent)] - 1,) + k[len(parent)+1:]
            self.tasks[shifted_k] = self.tasks.pop(k)
            self.tasks[shifted_k].num = shifted_k

        self.tasks = dict(sorted(self.tasks.items()))


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
  plan                    → Print entire file
  plan <n>                → Print <n> and its descendants
  plan <n> "<d>" ...      → Add/replace each pair. Atomic. Resets replacements to incomplete.
  plan complete <n>       → Mark <n> + descendants complete. Bubbles up to complete ancestors if all siblings complete.
  plan incomplete <n>     → Mark <n> + descendants incomplete. Bubbles up, making all ancestors incomplete.
  plan insert <n> "<d>"   → Insert task at <n>. Existing <n> and following siblings shift right (+1).
  plan delete <n>         → Delete <n> + descendants. Following siblings shift left (-1).
  plan --help             → Print this spec synopsis
"""

def dispatch(plan_file, args):
    """Takes the target file and a list of arguments."""
    manager = PlanManager(plan_file)

    match args:
        case []:
            manager.print_all()
            return
        case ["--help"]:
            print(HELP_TEXT, end="")
            return
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
            return
        case _ if len(args) >= 2 and len(args) % 2 == 0:
            pairs = list(zip(args[0::2], args[1::2]))
            manager.add_or_replace(pairs)
        case _:
            raise UsageError("unrecognized command or invalid arguments")

    manager.save()

def main():
    """The CLI entry point handles all sys interactions."""
    plan_file = Path('~/plan.txt').expanduser()
    args = sys.argv[1:]

    try:
        dispatch(plan_file, args)
    except UsageError as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(ExitCode.USAGE)
    except ValidationError as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(ExitCode.VALIDATION)
    except OSError as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(ExitCode.IO)

if __name__ == "__main__":
    main()
