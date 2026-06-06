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
    if not re.match(r'^[1-9]\d*(\.[1-9]\d*)*$', s):
        raise ValidationError(f"invalid task number format: {s}")
    return tuple(map(int, s.split('.')))

def stringify(num_tuple):
    return '.'.join(map(str, num_tuple))

class TaskNode:
    def __init__(self, num, desc, is_done=False):
        self.num = num  # tuple of ints
        self.desc = desc
        self.is_done = is_done
        self.parent = None
        self.children = []

    def set_done(self, val):
        self.is_done = val
        for child in self.children:
            child.set_done(val)

    def bubble_up(self):
        if not self.parent:
            return
        if self.is_done:
            if all(child.is_done for child in self.parent.children):
                self.parent.is_done = True
                self.parent.bubble_up()
        else:
            self.parent.is_done = False
            self.parent.bubble_up()

    def to_line(self):
        """Standardizes escaping for both saving and printing."""
        state = '☒' if self.is_done else '☐'
        desc_esc = self.desc.replace('\\', '\\\\').replace('"', '\\"')
        return f'{state} {stringify(self.num)} "{desc_esc}"'

class PlanManager:
    def __init__(self, filepath):
        self.filepath = Path(filepath)
        self.root_nodes = []
        self.load()

    def load(self):
        if not self.filepath.exists():
            return

        flat_tasks = []
        lines = self.filepath.read_text(encoding='utf-8').splitlines()

        for idx, line in enumerate(lines, 1):
            if not line.strip():
                continue
            match = re.match(r'^([☐☒])\s+([1-9]\d*(?:\.[1-9]\d*)*)\s+"(.*)"$', line)
            if not match:
                raise OSError(f"malformed line {idx} in plan.txt")

            state, num_str, desc = match.groups()
            desc = desc.replace('\\"', '"').replace('\\\\', '\\')
            flat_tasks.append((parse_num(num_str), desc, state == '☒'))

        # Reconstruct tree hierarchy dynamically
        flat_tasks.sort(key=lambda x: x[0])
        node_map = {}
        for num, desc, is_done in flat_tasks:
            node = TaskNode(num, desc, is_done)
            node_map[num] = node
            if len(num) == 1:
                self.root_nodes.append(node)
            else:
                parent_num = num[:-1]
                if parent_num in node_map:
                    parent = node_map[parent_num]
                    node.parent = parent
                    parent.children.append(node)
                else:
                    raise OSError(f"corrupt hierarchy: parent {stringify(parent_num)} missing")

    def save(self):
        lines = []
        def collect(nodes):
            for node in nodes:
                # Derive number dynamically based on absolute index paths
                if node.parent:
                    idx = node.parent.children.index(node) + 1
                    node.num = node.parent.num + (idx,)
                else:
                    idx = self.root_nodes.index(node) + 1
                    node.num = (idx,)

                lines.append(node.to_line())
                collect(node.children)

        collect(self.root_nodes)
        self.filepath.write_text('\n'.join(lines) + ('\n' if lines else ''), encoding='utf-8')

    def find_node(self, num_str):
        target = parse_num(num_str)
        def search(nodes):
            for node in nodes:
                if node.num == target: return node
                res = search(node.children)
                if res: return res
            return None
        node = search(self.root_nodes)
        if not node:
            raise ValidationError(f"task {num_str} does not exist")
        return node

    def print_all(self):
        def out(nodes):
            for node in nodes:
                print(node.to_line())
                out(node.children)
        out(self.root_nodes)

    def print_subtree(self, num_str):
        root = self.find_node(num_str)
        def out(node):
            print(node.to_line())
            for child in node.children: out(child)
        out(root)

    def complete(self, num_str):
        node = self.find_node(num_str)
        node.set_done(True)
        node.bubble_up()

    def incomplete(self, num_str):
        node = self.find_node(num_str)
        node.set_done(False)
        node.bubble_up()

    def insert(self, num_str, desc):
        target = parse_num(num_str)
        if len(target) == 1:
            idx = target[0] - 1
            if idx < 0 or idx > len(self.root_nodes):
                raise ValidationError(f"sibling gap - expected {len(self.root_nodes) + 1}")
            self.root_nodes.insert(idx, TaskNode(target, desc))
        else:
            parent = self.find_node(stringify(target[:-1]))
            idx = target[-1] - 1
            if idx < 0 or idx > len(parent.children):
                raise ValidationError(f"sibling gap - expected {stringify(target[:-1])}.{len(parent.children) + 1}")
            new_node = TaskNode(target, desc)
            new_node.parent = parent
            parent.children.insert(idx, new_node)
            parent.is_done = False
            parent.bubble_up()

    def delete(self, num_str):
        node = self.find_node(num_str)
        if node.parent:
            node.parent.children.remove(node)
            node.parent.bubble_up()
        else:
            self.root_nodes.remove(node)

    def add_or_replace(self, pairs):
        parsed_pairs = [(parse_num(n), d) for n, d in pairs]
        parsed_pairs.sort(key=lambda x: x[0])

        for target, desc in parsed_pairs:
            # Try to replace
            def search(nodes):
                for n in nodes:
                    if n.num == target: return n
                    res = search(n.children)
                    if res: return res
                return None

            existing = search(self.root_nodes)
            if existing:
                existing.desc = desc
                existing.is_done = False
                existing.bubble_up()
            else:
                # Add asset
                if len(target) == 1:
                    if target[0] != len(self.root_nodes) + 1:
                        if len(self.root_nodes) == 0:
                            raise ValidationError("blank slate must start at 1")
                        raise ValidationError(f"sibling gap - expected {len(self.root_nodes) + 1}")
                    self.root_nodes.append(TaskNode(target, desc))
                else:
                    parent = search(self.root_nodes)
                    if not parent:
                        # Backup hierarchy seek if not built in batch yet
                        def search_str(nodes, t):
                            for n in nodes:
                                if n.num == t: return n
                                r = search_str(n.children, t)
                                if r: return r
                            return None
                        parent = search_str(self.root_nodes, target[:-1])

                    if not parent:
                        raise ValidationError(f"parent {stringify(target[:-1])} does not exist")

                    if target[-1] != len(parent.children) + 1:
                        raise ValidationError(f"sibling gap - expected {stringify(target[:-1])}.{len(parent.children) + 1}")

                    new_node = TaskNode(target, desc)
                    new_node.parent = parent
                    parent.children.append(new_node)
                    parent.is_done = False
                    parent.bubble_up()
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
        # ... inside dispatch ...
        case ["delete", *rest]:
            if len(rest) != 1: raise UsageError("unrecognized command or invalid arguments")
            manager.delete(rest[0])
        case [n] if n.isdigit() or '.' in n:
            manager.print_subtree(n)
            return
        case _ if len(args) % 2 == 0:
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
