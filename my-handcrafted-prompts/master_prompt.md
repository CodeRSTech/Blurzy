## Master prompt for planning and phased refactors

Use this prompt when a task first needs to be understood, refined, and converted into a practical execution plan before implementation begins.

---

## Purpose

Create a fast, reusable planning workflow that works for many kinds of tasks:

- feature additions
- refactors
- bug-fix programs
- architecture cleanup
- UI/UX workflow improvements
- documentation-driven implementation planning

The goal is not only to produce a plan, but to produce a plan that can evolve safely as work progresses.

---

## Core planning philosophy

1. Identify the true core object or concept of the task.
2. Refine the task around that core instead of around scattered symptoms.
3. Separate high-level feature definition from execution planning.
4. Break execution into phases with explicit dependencies.
5. Preserve learning from each phase so later phases can be corrected early.
6. Keep planning artifacts lightweight, local, and easy to update.

---

## Recommended directory structure

Keep planning artifacts under a dedicated directory inside `my-handcrafted-prompts`.

Example:

```text
my-handcrafted-prompts/
  task_name/
    task_name.md
    task_name_plan.md
    plan_phases/
      phase_1.md
      phase_2.md
      phase_3.md
      ...
```

### File roles

- `task_name.md`
  - refined problem definition
  - desired behavior
  - scope decisions
  - de-prioritized items

- `task_name_plan.md`
  - high-level execution index
  - planning rules
  - phase map
  - shared documentation conventions

- `plan_phases/phase_N.md`
  - one markdown file per phase
  - each file owns the intent, scope, dependencies, exit criteria, and running notes for that phase

---

## Recommended workflow

### Step 1: Refine the request

Before planning implementation, rewrite the task in clearer and more stable terms:

- what is broken now
- what must become true
- what the user really cares about
- what is core vs incidental

This becomes `task_name.md`.

### Step 2: Define the execution shape

Create a high-level plan index:

- purpose
- workflow rules
- phase list
- note-taking structure
- cross-phase rules

This becomes `task_name_plan.md`.

### Step 3: Split work into phase files

Create one file per phase under `plan_phases/`.

Each phase file should contain:

- phase title
- goal
- scope
- candidate files or components
- dependencies
- exit criteria
- update log

### Step 4: Evolve the plan while working

When a phase is completed or materially investigated:

- append a structured note block to that phase file
- capture what was learned
- capture decisions made
- capture blockers or surprises
- update later phase files if the strategy changed

### Step 5: Treat later phases as editable

The phase files are not static.
They should be revised when earlier work reveals:

- a better abstraction
- a hidden dependency
- a flawed assumption
- an easier or safer path

---

## Structured note block

Use this exact block when recording progress or findings inside a phase file:

```text
[Contributor]: Developer | Copilot
[Timestamp]: YYYY-MM-DDTHH:MM:SS.sss±HH:MM
[Type]: planning | implementation | review | blocker
[Summary]:
- concise update

[Decisions]:
- important decision

[Problems]:
- issue encountered, or `None`

[Next Phase Impact]:
- downstream change required, or `None`
```

### Note block guidance

- `Developer` refers to the human author.
- `Copilot` refers to the assistant.
- `planning` is for plan creation or refinement.
- `implementation` is for completed or partially completed execution work.
- `review` is for findings after inspecting code or results.
- `blocker` is for work that cannot proceed without a decision or prerequisite.

---

## How to choose phases

Good phases are:

- meaningful
- dependency-aware
- narrow enough to be understandable
- broad enough to produce a real milestone

Typical phase categories:

1. establish the core seam or abstraction
2. synchronize or connect existing surfaces
3. fix transform/state/lifecycle correctness
4. normalize actions and remove obsolete paths
5. add primary new capability
6. improve ergonomics or UX
7. add regression protection

Not every task needs all of these, but this is a strong default pattern.

---

## What to record in each phase file

At minimum:

### Goal

What this phase must achieve.

### Scope

What this phase is responsible for, and what it is not.

### Candidate files or components

Where implementation or investigation is likely to happen.

### Dependencies

Which earlier phases must be completed first.

### Exit criteria

What must be true before the phase is considered done.

### Update log

A running history of decisions, discoveries, and changes to downstream strategy.

---

## General planning rules

1. Prefer one stable source of truth for each important concept.
2. Avoid planning around temporary UI state when a deeper model exists.
3. Convert action lists into model-driven behavior whenever possible.
4. Keep destructive or high-risk changes behind explicit phase boundaries.
5. Add tests after the behavior seams are understood.
6. Defer attractive extras if they would destabilize the core plan.

---

## Good prompts to derive from this template

This planning pattern works especially well when the request sounds like:

- "This feature is buggy and incomplete; define it properly first."
- "We need a phased refactor."
- "The implementation will likely churn."
- "I want the work documented as it evolves."
- "The plan itself must be refined before coding."

---

## Quick-start adaptation template

Copy and adapt this skeleton for a new task:

```text
Task name: <task_name>

Core object or concept:
- <thing the task really revolves around>

Planning directory:
- my-handcrafted-prompts/<task_name>/

Files:
- <task_name>.md
- <task_name>_plan.md
- plan_phases/phase_1.md
- plan_phases/phase_2.md
- ...

Planning rules:
1. Refine the task before implementation.
2. Keep one markdown file per phase.
3. Append structured note blocks as work progresses.
4. Update later phases when earlier phases reveal better strategy.
5. Keep high-level scope separate from execution details.
```

---

## Expected outcome

Using this structure should make it faster to:

- start future planning sessions
- preserve reasoning across long refactors
- reduce repeated re-analysis
- hand off context between Developer and Copilot
- keep evolving plans coherent instead of fragmented
