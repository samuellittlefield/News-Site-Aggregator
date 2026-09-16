---
type: regex
target: {source: file, path: frontend/src/components/GenericBallotBar.tsx}
pattern: "poll-(red|blue)"
match: contains
---
AC-3: party data uses the new poll-red/poll-blue tokens rather than the
old dark-tuned red-400/blue-400 classes.
