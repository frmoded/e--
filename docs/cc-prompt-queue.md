# CC prompt queue — generic side-project template

This file tells Claude Code (CC) how to drain prompts authored by the Cowork session. It is the companion to `cowork-protocol.md`.

When the user fires `claude -p "drain prompts"` (or `do prompt`, or equivalent), CC reads this file plus the next prompt in `prompts/staged/` and proceeds per the rules below.

## Queue location and partitions

```
prompts/
  staged/        # queue — drain in lexicographic order (oldest filename first)
  feedback/      # CC writes feedback here, mirroring the prompt filename
  done/          # move prompt here after successful drain
  failed/        # move prompt here after unsuccessful drain
  questions/     # move prompt here if CC must pause for user input
```

**Drain order:** oldest filename first (lexicographic). The naming convention `YYYY-MM-DD-HHMM-name.md` makes lexicographic = chronological.

**One prompt per `do prompt` invocation.** The verb "drain prompts" (plural) is the only thing that authorizes multi-prompt processing in one CC session.

## Drain ritual (per prompt)

1. **Read the prompt.** Read the entire file before touching anything.
2. **Version-bump sanity check** (see "Hard rules" below) — reconcile any version refs in the prompt against current file state. Pause and flag if drift exists.
3. **Read the cited files** named in §3 ("Files to modify"). Confirm paths exist and the surrounding code matches the prompt's assumptions. If a path is wrong or an assumption is broken, flag in feedback and pause.
4. **Follow the prompt's implementation notes.** For bug-investigation prompts, the TDD discipline (failing test first) is non-negotiable — see "Hard rules."
5. **Run the test command** named in the prompt's §5. Report pass count as `X/X in Y ms` in the feedback file.
6. **Run any other auto-verifiable smoke** named in §5. Report results.
7. **Git operations** per the default-on policy in "Hard rules."
8. **Write the feedback file** to `prompts/feedback/<same-filename>.md` per the structure below.
9. **Move the prompt** from `staged/` to `done/` (or `failed/` / `questions/`). Never delete.
10. **Post a brief chat summary** linking to the feedback file. The feedback file is the canonical record; the chat summary is for the user's scrolling convenience.

## Feedback file structure

Default structure (the prompt's §7 may override):

```
# Feedback — <prompt name>

## §0. Drain metadata

- Drained against commit: <SHA — read with `git rev-parse HEAD` at drain start; do not recall or infer it>
- Versions before/after (if any version bumps): manifest/package/etc. — was X, now Y
- Test suite result: X/X in Y ms
- Git ops: commit SHAs created, tags, releases; local HEAD vs `origin/<branch>` (ahead/behind). A failed push is expected and not a problem — see the "Git state" hard rule.

## §1. Outcome

### §1.1 Cases (for bug-fix prompts: the failing-test cases)

### §1.2 Pre-fix verbatim output (for bug-fix prompts: failing-test output)

### §1.3 Fix

### §1.4 Post-fix verbatim output (for bug-fix prompts: passing-test output)

### §1.5 Full suite

## §2. Notes / follow-ups

Anything worth flagging for cowork review — surprises, prompt assumptions that
didn't hold, candidate follow-up prompts, code smells noticed in passing.
```

For non-bug-fix prompts (new features, refactors, docs), §1 can collapse to a single "what shipped" section. The structure above is the maximal form.

## Hard rules

### One prompt per `do prompt` invocation

"Drain prompts" (plural) is the only verb that authorizes multi-prompt processing in one CC session. Otherwise, drain one, write feedback, stop.

### Never invent work

Empty queue → report "queue empty" and stop. Don't synthesize prompts from inferred user intent. Don't drain a prompt from `done/` because it looks similar to current work.

### Never delete a prompt file

All terminal states are moves: `staged/` → `done/` / `failed/` / `questions/`. Same for feedback files — once written, they stay. Preserves the audit trail.

### Git operations are default-on, opt-out per prompt

CC may commit, push, tag, and create GitHub releases (via `gh release create`, etc.) as part of completing the prompt's work, whenever the change naturally calls for it (bug fix → commit + push; release prompt → commit + push + tag + GH release). The user does NOT need to authorize each separately.

The prompt can override with explicit phrases like "leave uncommitted for review" or "don't tag yet" — those take precedence. **Destructive operations** (`git push --force`, `git reset --hard`, branch deletion, history rewrite) remain opt-in and require explicit per-prompt authorization.

**Commit message convention:** include the prompt filename in brackets at the start of the message header for audit trail:

```
[2026-06-15-1400-fix-auth-bug] session-store: use stable hash for key derivation
```

Body content stays per-change.

**Always report** in the feedback file's §0: commit SHAs, pushed branches, tag names, GH release URLs.

### Git state: report what `git` says, and pushing is the user's job (HARD RULE)

Two failures observed repeatedly in practice: (a) the "drained against" SHA reported from memory instead of from git, and (b) a failed `git push` misdiagnosed as a policy/harness block.

- **Read git state, never recall it.** The §0 "drained against" SHA is `git rev-parse HEAD` at drain start. Ahead/behind is `git rev-list --count origin/<branch>..HEAD`. Report the command output, not an inference.
- **The sandbox has no network.** `git push` and any remote fetch will fail from the CC sandbox — this is expected, NOT a harness or policy block; do not invent an explanation. Commit locally; report local HEAD and ahead/behind. **A failed push is never a drain failure.** Pushing to the remote is the user's job, from their own machine. Do not retry pushes.

### No out-of-band commits (HARD RULE)

Every code commit traces to a staged prompt. If a fix is made outside a normal drain (an ad-hoc session, a quick follow-up), it STILL leaves a feedback note: write `prompts/feedback/<date>-<short-name>.md` describing what changed and why, with a commit header that names it. A commit with no feedback note erodes the load-bearing audit trail (cf. the `6b056c8` follow-up that had to be reconstructed retroactively).

### Confirm queue + HEAD before draining (HARD RULE)

Before draining, check `prompts/staged/` and `git log --oneline -3`. Do not act on a prompt that has already been drained — its commit is in the log and it has moved to `done/`. Queue and git state change between queue-time and drain-time; reconcile against reality first.

### Version-bump sanity check (HARD RULE)

Before touching any code, for every file the prompt declares a version bump on (`package.json`, `manifest.json`, `Cargo.toml`, etc.), read the file's current value and reconcile with the prompt:

1. **Placeholder syntax** (`{CURRENT} → {NEXT_PATCH}`, `{CURRENT} → {NEXT_MINOR}`): substitute live values, log both in §0 of the feedback file ("package.json was 1.2.3 at drain start; bumping to 1.2.4"), proceed.
2. **Concrete numbers that match reality** (prompt says `1.2.3 → 1.2.4` and file says `1.2.3`): proceed, log the bump in §0 as usual.
3. **Concrete numbers that DON'T match** (prompt says `1.2.0 → 1.2.1` but file says `1.2.3`): **pause and flag**. One-line message: "Prompt assumes package.json at 1.2.0; actual is 1.2.3. Proceed with `1.2.3 → 1.2.4`, or pause for re-authorization?" Wait for explicit answer. Do NOT silently correct. Do NOT bump backward. Do NOT guess intent.

### TDD discipline for bug-fix prompts (HARD RULE)

When a prompt's stated purpose is "find and fix bug X" (or any bug-fix shape):

1. **Write a failing test first** that reproduces the bug against current code.
2. **Run it.** Confirm it fails with the expected error or assertion failure.
3. **Capture the verbatim output** for the feedback file's §1.2.
4. **Implement the fix.**
5. **Re-run the test.** Confirm it now passes.
6. **Capture the verbatim output** for §1.4.
7. **Run the full suite.** Confirm no regressions. Capture for §1.5.

The order matters — test first, then fix. If you accidentally ship the fix before writing the test, do NOT recover by `git stash`'ing the fix and re-running to fake a pre-fix capture. Instead, note the ordering inversion in §2 of the feedback. Honesty about procedure beats fake reconstruction.

**If the failing test passes against current code** — the bug isn't where the prompt hypothesized. Do NOT ship a speculative fix. Either pivot to investigate elsewhere or ship diagnostic instrumentation only. Report the pivot decision explicitly in feedback.

### Test fixtures must not lie about being verbatim

If a test fixture's docstring or comment claims to "mirror production" or "match the production helper," the fixture MUST either (a) dynamically load production source at test time, or (b) include a static drift-check assertion that fails the suite when production drifts. Hand-copied fixtures that claim verbatim status but silently diverge are a worse trap than no fixture at all. If you ship such a fixture without dynamic-load or drift-check, flag the gap in §2 with a candidate follow-up prompt.

### Tests invoke production, not simulate it from outside

When a fix is plumbing-only (event hook, debounce, retry, refresh helper), the test must call the plumbing directly — not the end-user surface the plumbing serves. A test that simulates the surface via a parallel code path doesn't prove the production plumbing was actually invoked.

### Clean-environment smoke before tagging any release

When a prompt cuts a release (`gh release create`, version bump, tagged push), perform a clean-environment smoke FIRST: fresh temp directory or fresh database or fresh container, install/unpack the release artifact, verify the install structure matches what production would produce, exercise any non-UI path that can be verified from the sandbox.

Long-running working trees mask bundle-completeness gaps. The fresh environment is the only check that catches "the bundled subset works in isolation."

### Respect normal CC safety rules

This queue convention does not override anything else. No auto-merging PRs. No destructive operations without confirmation. No editing files outside the project root. No skipping `.gitignore`'d secrets even if their content would be useful for the prompt.

## Smoke automation

Every prompt's §5 splits smoke into **CC-runnable** (builds, tests, curls, file-shape checks, output-listing, diffs) and **user-required** (UI clicks, visual rendering, browser-only paths).

CC runs everything in the first bucket in the sandbox. Report results verbatim — pass counts, output excerpts, file sizes, byte counts. Do not paraphrase test output; paste it.

The user runs only the second bucket. CC's job is to leave the user with a single explicit checklist of "open this URL, click X, confirm Y," not a debugging trail.

## Backtick trap (language-agnostic version)

When embedding code-as-string inside a host language (Python in JS template literals, SQL in Rust strings, HTML in TypeScript strings, etc.), the host language's quote/escape characters are off-limits inside the embedded code. Specifically:

- JS template literals use backticks → embedded code (Python, etc.) cannot use backticks even in docstrings or comments.
- Python triple-quoted strings → embedded code cannot use unescaped triple-quotes.
- Rust raw strings `r"..."` → adjust the `#` count when embedded code has `"#` sequences.

If a prompt has CC writing one language inside another language's string, CC reviews the embedded code for the host language's reserved chars before saving and substitutes or escapes as needed. Flag any substitution in §2 so cowork can audit.

## Prompt filename collision

If a prompt with the same name already exists in `done/` or `failed/`, do NOT overwrite. Pause and report. The user will rename the new prompt before re-firing.

## Questions partition

If during a drain CC discovers that proceeding requires information not in the prompt (an ambiguous spec, a missing file, a contradiction between two prompt sections), move the prompt to `prompts/questions/`, write a feedback file with §1 containing the specific question(s), and stop. Do not guess. Do not partial-ship.

The user reviews, adds answers to the prompt (or writes a successor), and moves it back to `staged/` for re-drain.
