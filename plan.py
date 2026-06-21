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

                # Check for orphans during file load
                if (parent := path[:-1]) and parent not in self.tasks:
                    raise PlanError(f"parent task '{stringify(parent)}' does not exist")

                self.tasks[path] = Task(desc, state == '☒')
            except (ValueError, PlanError) as e:
                raise OSError(f"malformed line {idx} in plan.txt: {e}")

    def save(self):
        lines = [render(p, t) for p, t in sorted(self.tasks.items())]
        self.filepath.write_text('\n'.join(lines) + '\n' if lines else '', encoding='utf-8')

    def add(self, path, desc):
        if not (desc := desc.strip()):
            raise PlanError("task description cannot be empty")
        if path in self.tasks:
            raise PlanError(f"task '{stringify(path)}' already exists")
        if (parent := path[:-1]) and parent not in self.tasks:
            raise PlanError(f"parent task '{stringify(parent)}' does not exist")
        self.tasks[path] = Task(desc)

    def edit(self, path, desc):
        if not (desc := desc.strip()):
            raise PlanError("task description cannot be empty")
        if path not in self.tasks:
            raise PlanError(f"task '{stringify(path)}' not found")
        self.tasks[path].desc = desc

    def rm(self, target):
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
  plan                       Show entire plan (or help if empty)
  plan ls [<id>]             Show entire plan, or task <id> and its descendants
  plan add <id> <text...>    Add task <id> (quotes not required for text)
  plan rm <id>               Remove task <id> and all its descendants
  plan edit <id> <text...>   Replace description of task <id>, keeping current state
  plan done <id>             Mark task <id> complete
  plan todo <id>             Mark task <id> incomplete
  plan --help                Show this help
"""

def dispatch(argv, path):
    """Core argument interpreter used by both the CLI and the test-suite."""
    mgr = PlanManager(path)

    match argv:
        case []:
            if not mgr.tasks:
                print(HELP_TEXT, end="")
            else:
                mgr.display()
            return
        case ["--help"]:
            print(HELP_TEXT, end="")
            return
        case ["ls"]:
            mgr.display()
            return
        case ["ls", tgt]:
            mgr.display(parse_num(tgt))
            return
        case ["add", tgt, *text_parts] if text_parts:
            mgr.add(parse_num(tgt), " ".join(text_parts))
        case ["add", *_]:
            raise PlanError("'add' requires an ID and a description")
        case ["rm", tgt]:
            mgr.rm(parse_num(tgt))
        case ["rm", *_]:
            raise PlanError("'rm' requires exactly 1 ID argument")
        case ["edit", tgt, *text_parts] if text_parts:
            mgr.edit(parse_num(tgt), " ".join(text_parts))
        case ["edit", *_]:
            raise PlanError("'edit' requires an ID and a new description")
        case ["done" | "todo" as cmd, tgt]:
            mgr.set_state(parse_num(tgt), cmd == "done")
        case ["done" | "todo" as cmd, *_]:
            raise PlanError(f"'{cmd}' requires exactly 1 ID argument")
        case _:
            raise PlanError(f"unrecognized command or arguments: '{' '.join(argv)}'")

    mgr.save()

def main():
    try:
        dispatch(sys.argv[1:], Path('~/plan.txt').expanduser())
    except (PlanError, OSError) as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    main()
