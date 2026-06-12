
# plan - Deterministic State Management for Autonomous Agents

Autonomous agents excel at problem-solving but often struggle to maintain
long-term, multi-step plans within a finite context window. Relying on an LLM to
hold, shift, and manipulate complex task trees in-memory frequently leads to
hallucination, lost steps, and structural corruption.

`plan` is a lightweight, strictly hierarchical task manager explicitly designed
as a discrete tool for CLI-based AI agents. By offloading task tracking to a
deterministic, fixed-ID architecture, `plan` significantly reduces the cognitive
load on the agent. It provides a stable, queryable source of truth, allowing
agents to reliably execute, track, and dynamically modify workflows without
context degradation.

## Built for Agents

- **Stable Addressing:** Tasks are strictly referenced by absolute,
  dot-separated IDs (e.g., `1.2.1`). Because sibling nodes never shift
  implicitly, the agent is guaranteed to operate on the exact node it intends
  to, even as the tree evolves.
- **Context Window Optimization:** Rather than dumping an entire project state
  into the context window, an agent can query specific subtrees (e.g., `plan
  2.1`) to retrieve only the information relevant to its immediate objective.
- **Atomic Resilience:** Batch operations are transactional. If an agent
  hallucinates an invalid command (such as attempting to create an orphan task),
  `plan` cleanly aborts the transaction and returns a standard error, preventing
  the agent from corrupting its own state file.
- **Decoupled Logic:** Completion states are explicitly independent. The agent
  is in full control of marking tasks complete without having to predict or
  account for automagic cascading behaviors.

## Example Agent Workflow

Imagine a CLI agent tasked with setting up a local web application. Instead of
holding the plan in its prompt, it uses `plan` to structure its thoughts and
execute methodically.

### 1. The agent initializes a high-level plan

```bash
agent@serenity:~$ plan 1 "Provision Database" 2 "Setup Backend API" 3 "Configure Frontend"
```

### 2. The agent focuses on Task 1 and breaks it down dynamically:

```bash
agent@serenity:~$ plan 1.1 "Install PostgreSQL" 1.2 "Create user and schema"
agent@serenity:~$ plan 1
☐ 1 "Provision Database"
☐ 1.1 "Install PostgreSQL"
☐ 1.2 "Create user and schema"
```

### 3. The agent encounters an issue and adapts its plan on the fly:

*The agent realizes port 5432 is blocked. It adds a subtask to resolve this before proceeding, marks it complete when done, and then completes the installation.*

```bash
agent@serenity:~$ plan 1.1.1 "Kill rogue process on port 5432"
agent@serenity:~$ plan complete 1.1.1
agent@serenity:~$ plan complete 1.1
agent@serenity:~$ plan 1
☐ 1 "Provision Database"
☒ 1.1 "Install PostgreSQL"
☒ 1.1.1 "Kill rogue process on port 5432"
☐ 1.2 "Create user and schema"
```

### 4. Cleaning up:

*Once a massive subtree is complete, the agent can delete it to prune its context entirely, or leave it marked complete for an audit trail.*

```bash
agent@serenity:~$ plan complete 1
agent@serenity:~$ plan 2
☐ 2 "Setup Backend API"
```
