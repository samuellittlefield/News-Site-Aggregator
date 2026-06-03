import { useState } from "react";
import {
  CandidateSummary,
  addManualTag,
  confirmTag,
  rejectTag,
  useCandidates,
  useIssueTaxonomy,
  usePendingTags,
} from "../api/client";

const OFFICE_LABELS: Record<string, string> = { H: "House", S: "Senate", G: "Governor" };
const PARTY_STYLES: Record<string, string> = {
  DEM: "bg-blue-950 text-blue-400 border-blue-800",
  REP: "bg-red-950 text-red-400 border-red-800",
  IND: "bg-gray-800 text-gray-300 border-gray-600",
};

function ConfidenceBar({ value }: { value: number | null }) {
  if (value == null) return null;
  const pct = Math.round(value * 100);
  const color = value >= 0.8 ? "bg-green-500" : value >= 0.6 ? "bg-yellow-500" : "bg-orange-500";
  return (
    <div className="flex items-center gap-1.5">
      <div className="h-1.5 w-16 bg-gray-800 rounded-full overflow-hidden">
        <div className={`h-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-[10px] text-gray-500">{pct}%</span>
    </div>
  );
}

// ── Pending Tags Tab ──────────────────────────────────────────────────────────

function PendingTagsTab() {
  const { tags, loading, refresh } = usePendingTags();
  const [processing, setProcessing] = useState<Set<number>>(new Set());

  const handle = async (tagId: number, candidateId: number, action: "confirm" | "reject") => {
    setProcessing(prev => new Set([...prev, tagId]));
    try {
      if (action === "confirm") await confirmTag(candidateId, tagId);
      else await rejectTag(candidateId, tagId);
      refresh();
    } finally {
      setProcessing(prev => { const s = new Set(prev); s.delete(tagId); return s; });
    }
  };

  if (loading) return <div className="h-32 bg-gray-900 rounded-xl animate-pulse" />;

  if (tags.length === 0) {
    return (
      <div className="text-center py-12 text-gray-600">
        <p className="text-2xl mb-2">✓</p>
        <p>No pending AI suggestions. Run the issue tagger to generate new ones.</p>
        <p className="text-xs mt-2">POST /api/admin/run-tagger to trigger manually</p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <p className="text-xs text-gray-600">{tags.length} suggestions awaiting review · sorted by confidence</p>
      {tags.map(tag => (
        <div key={tag.tag_id} className="bg-gray-900 border border-gray-800 rounded-xl p-4 space-y-3">
          <div className="flex items-start justify-between gap-4">
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <span className="font-semibold text-white text-sm">{tag.candidate_name}</span>
                {tag.candidate_party && (
                  <span className={`text-[10px] font-bold border rounded px-1 py-px ${PARTY_STYLES[tag.candidate_party] ?? "bg-gray-800 text-gray-400 border-gray-700"}`}>
                    {tag.candidate_party}
                  </span>
                )}
                <span className="text-xs text-gray-500">
                  {OFFICE_LABELS[tag.candidate_office]} · {tag.candidate_state}
                  {tag.candidate_district ? `-${tag.candidate_district}` : ""}
                </span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-xs font-medium text-purple-300 bg-purple-950/50 border border-purple-800 rounded-full px-2 py-0.5">
                  {tag.issue_label}
                </span>
                <ConfidenceBar value={tag.confidence} />
              </div>
            </div>

            <div className="flex items-center gap-2 shrink-0">
              <button
                onClick={() => handle(tag.tag_id, tag.candidate_id, "confirm")}
                disabled={processing.has(tag.tag_id)}
                className="text-xs px-3 py-1.5 bg-green-900/50 hover:bg-green-900 border border-green-800 text-green-400 rounded-lg transition-colors disabled:opacity-50"
              >
                ✓ Confirm
              </button>
              <button
                onClick={() => handle(tag.tag_id, tag.candidate_id, "reject")}
                disabled={processing.has(tag.tag_id)}
                className="text-xs px-3 py-1.5 bg-gray-800 hover:bg-gray-700 border border-gray-700 text-gray-400 rounded-lg transition-colors disabled:opacity-50"
              >
                ✗ Reject
              </button>
            </div>
          </div>

          {tag.supporting_text && (
            <blockquote className="text-xs text-gray-500 italic border-l-2 border-gray-700 pl-3 leading-relaxed">
              "{tag.supporting_text}"
            </blockquote>
          )}
        </div>
      ))}
    </div>
  );
}

// ── Candidate Browser Tab ─────────────────────────────────────────────────────

function CandidateBrowserTab() {
  const [officeFilter, setOfficeFilter] = useState<string>("H");
  const [stateFilter, setStateFilter] = useState<string>("");
  const [selectedCandidate, setSelectedCandidate] = useState<CandidateSummary | null>(null);
  const [newIssue, setNewIssue] = useState<string>("");
  const [addingTag, setAddingTag] = useState(false);
  const taxonomy = useIssueTaxonomy();

  const { candidates, loading } = useCandidates(officeFilter || undefined, stateFilter || undefined);

  const handleAddTag = async () => {
    if (!selectedCandidate || !newIssue) return;
    setAddingTag(true);
    try {
      await addManualTag(selectedCandidate.id, newIssue);
      setNewIssue("");
    } finally {
      setAddingTag(false);
    }
  };

  return (
    <div className="space-y-4">
      {/* Filters */}
      <div className="flex items-center gap-3">
        <div className="flex gap-1">
          {["H", "S", "G", ""].map(o => (
            <button
              key={o}
              onClick={() => setOfficeFilter(o)}
              className={`text-xs px-2.5 py-1 rounded-lg border transition-colors ${
                officeFilter === o ? "border-gray-600 text-gray-300 bg-gray-800" : "border-gray-800 text-gray-600 hover:text-gray-400"
              }`}
            >
              {o ? OFFICE_LABELS[o] : "All"}
            </button>
          ))}
        </div>
        <input
          type="text"
          placeholder="State (e.g. NY)"
          value={stateFilter}
          onChange={e => setStateFilter(e.target.value.toUpperCase())}
          maxLength={2}
          className="text-xs bg-gray-900 border border-gray-700 rounded-lg px-3 py-1.5 text-white w-24 focus:outline-none focus:border-gray-500"
        />
        <span className="text-xs text-gray-600">{candidates.length} candidates</span>
      </div>

      {loading ? (
        <div className="h-32 bg-gray-900 rounded-xl animate-pulse" />
      ) : (
        <div className="grid grid-cols-2 gap-2 max-h-96 overflow-y-auto pr-1">
          {candidates.map(c => (
            <button
              key={c.id}
              onClick={() => setSelectedCandidate(c === selectedCandidate ? null : c)}
              className={`text-left p-3 rounded-xl border transition-colors space-y-1 ${
                selectedCandidate?.id === c.id
                  ? "border-purple-700 bg-purple-950/30"
                  : "border-gray-800 bg-gray-900 hover:border-gray-700"
              }`}
            >
              <div className="flex items-center justify-between gap-2">
                <span className="text-xs font-medium text-white truncate">{c.name}</span>
                {c.party && (
                  <span className={`text-[9px] font-bold border rounded px-1 shrink-0 ${PARTY_STYLES[c.party] ?? "bg-gray-800 text-gray-400 border-gray-700"}`}>
                    {c.party}
                  </span>
                )}
              </div>
              <p className="text-[10px] text-gray-500">
                {OFFICE_LABELS[c.office]} · {c.state}{c.district ? `-${c.district}` : ""}
                {c.cook_rating ? ` · ${c.cook_rating}` : ""}
              </p>
              {c.confirmed_issues.length > 0 && (
                <div className="flex flex-wrap gap-1">
                  {c.confirmed_issues.slice(0, 3).map(code => (
                    <span key={code} className="text-[9px] bg-purple-950/50 text-purple-400 border border-purple-900 rounded-full px-1.5 py-px">
                      {code}
                    </span>
                  ))}
                </div>
              )}
            </button>
          ))}
        </div>
      )}

      {/* Add tag panel */}
      {selectedCandidate && (
        <div className="border border-gray-700 rounded-xl p-4 space-y-3 bg-gray-950">
          <p className="text-sm font-medium text-white">{selectedCandidate.name}</p>
          <div className="flex items-center gap-2">
            <select
              value={newIssue}
              onChange={e => setNewIssue(e.target.value)}
              className="flex-1 text-xs bg-gray-900 border border-gray-700 rounded-lg px-3 py-1.5 text-white focus:outline-none focus:border-gray-500"
            >
              <option value="">— Select issue —</option>
              {taxonomy.map(t => (
                <option key={t.code} value={t.code}>{t.label}</option>
              ))}
            </select>
            <button
              onClick={handleAddTag}
              disabled={!newIssue || addingTag}
              className="text-xs px-3 py-1.5 bg-purple-900/50 hover:bg-purple-900 border border-purple-800 text-purple-300 rounded-lg transition-colors disabled:opacity-50"
            >
              {addingTag ? "Adding…" : "Add Tag"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Main Admin Page ───────────────────────────────────────────────────────────

type AdminTab = "pending" | "candidates";

export function AdminPage() {
  const [tab, setTab] = useState<AdminTab>("pending");

  return (
    <div className="min-h-screen bg-gray-950">
      <div className="max-w-4xl mx-auto px-4 py-8 space-y-6">
        <div className="space-y-1">
          <h2 className="text-xl font-bold text-white tracking-tight">Election Intelligence Admin</h2>
          <p className="text-xs text-gray-600">Internal use only · Issue tag review + candidate management</p>
        </div>

        {/* Tabs */}
        <div className="flex gap-1 border-b border-gray-800 pb-0">
          {([["pending", "Pending AI Tags"], ["candidates", "Candidate Browser"]] as [AdminTab, string][]).map(([id, label]) => (
            <button
              key={id}
              onClick={() => setTab(id)}
              className={`text-sm px-4 py-2 border-b-2 transition-colors -mb-px ${
                tab === id ? "border-purple-500 text-white" : "border-transparent text-gray-500 hover:text-gray-300"
              }`}
            >
              {label}
            </button>
          ))}
        </div>

        {tab === "pending" && <PendingTagsTab />}
        {tab === "candidates" && <CandidateBrowserTab />}
      </div>
    </div>
  );
}
