// Labels in the Economist/YouGov PDFs come out of the text layer with spaces
// stripped ("Stronglyapprove", "Notsure", group lines like "PartyIDwithLeaners").
// These helpers turn them back into readable text for display.

const ROW_LABELS: Record<string, string> = {
  Approve: "Approve",
  Disapprove: "Disapprove",
  Stronglyapprove: "Strongly approve",
  Somewhatapprove: "Somewhat approve",
  Somewhatdisapprove: "Somewhat disapprove",
  Stronglydisapprove: "Strongly disapprove",
  Notsure: "Not sure",
  Totals: "Totals",
  Generallyheadedintherightdirection: "Right direction",
  Offonthewrongtrack: "Wrong track",
};

// Multi-word tokens that appear concatenated in group-header lines.
const GROUP_TOKENS: Record<string, string> = {
  PartyID: "Party ID",
  PartyIDwithLeaners: "Party ID w/ leaners",
  "2024Vote": "2024 Vote",
};

// Known words for the regex fallback splitter (longest first so greedy matches win).
const WORDS = [
  "Strongly", "Somewhat", "Generally", "headed", "into", "the", "right",
  "direction", "wrong", "track", "approve", "disapprove", "Not", "sure",
  "Off", "on",
].sort((a, b) => b.length - a.length);

export function prettyLabel(raw: string): string {
  if (ROW_LABELS[raw]) return ROW_LABELS[raw];
  // Regex fallback: greedily split concatenated known words, capitalize first.
  const re = new RegExp(WORDS.join("|"), "g");
  const spaced = raw.replace(re, (m) => ` ${m}`).trim();
  if (spaced !== raw) {
    return spaced.charAt(0).toUpperCase() + spaced.slice(1);
  }
  return raw;
}

export function prettyGroup(raw: string): string {
  return raw
    .split(/\s+/)
    .map((tok) => GROUP_TOKENS[tok] ?? tok)
    .join(" · ");
}
