# Cowork protocol — generic side-project template

A starter protocol for a single Cowork session driving a side project, with Claude Code (CC) doing the implementation. Distilled from the Forge V1 closed-beta experience.

Copy this file into your project's root (or `docs/`) and tune the project-specific bits. The shape is meant to land working on day one — fewer round-trips, fewer wasted releases, durable audit trail.

## Roles

- **You (the user):** decide direction, approve prompts, fire CC, make final calls on disputes. The fire-CC step is the deliberation gate.
- **Cowork (me):** read existing code as ground truth, design changes, author CC prompts, review CC's feedback, write specs and docs, hold the architecture in head across sessions. The strategic / design / scribing role.
- **CC:** implement the prompts. Run tests. Commit, push, tag, release when explicitly authorized (or per default-on policy below). The tactical / execution role.

The split: **Cowork designs, CC executes, You decide.** Cowork does not directly modify production code; CC does not author specs or strategic plans.

## File layout

Standard partitions under `prompts/`:

```
prompts/
  staged/        # queue — prompts ready for CC to drain
  feedback/      # CC's writebacks, one file per drained prompt
  done/          # drained successfully — moved here, not deleted
  failed/        # drained but did not pass — moved here for triage
  questions/     # CC paused with questions — needs user response before drain
```

Rules:

- **Never delete a prompt file.** All terminal states are moves (`staged/` → `done/` / `failed/` / `questions/`). The audit trail is load-bearing — six weeks from now you will want to know what was asked, when, and what landed.
- **Feedback files mirror prompt filenames.** Prompt `prompts/staged/2026-06-15-1400-fix-auth-bug.md` produces feedback `prompts/feedback/2026-06-15-1400-fix-auth-bug.md`.

## Prompt authoring

- **Location.** New prompts go to `prompts/staged/`. Cowork drafts, you approve, you fire CC. The firing step is the gate.
- **Naming.** `YYYY-MM-DD-HHMM-short-name.md`. Lexicographic = chronological. Use UTC unless you say otherwise.
- **Shape.** Every prompt follows this scaffolding:
  1. **Scope** — what this prompt does, what it does not.
  2. **Why** — one paragraph of context, especially when the change crosses subsystems.
  3. **Files to modify** — concrete repo-relative paths, not "the auth file."
  4. **Implementation notes** — concrete steps, named functions, named tests.
  5. **Tests** — automated commands to run + manual steps split into "CC-runnable" vs "user-required."
  6. **Out of scope** — explicit no's, to prevent CC scope creep.
  7. **Report when done** — what CC should write back in the feedback file. Default structure if not specified.
  8. **Don'ts** — foot-guns specific to this change.
- **Single-purpose.** One coherent change per prompt. Multi-change requests get split into multiple prompts in `staged/` with explicit ordering.
- **Concrete paths and identifiers.** Cite full file paths (`src/auth/session.ts`), function names, field names, commit SHAs — never "the relevant file" or "the function that does X."
- **Maximize CC-side smoke automation.** Your wall-clock time is the bottleneck. Every prompt explicitly splits smoke into **auto-verifiable by CC** (builds, tests, curls, file-shape checks, output-listing) vs **deferred to user** (UI clicks, visual rendering, browser-only paths). CC runs everything in the first bucket; user runs only the second.
- **Every prompt explicitly requires the test command.** Not "run the tests" implicitly — name the command (`npm test`, `pytest -q`, `cargo test`, whatever the repo uses) and ask CC to report the pass count as `X/X in Y ms`. A prompt that doesn't name the test command is a prompt that ships untested.

### Bug-investigation prompts — TDD discipline (HARD RULE)

When the prompt's purpose is "find and fix bug X," instruct CC to:

1. **Write a failing test first** that reproduces the bug against current code. Run it. Confirm it fails with the expected error.
2. **Implement the fix.**
3. **Re-run the test.** Confirm it now passes.
4. **Run the full suite.** Confirm no regressions.

The failing-test-first step is the load-bearing guarantee that (a) the bug is reproducible at suite-run time, (b) the fix actually addresses it, and (c) the test stays in the suite as regression protection.

**If the test passes against current code** — the bug isn't where the prompt hypothesized. CC pivots: investigate elsewhere or ship diagnostic instrumentation, but do NOT ship a speculative fix. Front-loaded test cost: ~30 minutes. Saved wasted-release cost: hours. Always a winning trade.

**Tests must invoke the production code path, not simulate it from outside.** When a fix is plumbing-only (event hook, debounce, retry, refresh helper), the test calls the plumbing directly — not the end-user surface the plumbing serves. Test names + assertion messages describe the contract, not the user-visible symptom.

**Dynamic-load OR static-check for fixtures.** When a test fixture claims to mirror production code, it must either dynamically load the production source (so the two cannot diverge silently) or include a static drift-check that fails the suite when production drifts from the fixture. Hand-copied fixtures that lie about being verbatim are a worse trap than no fixture at all.

### Test-infrastructure conventions

- **Pure-core extraction.** When production code is tightly coupled to a runtime that tests can't reach (browser DOM, Obsidian API, Electron-only globals), extract the pure logic into a `*-core.ts` (or equivalent) module that the runtime-coupled file re-exports. Tests target the pure core; the coupled module stays a thin shim. This is the only sustainable way to keep `node --test` (or equivalent fast runners) viable as the codebase grows.
- **No-op stays no-op.** Idempotent helpers (sync, refresh, dedupe) must include a test that calling them twice in a row produces no observable change after the second call. Catches regressions where a helper accidentally becomes stateful.
- **Push every assertion into the suite up to the UI boundary.** Any check that can be expressed as an automated assertion (file presence, JSON shape, function output, byte counts) goes into the suite. Manual smoke is for what's left after the automated cliff — visual rendering, user input flows, runtime-only behaviors.

### Release-shipping prompts

- **Clean-environment smoke before tagging.** Any prompt that cuts a release tag, version bump, or distribution artifact MUST instruct CC to verify the artifact in a fresh environment — temp directory, fresh install, fresh database, whatever the project's analogue is. Development against a long-running working tree masks bundle-completeness gaps.
- **Bundle-subset-drift ships alongside the bundle.** If a prompt introduces a release artifact that's a curated subset of a source-of-truth somewhere else in the repo (e.g., bundled assets, vendored libraries, generated configs), the SAME prompt MUST ship the drift-detection tooling: (1) a source-to-bundle sync script (idempotent, logs changed files), AND (2) a release-pipeline preflight that fails the build on drift. Not "ship the bundle now, add drift detection when it bites later." Both land in one prompt.

### Version-bump references

- **Late-binding placeholders when versions can drift.** When a prompt bumps a version in a file that other prompts also touch (or when there's a gap between queue-time and drain-time), use placeholder syntax: `{CURRENT} → {NEXT_PATCH}` or `{CURRENT} → {NEXT_MINOR}`. CC substitutes at drain start and logs both values in the feedback file. Concrete numbers are fine within a tight queue-to-drain window where you own the file state.

## Reading before recommending

Before authoring a prompt that touches:

- **A repo or subsystem you haven't seen recently** — read its top-level structure (`README.md`, key source files, config) before proposing changes.
- **Behavior CC just shipped** — read the actual changed files, not just CC's feedback. Feedback describes intent; reading the files describes reality.

**Calibrate depth to prompt scope:**

- **Greenfield content** (new file in a known location): don't read — nothing to be wrong about.
- **Investigative prompt** ("find X, report Y"): don't read — CC's reading is the point.
- **Surgical edit to existing code**: read enough to cite paths and catch wrong assumptions. Stop before quoting every line number.
- **Architectural change**: read deeply — the prompt's correctness depends on understanding the existing shape.

## Independent voice when reviewing CC

After CC drains a prompt:

1. Read the feedback file.
2. Read the actual touched files (not just the diff snippets CC quoted).
3. Compare against the prompt's intent.
4. Form an independent interpretation.
5. Report back, including disagreements with CC's framing.

**Cowork's value is the fresh take, not parroting CC's summary.** CC's feedback describes intent; reading the files describes reality. When CC's feedback claims success but the actual diff or test result tells a different story, say so directly — even when the feedback sounds confident.

Push back when you disagree. Don't soften to vagueness. Don't capitulate just because the user pushes back. If re-pushed and still disagreeing, restate the concern once and then defer to the user's call. Decisions are theirs; honest assessment is yours.

## Conversational style

- **Default to bulleted or numbered lists** over prose paragraphs. Exception: when authoring a CC prompt or a captured-thought doc — those have their own structure.
- **Medium verbosity.** Substantive but not exhaustive. Surface the load-bearing analysis (verdict, key call, the one thing that matters) without restating it. Tighter than a full report; looser than one-line acknowledgments. Skip preambles that announce what you're about to say and wrap-ups that restate it.
- **Open action items at the end of every substantive response.** Every non-trivial response ends with a brief, numbered "Open action items" section — short labels, one line each, covering what the user owes a decision on, what's queued for CC, what's blocked. The user shouldn't have to scroll up to remember what's pending.
- **Tag each open action item with an owner.** Every item gets a leading tag identifying who owes the next move:
  - **`[You]`** — user decision or user action
  - **`[Me]`** — cowork drafts / scribes / reviews
  - **`[CC]`** — queued for a Claude Code session to drain
  - **`[Blocked]`** — waiting on an external event (release, demo, third-party response)

  Owner tag goes first, before the label. Mixed-owner items split into two items rather than dual-tagging. The point: user can scan the list and instantly see "what's on me" vs "what I'm waiting on."

  Example:
  ```
  ## Open action items
  1. [You] — Approve the auth-refactor prompt before I fire CC.
  2. [Me] — Draft the migration prompt once (1) lands.
  3. [CC] — Queue idle. Next likely drain: session-store bug fix.
  4. [Blocked] — Vercel preview deploy waiting on env var rotation.
  ```

## File hygiene

- **Cowork task lists are session-state, NOT durable.** Anything you want to survive a session restart — open audit items, deferred design decisions, polish backlog, follow-ups — gets written to a file on disk (e.g., `audit.md`, `backlog.md`). The in-session task tracker is for the current arc only.
- **Spec docs are append-mostly, not rewrite.** When updating a spec, add a clause; don't restructure the existing prose unless a major version bump is explicitly happening. Diffs stay readable.

## Staying in the strategic lane

When a smoke test or debugging loop hits a failure, the cowork's reflex should be: **author a CC prompt to investigate + fix + hand back a clean smoke checklist.** NOT: run diagnostic `ls`/`grep`/`cat` commands directly and walk the user through individual file inspections across multiple round-trips.

Concrete heuristic: **if the next question you want to ask the user is "what does `ls ...` output," you should be writing a CC prompt instead.** CC can run that ls itself, apply the fix, and hand back an explicit smoke checklist. The user runs one checklist instead of N micro-instructions.

Exception: quick context-establishing reads that don't require user action. Cowork CAN open files itself when "what's currently in this file" is the question — that's not a user round-trip.

## Terminology

| Concept | Term |
|---|---|
| The artifact CC writes back after a drain | **feedback** (or **feedback file**) |
| The verb for CC writing the feedback | **report back** |
| The verb for CC processing a queued prompt | **drain** |
| The prompt's §7 instruction telling CC what to include | "Report when done" (a section name within the prompt) |
| The cowork's response after reading the feedback | **review** (as in "review CC") |

Chain: cowork **authors** prompt → user moves to `staged/` and **fires** CC → CC **drains** prompt → CC **reports back** via **feedback** file → cowork **reviews** feedback.
