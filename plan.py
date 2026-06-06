#!/usr/bin/env python3
"""
plan - A hierarchical task manager.
Maintains an ordered, tree-like structure of tasks in ~/plan.txt.
"""

import sys
import re
from pathlib import Path

class UsageError(Exception): pass
class ValidationError(Exception): pass

def parse_num(s):
    """Validates and converts a dot-separated string into a tuple of integers."""
    if not re.match(r'^[1-9]\d*(\.[1-9]\d*)*$', s):
        raise ValidationError(f"invalid task number format: {s}")
    return tuple(map(int, s.split('.')))

def stringify(num_tuple):
    """Converts a tuple of integers back into a dot-separated string."""
    return '.'.join(map(str, num_tuple))


class TaskNode:
    """
    Represents a single task in the hierarchy.
    Instead of calculating deep shifts manually, tasks are just objects in a list.
    When a list item is inserted or deleted, Python naturally shifts the sibling objects.
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
            return "root" # The hidden master root of the tree

        idx = self.parent.children.index(self) + 1

        # If our parent is the hidden master root, we are a top-level task (e.g., 1, 2, 3)
        if not self.parent.parent:
            return str(idx)

        # Otherwise, we prepend our parent's computed number
        return f"{self.parent.number}.{idx}"

    def clone(self, new_parent=None):
        """Creates a deep copy of this node and its descendants."""
        node = TaskNode(self.desc, parent=new_parent)
        node.is_done = self.is_done
        # FIX: Ensure the recursive call uses the correct 'new_parent' argument name
        node.children = [child.clone(new_parent=node) for child in self.children]
        return node

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


class PlanTree:
    """Manages the lifecycle, traversal, and validation of the Node structure."""
    def __init__(self):
        self.root = TaskNode("root")

    def clone(self):
        """Returns a completely decoupled duplicate of the tree for atomic transaction drafting."""
        new_tree = PlanTree()
        new_tree.root = self.root.clone()
        return new_tree

    def get_node(self, path):
        """Traverses the tree to find a node by its tuple path. Returns None if missing."""
        current = self.root
        for segment in path:
            idx = segment - 1
            if idx < 0 or idx >= len(current.children):
                return None
            current = current.children[idx]
        return current

    def get_all_nodes(self):
        """Yields every visible node in the tree in standard viewing order."""
        for child in self.root.children:
            yield from child.walk()

    def insert(self, path, desc):
        """Inserts a new task, enforcing structure and naturally shifting siblings."""
        parent_path = path[:-1]
        target_idx = path[-1] - 1

        parent_node = self.get_node(parent_path)
        if not parent_node:
            raise ValidationError(f"parent {stringify(parent_path)} does not exist")

        # Gap validation
        if target_idx > len(parent_node.children):
            # FIX 1: Check if the root list is completely empty, regardless of the target index requested
            if not parent_path and len(parent_node.children) == 0:
                raise ValidationError("blank slate must start at 1")

            expected_path = list(parent_path) + [len(parent_node.children) + 1]
            raise ValidationError(f"sibling gap - expected {stringify(expected_path)}")

        new_node = TaskNode(desc, parent=parent_node)
        parent_node.children.insert(target_idx, new_node)
        new_node.set_state(False)

    def delete(self, path):
        """Deletes a task and its descendants, naturally closing the gap behind it."""
        node = self.get_node(path)
        if not node:
            raise ValidationError(f"task {stringify(path)} does not exist")

        parent = node.parent
        parent.children.remove(node)

        # FIX 2: If the parent still exists (isn't the hidden root), re-evaluate its completion state
        if parent.parent:
            if parent.children and all(c.is_done for c in parent.children):
                parent.is_done = True
                parent.bubble_up()

    def add_or_replace(self, pairs):
        """Batch processes additions and replacements atomically."""
        sorted_pairs = sorted(pairs, key=lambda x: x[0])

        for path, desc in sorted_pairs:
            if node := self.get_node(path):
                node.desc = desc
                node.set_state(False)
            else:
                self.insert(path, desc)


class PlanManager:
    """Handles disk I/O and wraps Tree operations in atomic transactions."""
    def __init__(self, filepath):
        self.filepath = Path(filepath)
        self.tree = PlanTree()
        self.load()

    def load(self):
        if not self.filepath.exists():
            return

        lines = self.filepath.read_text(encoding='utf-8').splitlines()
        for idx, line in enumerate(lines, 1):
            if not line.strip():
                continue

            if not (match := re.match(r'^([☐☒])\s+([1-9]\d*(?:\.[1-9]\d*)*)\s+"(.*)"$', line)):
                raise OSError(f"malformed line {idx} in plan.txt")

            state, num_str, desc = match.groups()
            desc = desc.replace('\\"', '"').replace('\\\\', '\\')
            path = parse_num(num_str)

            # Because the file format strictly enforces ordering, we can bypass
            # the shifting rules and directly append the loaded objects to their parents.
            parent = self.tree.get_node(path[:-1])
            if not parent:
                raise OSError(f"hierarchy broken at line {idx} in plan.txt")

            node = TaskNode(desc, parent=parent)
            node.is_done = (state == '☒')
            parent.children.append(node)

    def save(self):
        lines = []
        for node in self.tree.get_all_nodes():
            state = '☒' if node.is_done else '☐'
            desc_esc = node.desc.replace('\\', '\\\\').replace('"', '\\"')
            lines.append(f'{state} {node.number} "{desc_esc}"')

        self.filepath.write_text('\n'.join(lines) + ('\n' if lines else ''), encoding='utf-8')

    def print_tasks(self, iterator):
        """Helper to format and print a stream of nodes."""
        for node in iterator:
            state = '☒' if node.is_done else '☐'
            desc_esc = node.desc.replace('\\', '\\\\').replace('"', '\\"')
            print(f'{state} {node.number} "{desc_esc}"')

    # --- Transactional Command Wrappers ---
    # By creating a clone draft first, we guarantee atomicity. If a Validation Error
    # happens deep inside the tree manipulation, the real tree remains untouched.

    def complete(self, num_str):
        path = parse_num(num_str)
        draft = self.tree.clone()
        if not (node := draft.get_node(path)):
            raise ValidationError(f"task {num_str} does not exist")
        node.set_state(True)
        self.tree = draft

    def incomplete(self, num_str):
        path = parse_num(num_str)
        draft = self.tree.clone()
        if not (node := draft.get_node(path)):
            raise ValidationError(f"task {num_str} does not exist")
        node.set_state(False)
        self.tree = draft

    def insert(self, num_str, desc):
        draft = self.tree.clone()
        draft.insert(parse_num(num_str), desc)
        self.tree = draft

    def delete(self, num_str):
        draft = self.tree.clone()
        draft.delete(parse_num(num_str))
        self.tree = draft

    def add_or_replace(self, pairs):
        draft = self.tree.clone()
        draft.add_or_replace([(parse_num(n), d) for n, d in pairs])
        self.tree = draft

    def print_all(self):
        self.print_tasks(self.tree.get_all_nodes())

    def print_subtree(self, num_str):
        if not (target := self.tree.get_node(parse_num(num_str))):
            raise ValidationError(f"task {num_str} does not exist")
        self.print_tasks(target.walk())


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
    manager = PlanManager(plan_file)

    match args:
        case []:
            manager.print_all()
            return
        case ["--help"]:
            print(HELP_TEXT, end="")
            return
        case ["complete", *rest]:
            if len(rest) != 1: raise UsageError("unrecognized command or invalid arguments")
            manager.complete(rest[0])
        case ["incomplete", *rest]:
            if len(rest) != 1: raise UsageError("unrecognized command or invalid arguments")
            manager.incomplete(rest[0])
        case ["insert", *rest]:
            if len(rest) != 2: raise UsageError("unrecognized command or invalid arguments")
            manager.insert(rest[0], rest[1])
        case ["delete", *rest]:
            if len(rest) != 1: raise UsageError("unrecognized command or invalid arguments")
            manager.delete(rest[0])
        case [n] if n.isdigit() or '.' in n:
            manager.print_subtree(n)
            return
        case _ if len(args) % 2 == 0 and len(args) > 0:
            pairs = list(zip(args[0::2], args[1::2]))
            manager.add_or_replace(pairs)
        case _:
            raise UsageError("unrecognized command or invalid arguments")

    manager.save()

def main():
    if len(sys.argv) == 2 and sys.argv[1] == '--help':
        print(HELP_TEXT, end="")
        sys.exit(0)

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
