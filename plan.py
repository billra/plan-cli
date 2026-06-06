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


# --- Core Data Models ---
class TaskNode:
    """A node in the plan tree. Its task number is dynamically derived from its array position."""
    def __init__(self, desc="", is_complete=False):
        self.desc = desc
        self.is_complete = is_complete
        self.children = []
        self.parent = None

    @property
    def num(self):
        """Recursively calculate the tuple number based on its index in the parent's array."""
        if not self.parent:
            return ()
        idx = self.parent.children.index(self) + 1
        return self.parent.num + (idx,)

    def to_line(self):
        """Serializes the task to the strict file format."""
        box = CHECK_COMPLETE if self.is_complete else CHECK_INCOMPLETE
        desc_esc = self.desc.replace('\\', '\\\\').replace('"', '\\"')
        return f'{box} {format_num(self.num)} "{desc_esc}"'

    def __str__(self):
        return self.to_line()


# --- Task Manager ---
class PlanManager:
    """Handles the tree state, mutations, and file I/O."""

    def __init__(self, plan_file):
        self.plan_file = plan_file
        self.root = TaskNode()  # A dummy root node to hold the top-level tasks
        self.load()

    # --- Data Access ---
    def get_node(self, num_tuple, strict=False):
        """Walks down the tree to find a node by its tuple number."""
        curr = self.root
        for idx in num_tuple:
            if idx - 1 < 0 or idx - 1 >= len(curr.children):
                if strict:
                    raise ValidationError(f"task {format_num(num_tuple)} does not exist")
                return None
            curr = curr.children[idx - 1]
        return curr

    def _traverse(self, node):
        """Yields all nodes in depth-first order."""
        for child in node.children:
            yield child
            yield from self._traverse(child)

    # --- IO & Validation ---
    def load(self):
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

            # Since the file is strictly ordered, we can just safely rebuild the tree sequentially
            self._insert_node_at(num, desc, is_complete=(box == CHECK_COMPLETE))

    def save(self):
        """Writes the entire tree recursively to disk."""
        try:
            lines = [node.to_line() + '\n' for node in self._traverse(self.root)]
            self.plan_file.write_text(''.join(lines), encoding='utf-8')
        except OSError as e:
            raise OSError(f"unable to write to file {self.plan_file}") from e

    # --- Core Tree Mutations ---
    def _insert_node_at(self, num, desc, is_complete=False):
        """The core mutator for injecting nodes safely into the tree hierarchy."""
        parent = self.get_node(num[:-1])
        if not parent:
            raise ValidationError(f"parent {format_num(num[:-1])} does not exist")

        target_idx = num[-1] - 1

        # Validation: Sibling Gaps & Blank Slate
        if target_idx > len(parent.children):
            if parent == self.root and len(parent.children) == 0:
                raise ValidationError("blank slate must start at 1")
            expected = num[:-1] + (len(parent.children) + 1,)
            raise ValidationError(f"sibling gap - expected {format_num(expected)}")

        # If it exists, update it. If not, append/insert it.
        if target_idx < len(parent.children):
            node = parent.children[target_idx]
            node.desc = desc
            return node
        else:
            node = TaskNode(desc, is_complete)
            node.parent = parent
            parent.children.append(node)
            return node

    # --- Bubble Rules ---
    def _bubble_down(self, node, state):
        node.is_complete = state
        for child in self._traverse(node): # <-- FIXED HERE
            child.is_complete = state

    def _bubble_up_complete(self, node):
        curr = node.parent
        while curr and curr != self.root:
            if all(c.is_complete for c in curr.children):
                curr.is_complete = True
                curr = curr.parent
            else:
                break

    def _bubble_up_incomplete(self, node):
        curr = node.parent
        while curr and curr != self.root:
            curr.is_complete = False
            curr = curr.parent

    # --- Command Implementations ---
    def print_all(self):
        for node in self._traverse(self.root):
            print(node)

    def print_subtree(self, num_str):
        node = self.get_node(parse_num(num_str), strict=True)
        print(node)
        for child in self._traverse(node):
            print(child)

    def complete(self, num_str):
        node = self.get_node(parse_num(num_str), strict=True)
        self._bubble_down(node, True)
        self._bubble_up_complete(node)

    def incomplete(self, num_str):
        node = self.get_node(parse_num(num_str), strict=True)
        self._bubble_down(node, False)
        self._bubble_up_incomplete(node)

    def add_or_replace(self, pairs):
        # Sort tuples mathematically so parents are always processed before their children
        parsed_pairs = [(parse_num(n), d) for n, d in pairs]
        parsed_pairs.sort(key=lambda x: x[0])

        affected_nodes = []
        for num, desc in parsed_pairs:
            node = self._insert_node_at(num, desc)
            affected_nodes.append(node)

        # Trigger side-effects only after all insertions are valid
        for node in affected_nodes:
            self._bubble_down(node, False)
            self._bubble_up_incomplete(node)

    def insert(self, num_str, desc):
        num = parse_num(num_str)
        parent = self.get_node(num[:-1], strict=True)
        target_idx = num[-1] - 1

        if target_idx > len(parent.children):
            expected = num[:-1] + (len(parent.children) + 1,)
            raise ValidationError(f"sibling gap - expected {format_num(expected)}")

        node = TaskNode(desc)
        node.parent = parent
        parent.children.insert(target_idx, node) # Native shift right!

        self._bubble_down(node, False)
        self._bubble_up_incomplete(node)

    def delete(self, num_str):
        node = self.get_node(parse_num(num_str), strict=True)
        node.parent.children.remove(node) # Native shift left!


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
