---
type: baseline
baseline_file: baseline-diff.patch
criteria: |
  The reference diff is the actual shipped, human-approved implementation
  of this feature. Score how well the candidate's diff satisfies the same
  acceptance criteria by any reasonable route — exact class names or file
  boundaries don't need to match the reference, but the same tokens
  (glass-base, glass-panel, poll-red/poll-blue), the same scoping (only
  the Polling page's exclusive components), and the same out-of-scope
  discipline (Dashboard untouched) should be present.
---
Rubric-graded comparison against the real merged PR, not just a pass/fail
regex.
