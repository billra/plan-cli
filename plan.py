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

PATH_RE = re.compile(r'^[1-9]\d*(\.[1-9]\d*)*$')

# ==========================================
# Task Object & Utilities
# ==========================================

class Task:
    __slots__ = ('desc', 'is_done')
    def __init__(self, desc, is_done=False):
        self.desc = desc
        self.is_done = is_done

def parse_num(s):
    if not PATH_RE.match(s):
        raise PlanError(f"invalid task format: '{s}' (expected e.g. '1' or '1.2')")
    return tuple(map(int, s.split('.')))

def stringify(tup):
    return '.'.join(map(str, tup))

def is_descendant(target, candidate):
    return candidate[:len(target)] == target

def render(path, task):
    return f"{'☒' if task.is_done else '☐'} {stringify(path)} {task.desc}"

# ==========================================
# Core Engine
# ==========================================

class PlanManager:
    def __init__(self, filepath):
        self.filepath = filepath
        self.tasks = {}
        self.load()

    def load(self):
        if not self.filepath.exists():
            return

        for idx, line in enumerate(self.filepath.read_text(encoding='utf-8').splitlines(), 1):
            if not line.strip(): continue

            parts = line.split(maxsplit=2)
            if len(parts) != 3 or parts[0] not in ('☐', '☒'):
                raise OSError(f"malformed line {idx}: expected '☐|☒ <number> <desc>'")

            state_char, path_str, raw_desc = parts
            path, desc = parse_num(path_str), raw_desc.strip()

            if not desc:
                raise OSError(f"malformed line {idx}: description cannot be empty")

            if (parent := path[:-1]) and parent not in self.tasks:
                raise OSError(f"hierarchy broken line {idx}: missing parent '{stringify(parent)}'")

            self.tasks[path] = Task(desc, is_done=(state_char == '☒'))

    def save(self):
        lines = [render(path, task) for path, task in sorted(self.tasks.items())]
        self.filepath.write_text('\n'.join(lines) + '\n' if lines else '', encoding='utf-8')

    def transaction(self, action):
        """Used only for multi-adds to prevent partial application."""
        original = self.tasks
        self.tasks = copy.deepcopy(self.tasks)
        try:
            action()
        except Exception:
            self.tasks = original
            raise

    def add_or_replace(self, path, desc):
        if not (desc := desc.strip()):
            raise PlanError("task description cannot be empty")
        if (parent := path[:-1]) and parent not in self.tasks:
            raise PlanError(f"parent task '{stringify(parent)}' does not exist")
        self.tasks[path] = Task(desc, is_done=False)

    def delete(self, target_path):
        if target_path not in self.tasks:
            raise PlanError(f"task '{stringify(target_path)}' not found")
        self.tasks = {p: t for p, t in self.tasks.items() if not is_descendant(target_path, p)}

    def set_state(self, target_path, is_done):
        if target_path not in self.tasks:
            raise PlanError(f"task '{stringify(target_path)}' not found")
        self.tasks[target_path].is_done = is_done

    def display(self, target_path=None):
        visible = sorted(
            (p, t) for p, t in self.tasks.items()
            if target_path is None or is_descendant(target_path, p)
        )
        if target_path and not visible:
            raise PlanError(f"task '{stringify(target_path)}' not found")
        for path, task in visible:
            print(render(path, task))

# ==========================================
# CLI Dispatcher
# ==========================================

HELP_TEXT = """plan - A Hierarchical Task Manager

Task Numbering:
  • Use dot-separated integers without leading zeros (e.g., 1, 1.2, 1.2.10).
  • Gaps in numbering are permitted (e.g., 1 and 3 without 2).
  • A parent task must exist before adding a child task.

Commands:
  plan                    Show the entire plan
  plan <n>                Show task <n> and descendants
  plan <n> "<desc>" ...   Add or replace tasks
  plan complete <n>       Mark task <n> complete
  plan incomplete <n>     Mark task <n> incomplete
  plan delete <n>         Remove task <n> and descendants
  plan --help             Show this help
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
            manager.set_state(parse_num(target), cmd == "complete")
        case ["delete", target]:
            manager.delete(parse_num(target))
        case ["complete" | "incomplete" | "delete" as cmd, *_]:
            raise PlanError(f"'{cmd}' requires exactly 1 argument")
        case [n] if PATH_RE.match(n):
            manager.display(parse_num(n))
            return
        case _ if len(args) % 2 == 0 and len(args) > 0:
            pairs = sorted((parse_num(p), d) for p, d in zip(args[::2], args[1::2]))
            manager.transaction(
                lambda: [manager.add_or_replace(path, desc) for path, desc in pairs]
            )
        case _:
            raise PlanError(f"unrecognized arguments: '{' '.join(args)}'")

    manager.save()

def main():
    try:
        dispatch(Path('~/plan.txt').expanduser(), sys.argv[1:])
    except (PlanError, OSError) as e:
        sys.exit(f"error: {e}")

if __name__ == '__main__':
    main()
