#!/usr/bin/env python3
"""
plan - A hierarchical task manager.
Maintains an ordered, tree-like structure of tasks in ~/plan.txt.
"""

import sys
import re
from pathlib import Path
from dataclasses import dataclass

class UsageError(Exception): pass
class ValidationError(Exception): pass

def parse_num(s):
    if not re.match(r'^[1-9]\d*(\.[1-9]\d*)*$', s):
        raise ValidationError(f"invalid task number format: {s}")
    return tuple(map(int, s.split('.')))

def stringify(num_tuple):
    return '.'.join(map(str, num_tuple))

@dataclass
class Task:
    desc: str
    is_done: bool = False

class PlanManager:
    def __init__(self, filepath):
        self.filepath = Path(filepath)
        self.tasks = {}
        self.load()

    def load(self):
        if not self.filepath.exists():
            return

        lines = self.filepath.read_text(encoding='utf-8').splitlines()

        for idx, line in enumerate(lines, 1):
            if not line.strip():
                continue
            match = re.match(r'^([☐☒])\s+([1-9]\d*(?:\.[1-9]\d*)*)\s+"(.*)"$', line)
            if not match:
                raise OSError(f"malformed line {idx} in plan.txt")

            state, num_str, desc = match.groups()
            desc = desc.replace('\\"', '"').replace('\\\\', '\\')
            self.tasks[parse_num(num_str)] = Task(desc, state == '☒')

    def save(self):
        lines = []
        for num in sorted(self.tasks.keys()):
            task = self.tasks[num]
            state = '☒' if task.is_done else '☐'
            desc_esc = task.desc.replace('\\', '\\\\').replace('"', '\\"')
            lines.append(f'{state} {stringify(num)} "{desc_esc}"')

        self.filepath.write_text('\n'.join(lines) + ('\n' if lines else ''), encoding='utf-8')

    def _validate(self, tasks):
        if not tasks: return
        for k in sorted(tasks.keys()):
            if len(k) == 1:
                if k[0] > 1 and (k[0] - 1,) not in tasks:
                    # Clearer way to check if the user is trying to seed an empty slate with an invalid index
                    if len(tasks) == 1:
                        raise ValidationError("blank slate must start at 1")
                    raise ValidationError(f"sibling gap - expected {k[0]-1}")
            else:
                parent = k[:-1]
                if parent not in tasks:
                    raise ValidationError(f"parent {stringify(parent)} does not exist")
                if k[-1] > 1 and (*parent, k[-1] - 1) not in tasks:
                    raise ValidationError(f"sibling gap - expected {stringify((*parent, k[-1] - 1))}")

    def _shift(self, tasks, target, offset):
        parent_prefix = target[:-1]
        start_idx = target[-1]
        new_tasks = {}

        for k, task in tasks.items():
            # Check if this key is a sibling or descendant of a sibling that needs to shift
            is_match = (
                len(k) >= len(target) and
                k[:len(parent_prefix)] == parent_prefix and
                k[len(parent_prefix)] >= start_idx
            )

            if is_match:
                new_key = list(k)
                new_key[len(parent_prefix)] += offset
                new_tasks[tuple(new_key)] = task
            else:
                new_tasks[k] = task

        return new_tasks

    def _bubble(self, tasks, target, is_done):
        # Bubble down to descendants
        for k in tasks:
            if len(k) >= len(target) and k[:len(target)] == target:
                tasks[k].is_done = is_done

        # Bubble up to ancestors
        parent = target[:-1]
        while parent:
            if is_done:
                children = [tasks[k] for k in tasks if len(k) == len(parent) + 1 and k[:len(parent)] == parent]
                if children and all(c.is_done for c in children):
                    tasks[parent].is_done = True
                else:
                    break # Stop if a parent doesn't complete
            else:
                tasks[parent].is_done = False
            parent = parent[:-1]

    def _print_tasks(self, tasks_to_print):
        for num in sorted(tasks_to_print):
            task = self.tasks[num]
            state = '☒' if task.is_done else '☐'
            desc_esc = task.desc.replace('\\', '\\\\').replace('"', '\\"')
            print(f'{state} {stringify(num)} "{desc_esc}"')

    def print_all(self):
        self._print_tasks(self.tasks.keys())

    def print_subtree(self, num_str):
        target = parse_num(num_str)
        if target not in self.tasks:
            raise ValidationError(f"task {num_str} does not exist")
        subtree = [k for k in self.tasks if len(k) >= len(target) and k[:len(target)] == target]
        self._print_tasks(subtree)

    def complete(self, num_str):
        target = parse_num(num_str)
        if target not in self.tasks: raise ValidationError(f"task {num_str} does not exist")
        draft = {k: Task(v.desc, v.is_done) for k, v in self.tasks.items()}
        self._bubble(draft, target, True)
        self.tasks = draft

    def incomplete(self, num_str):
        target = parse_num(num_str)
        if target not in self.tasks: raise ValidationError(f"task {num_str} does not exist")
        draft = {k: Task(v.desc, v.is_done) for k, v in self.tasks.items()}
        self._bubble(draft, target, False)
        self.tasks = draft

    def insert(self, num_str, desc):
        target = parse_num(num_str)
        draft = {k: Task(v.desc, v.is_done) for k, v in self.tasks.items()}
        draft = self._shift(draft, target, 1)
        draft[target] = Task(desc)

        # Validate structural changes before executing state changes
        self._validate(draft)
        self._bubble(draft, target, False)
        self.tasks = draft

    def delete(self, num_str):
        target = parse_num(num_str)
        if target not in self.tasks: raise ValidationError(f"task {num_str} does not exist")
        draft = {k: Task(v.desc, v.is_done) for k, v in self.tasks.items()}

        # 1. Structural removal and shifting
        draft = {k: v for k, v in draft.items() if not (len(k) >= len(target) and k[:len(target)] == target)}
        draft = self._shift(draft, target, -1)

        # 2. Validate remaining structure
        self._validate(draft)

        # 3. Post-validation state cleanup
        parent = target[:-1]
        if parent in draft:
            children = [v for k, v in draft.items() if len(k) == len(parent) + 1 and k[:len(parent)] == parent]
            if children and all(c.is_done for c in children):
                self._bubble(draft, parent, True)

        self.tasks = draft

    def add_or_replace(self, pairs):
        draft = {k: Task(v.desc, v.is_done) for k, v in self.tasks.items()}
        parsed_pairs = sorted([(parse_num(n), d) for n, d in pairs])

        # 1. Populate the draft entries
        for target, desc in parsed_pairs:
            if target in draft:
                draft[target].desc = desc
            else:
                draft[target] = Task(desc)

        # 2. Validate structural integrity first (Catches Orphans and Sibling Gaps smoothly)
        self._validate(draft)

        # 3. Safe to bubble state now that hierarchy structure is verified
        for target, _ in parsed_pairs:
            self._bubble(draft, target, False)

        self.tasks = draft

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
