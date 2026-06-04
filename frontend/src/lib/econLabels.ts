// Labels in the Economist/YouGov PDFs come out of the text layer with spaces
// stripped ("Stronglyapprove", "Notsure", group lines like "PartyIDwithLeaners").
// These helpers turn them back into readable text for display.

// Complete map of the (bounded) row labels that appear across tracked questions:
// approve/disapprove scales, importance scales, direction-of-country, no-opinion.
const ROW_LABELS: Record<string, string> = {
  Approve: "Approve",
  Disapprove: "Disapprove",
  Stronglyapprove: "Strongly approve",
  Somewhatapprove: "Somewhat approve",
  Somewhatdisapprove: "Somewhat disapprove",
  Stronglydisapprove: "Strongly disapprove",
  Neitherapprovenordisapprove: "Neither",
  Notsure: "Not sure",
  Noopinion: "No opinion",
  Totals: "Totals",
  Generallyheadedintherightdirection: "Right direction",
  Offonthewrongtrack: "Wrong track",
  Important: "Important",
  Unimportant: "Unimportant",
  VeryImportant: "Very important",
  SomewhatImportant: "Somewhat important",
  NotveryImportant: "Not very important",
  NotImportant: "Not important",
};

// Multi-word tokens that appear concatenated in group-header lines.
const GROUP_TOKENS: Record<string, string> = {
  PartyID: "Party ID",
  PartyIDwithLeaners: "Party ID w/ leaners",
  "2024Vote": "2024 Vote",
};

export function prettyLabel(raw: string): string {
  if (ROW_LABELS[raw]) return ROW_LABELS[raw];
  // Safe fallback: only split on camelCase boundaries (lower→upper). This never
  // breaks an all-lowercase concatenation apart, so unknown labels degrade to
  // the raw text rather than being mangled (e.g. "Noopinion" stays intact).
  const spaced = raw.replace(/([a-z])([A-Z])/g, "$1 $2");
  return spaced.charAt(0).toUpperCase() + spaced.slice(1);
}

export function prettyGroup(raw: string): string {
  return raw
    .split(/\s+/)
    .map((tok) => GROUP_TOKENS[tok] ?? tok)
    .join(" · ");
}
