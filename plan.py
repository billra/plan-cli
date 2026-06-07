#!/usr/bin/env python3
"""
plan - A hierarchical task manager.
Maintains an ordered, tree-like structure of tasks in ~/plan.txt.
"""

import sys
import re
import copy
from pathlib import Path

ROOT_NAME = "root"

class UsageError(Exception): pass
class ValidationError(Exception): pass

def parse_num(s):
    """Validates and converts a dot-separated string into a tuple of integers."""
    if not re.match(r'^[1-9]\d*(\.[1-9]\d*)*$', s):
        raise ValidationError(f"invalid task number format: '{s}' (expected positive dot-separated integers like '1' or '1.2')")
    return tuple(map(int, s.split('.')))

def stringify(num_tuple):
    """Converts a tuple of integers back into a dot-separated string."""
    return '.'.join(map(str, num_tuple))

class TaskNode:
    """
    Represent a single task in the hierarchy.
    Because tasks are objects in a list, Python naturally handles all shifting
    and memory management when nodes are inserted or removed.
    """
    def __init__(self, desc="", parent=None):
        self.desc = desc
        self.is_done = False
        self.parent = parent
        self.children = []

    @property
    def number(self):
        """
        Dynamically computes the task number based on its current position in the tree.
        Because this is calculated on-the-fly, shifting is entirely automatic.
        """
        if not self.parent:
            return ROOT_NAME # The hidden master root of the tree

        idx = self.parent.children.index(self) + 1

        # If our parent is the hidden master root, we are a top-level task (e.g., 1, 2, 3)
        if not self.parent.parent:
            return str(idx)

        # Otherwise, we prepend our parent's computed number
        return f"{self.parent.number}.{idx}"

    def format_line(self):
        """Returns the canonical string representation of the task."""
        state = '☒' if self.is_done else '☐'
        desc_esc = self.desc.replace('\\', '\\\\').replace('"', '\\"')
        return f'{state} {self.number} "{desc_esc}"'

    def bubble_down(self, state):
        """Recursively forces the given state onto all descendants."""
        self.is_done = state
        for child in self.children:
            child.bubble_down(state)

    def bubble_up(self):
        """Cascades state changes up the ancestor chain based on the Bubble Rules."""
        if not self.parent or not self.parent.parent:
            return # Stop when we reach the hidden master root

        if self.is_done:
            # Complete Bubble Rule: Ancestor completes only if ALL children are complete
            if all(c.is_done for c in self.parent.children):
                self.parent.is_done = True
                self.parent.bubble_up()
        else:
            # Incomplete Bubble Rule: Ancestor immediately becomes incomplete
            self.parent.is_done = False
            self.parent.bubble_up()

    def set_state(self, state):
        """Safely applies a state change and triggers both directional rules."""
        self.bubble_down(state)
        self.bubble_up()

    def walk(self):
        """Generator that yields this node and all descendants in strict pre-order."""
        yield self
        for child in self.children:
            yield from child.walk()

    # --- Tree Operations ---

    def get_node(self, path):
        """Traverses the tree to find a node by its tuple path. Returns None if missing."""
        current = self
        for segment in path:
            idx = segment - 1
            if idx < 0 or idx >= len(current.children):
                return None
            current = current.children[idx]
        return current

    def insert(self, path, desc):
        """Inserts a new task, enforcing structure and naturally shifting siblings."""
        parent_path = path[:-1]
        target_idx = path[-1] - 1

        parent = self.get_node(parent_path)
        if not parent:
            raise ValidationError(f"cannot insert '{stringify(path)}': parent task '{stringify(parent_path)}' does not exist")

        # Gap validation
        if target_idx > len(parent.children):
            if not parent_path and not parent.children:
                raise ValidationError(f"cannot insert '{stringify(path)}': a blank plan must start at task '1'")

            expected_path = list(parent_path) + [len(parent.children) + 1]
            raise ValidationError(f"cannot insert '{stringify(path)}': sibling gap detected, expected '{stringify(expected_path)}'")

        new_node = TaskNode(desc, parent=parent)
        parent.children.insert(target_idx, new_node)
        new_node.set_state(False)

    def delete(self, path):
        """Deletes a task and its descendants, naturally closing the gap behind it."""
        node = self.get_node(path)
        if not node:
            raise ValidationError(f"cannot delete task '{stringify(path)}': task does not exist")

        parent = node.parent
        parent.children.remove(node)

        # Re-evaluate parent completion state in case we deleted the last incomplete child
        if parent.parent and parent.children and all(c.is_done for c in parent.children):
            parent.is_done = True
            parent.bubble_up()

    def add_or_replace(self, pairs):
        """Batch processes additions and replacements atomically."""
        for path, desc in sorted(pairs, key=lambda x: x[0]):
            if node := self.get_node(path):
                node.desc = desc
                node.set_state(False)
            else:
                self.insert(path, desc)

class PlanManager:
    """Handles disk I/O and wraps Tree operations in atomic deepcopy transactions."""
    def __init__(self, filepath):
        self.filepath = Path(filepath)
        self.root = TaskNode(ROOT_NAME)
        self.load()

    def load(self):
        """Parses the storage file and rebuilds the node tree."""
        if not self.filepath.exists():
            return

        lines = self.filepath.read_text(encoding='utf-8').splitlines()
        for idx, line in enumerate(lines, 1):
            if not line.strip():
                continue

            match = re.match(r'^([☐☒])\s+([1-9]\d*(?:\.[1-9]\d*)*)\s+"(.*)"$', line)
            if not match:
                raise OSError(f"malformed line {idx} in plan.txt: '{line.strip()}' (expected format: ☐|☒ <number> \"<description>\")")

            state, path, desc = match[1], parse_num(match[2]), match[3].replace('\\"', '"').replace('\\\\', '\\')

            parent = self.root.get_node(path[:-1])
            if not parent:
                parent_str = stringify(path[:-1]) if path[:-1] else ROOT_NAME
                raise OSError(f"hierarchy broken at line {idx} in plan.txt: parent task '{parent_str}' missing for '{stringify(path)}'")

            # Validate structural continuity (sibling gaps) during load
            target_idx = path[-1] - 1
            if target_idx != len(parent.children):
                expected_path_str = stringify(path[:-1] + (len(parent.children) + 1,))
                raise OSError(f"hierarchy broken at line {idx} in plan.txt: sibling gap detected for '{stringify(path)}', expected '{expected_path_str}'")

            node = TaskNode(desc, parent=parent)
            node.is_done = (state == '☒')
            parent.children.append(node)

    def save(self):
        """Computes current string representations and writes to disk."""
        lines = []
        for child in self.root.children:
            for node in child.walk():
                lines.append(node.format_line())

        self.filepath.write_text('\n'.join(lines) + ('\n' if lines else ''), encoding='utf-8')

    def print_tasks(self, iterator):
        """Helper to format and print a stream of nodes."""
        for node in iterator:
            print(node.format_line())

    # Transactional Command Wrapper:
    #  By creating a clone draft first, we guarantee atomicity. If a Validation
    # Error happens during tree manipulation, the real tree remains untouched.
    def _atomic(self, action):
        """Standardizes the deepcopy atomic transaction pattern to prevent corruption."""
        draft_root = copy.deepcopy(self.root)
        action(draft_root)
        self.root = draft_root

    def _update_task_state(self, target, state, action_name):
        """Helper to dynamically locate a node and update its state."""
        node = self.root.get_node(parse_num(target))
        if not node:
            raise ValidationError(f"cannot mark {action_name}: task '{target}' does not exist")
        node.set_state(state)

    def complete(self, target):
        self._update_task_state(target, True, "complete")

    def incomplete(self, target):
        self._update_task_state(target, False, "incomplete")

    def insert(self, target, desc):
        self.root.insert(parse_num(target), desc)

    def delete(self, target):
        self.root.delete(parse_num(target))

    def add_or_replace(self, pairs):
        parsed_pairs = [(parse_num(n), d) for n, d in pairs]
        self._atomic(lambda draft: draft.add_or_replace(parsed_pairs))

    def print_all(self):
        for child in self.root.children:
            self.print_tasks(child.walk())

    def print_subtree(self, target):
        node = self.root.get_node(parse_num(target))
        if not node:
            raise ValidationError(f"cannot print subtree: task '{target}' does not exist")
        self.print_tasks(node.walk())

HELP_TEXT = """Plan Tool Specification Synopsis

Storage:
  • File: ~/plan.txt (UTF-8)
  • Tasks are strictly ordered by ascending task numbers.
  • Formatting: ☐|☒ <number> "<description>"

Hierarchy:
  • Positive, dot-separated integers with no leading zeros (e.g., 1.2.10).
  • Gaps are invalid at all times. Sibling sets must be consecutive.

Commands:
  plan                  → Print entire file
  plan <n>              → Print <n> and its descendants
  plan <n> "<d>" ...    → Add/replace each pair. Atomic. Resets replacements to incomplete.
  plan complete <n>     → Mark <n> + descendants complete. Bubbles up to complete ancestors if all siblings complete.
  plan incomplete <n>   → Mark <n> + descendants incomplete. Bubbles up, making all ancestors incomplete.
  plan insert <n> "<d>" → Insert task at <n>. Existing <n> and following siblings shift right (+1).
  plan delete <n>       → Delete <n> + descendants. Following siblings shift left (-1).
  plan --help           → Print this spec synopsis
"""

def dispatch(plan_file, args):
    manager = PlanManager(plan_file)

    match args:
        case []:
            manager.print_all()
            return
        case ["--help"]:
            print(HELP_TEXT, end="")
            return
        case ["complete", *rest]:
            if len(rest) != 1:
                raise UsageError(f"'complete' requires exactly 1 argument: a task number (got {len(rest)})")
            manager.complete(rest[0])
        case ["incomplete", *rest]:
            if len(rest) != 1:
                raise UsageError(f"'incomplete' requires exactly 1 argument: a task number (got {len(rest)})")
            manager.incomplete(rest[0])
        case ["insert", *rest]:
            if len(rest) != 2:
                raise UsageError(f"'insert' requires exactly 2 arguments: a task number and a description (got {len(rest)})")
            manager.insert(rest[0], rest[1])
        case ["delete", *rest]:
            if len(rest) != 1:
                raise UsageError(f"'delete' requires exactly 1 argument: a task number (got {len(rest)})")
            manager.delete(rest[0])
        case [n] if n.isdigit() or '.' in n:
            manager.print_subtree(n)
            return
        case _ if len(args) % 2 == 0 and len(args) > 0:
            pairs = list(zip(args[0::2], args[1::2]))
            manager.add_or_replace(pairs)
        case _:
            raise UsageError(f"unrecognized command or invalid arguments: '{' '.join(args)}'")

    manager.save()

def main():
    try:
        dispatch(Path('~/plan.txt').expanduser(), sys.argv[1:])
    except UsageError as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(1)
    except ValidationError as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(2)
    except OSError as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(3)

if __name__ == '__main__':
    main()
