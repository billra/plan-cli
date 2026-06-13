#!/usr/bin/env python3
"""
plan - A hierarchical, fixed-ID task manager.
"""

import sys
from pathlib import Path

class PlanError(Exception): pass

# ==========================================
# Task & Utilities
# ==========================================

class Task:
    __slots__ = ('desc', 'is_done')
    def __init__(self, desc, is_done=False):
        self.desc = desc
        self.is_done = is_done

def parse_num(s):
    try:
        t = tuple(map(int, s.split('.')))
        if not t or any(i < 1 for i in t): raise ValueError
        return t
    except ValueError:
        raise PlanError(f"invalid format: '{s}' (expected e.g. '1' or '1.2')")

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
        try:
            text = self.filepath.read_text(encoding='utf-8')
        except FileNotFoundError:
            return

        for idx, line in enumerate(text.splitlines(), 1):
            if not line.strip(): continue
            try:
                state, p_str, desc = line.split(maxsplit=2)
                if state not in ('☐', '☒'): raise ValueError

                path = parse_num(p_str)
                self.add_or_replace(path, desc)
                self.tasks[path].is_done = (state == '☒')
            except (ValueError, PlanError) as e:
                raise OSError(f"malformed line {idx} in plan.txt: {e}")

    def save(self):
        lines = [render(p, t) for p, t in sorted(self.tasks.items())]
        self.filepath.write_text('\n'.join(lines) + '\n' if lines else '', encoding='utf-8')

    def add_or_replace(self, path, desc):
        if not (desc := desc.strip()):
            raise PlanError("task description cannot be empty")
        if (parent := path[:-1]) and parent not in self.tasks:
            raise PlanError(f"parent task '{stringify(parent)}' does not exist")
        self.tasks[path] = Task(desc)

    def delete(self, target):
        if target not in self.tasks:
            raise PlanError(f"task '{stringify(target)}' not found")
        self.tasks = {p: t for p, t in self.tasks.items() if not is_descendant(target, p)}

    def set_state(self, target, is_done):
        if target not in self.tasks:
            raise PlanError(f"task '{stringify(target)}' not found")
        self.tasks[target].is_done = is_done

    def display(self, target=None):
        visible = sorted(
            (p, t) for p, t in self.tasks.items()
            if target is None or is_descendant(target, p)
        )
        if target and not visible:
            raise PlanError(f"task '{stringify(target)}' not found")
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

def dispatch(argv, path):
    """Core argument interpreter used by both the CLI and the test-suite."""
    mgr = PlanManager(path)

    match argv:
        case []:                         # `plan`
            mgr.display(); return
        case ["--help"]:                 # `plan --help`
            print(HELP_TEXT, end=""); return
        case ["complete" | "incomplete" as cmd, tgt]:
            mgr.set_state(parse_num(tgt), cmd == "complete")
        case ["delete", tgt]:
            mgr.delete(parse_num(tgt))
        case ["complete" | "incomplete" | "delete" as cmd, *_]:
            raise PlanError(f"'{cmd}' requires exactly 1 argument")
        case [single]:                   # `plan <n>`
            mgr.display(parse_num(single)); return
        case _ if len(argv) % 2 == 0:    # batch upsert pairs
            pairs = sorted((parse_num(p), d) for p, d in zip(argv[::2], argv[1::2]))
            backup = mgr.tasks.copy()
            try:
                for p, d in pairs:
                    mgr.add_or_replace(p, d)
            except Exception:
                mgr.tasks = backup     # all-or-nothing
                raise
        case _:
            raise PlanError(f"unrecognized arguments: '{' '.join(argv)}'")

    mgr.save()

def main():
    try:
        dispatch(sys.argv[1:], Path('~/plan.txt').expanduser())
    except (PlanError, OSError) as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    main()
