import { createContext, useContext, useEffect, useState } from "react";
import {
  AdminAuthError,
  CandidateSummary,
  SourceRun,
  addManualTag,
  confirmTag,
  hasAdminKey,
  rejectTag,
  setAdminKey,
  useCandidates,
  useIssueTaxonomy,
  usePendingTags,
  useSourceRuns,
} from "../api/client";
import { ServiceStatusSection } from "../components/ServiceStatusSection";
import { SourceHealthSection, summarizeSourceHealth } from "../components/SourceHealthSection";

// ── Admin key gate ────────────────────────────────────────────────────────────
// Prompts for the X-Admin-Key once per session (in memory only). Since
// status-endpoint-auth (roadmap #16) gated GET /api/status/sources — it
// exposes our own per-source error_message, not public data — the prompt now
// fires on /admin page load (the sources fetch below), not only on the first
// write attempt; either path re-prompts with a visible error if the backend
// 401s.

interface AdminGateContextValue {
  runAdminAction: (action: () => Promise<void>) => Promise<void>;
}

const AdminGateContext = createContext<AdminGateContextValue | null>(null);

function useAdminAction() {
  const ctx = useContext(AdminGateContext);
  if (!ctx) throw new Error("useAdminAction must be used within AdminPage");
  return ctx.runAdminAction;
}

function useAdminGate() {
  const [promptOpen, setPromptOpen] = useState(false);
  const [keyInput, setKeyInput] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pendingAction, setPendingAction] = useState<(() => Promise<void>) | null>(null);

  const attempt = async (action: () => Promise<void>) => {
    try {
      await action();
      setError(null);
    } catch (e) {
      if (e instanceof AdminAuthError) {
        setError("Admin key was rejected — please re-enter it.");
        setPendingAction(() => action);
        setPromptOpen(true);
      } else {
        throw e;
      }
    }
  };

  const runAdminAction = async (action: () => Promise<void>) => {
    if (!hasAdminKey()) {
      setError(null);
      setPendingAction(() => action);
      setPromptOpen(true);
      return;
    }
    await attempt(action);
  };

  const submitKey = async () => {
    if (!keyInput) return;
    setAdminKey(keyInput);
    setKeyInput("");
    setPromptOpen(false);
    const action = pendingAction;
    setPendingAction(null);
    if (action) await attempt(action);
  };

  const cancelPrompt = () => {
    setPromptOpen(false);
    setPendingAction(null);
    setKeyInput("");
  };

  return { promptOpen, keyInput, setKeyInput, submitKey, cancelPrompt, error, runAdminAction };
}

function AdminKeyPrompt({
  keyInput,
  setKeyInput,
  submitKey,
  cancelPrompt,
}: {
  keyInput: string;
  setKeyInput: (v: string) => void;
  submitKey: () => void;
  cancelPrompt: () => void;
}) {
  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 px-4">
      <div className="bg-gray-900 border border-gray-700 rounded-xl p-5 w-full max-w-sm space-y-3">
        <p className="text-sm font-medium text-white">Admin key required</p>
        <p className="text-xs text-gray-500">
          This action needs the admin key. It's kept in memory for this session only.
        </p>
        <input
          type="password"
          autoFocus
          value={keyInput}
          onChange={e => setKeyInput(e.target.value)}
          onKeyDown={e => { if (e.key === "Enter") submitKey(); }}
          placeholder="Admin key"
          className="w-full text-sm bg-gray-950 border border-gray-700 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-gray-500"
        />
        <div className="flex justify-end gap-2">
          <button
            onClick={cancelPrompt}
            className="text-xs px-3 py-1.5 text-gray-400 hover:text-gray-200 transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={submitKey}
            disabled={!keyInput}
            className="text-xs px-3 py-1.5 bg-purple-900/50 hover:bg-purple-900 border border-purple-800 text-purple-300 rounded-lg transition-colors disabled:opacity-50"
          >
            Continue
          </button>
        </div>
      </div>
    </div>
  );
}

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
  const runAdminAction = useAdminAction();

  const handle = async (tagId: number, candidateId: number, action: "confirm" | "reject") => {
    setProcessing(prev => new Set([...prev, tagId]));
    try {
      await runAdminAction(async () => {
        if (action === "confirm") await confirmTag(candidateId, tagId);
        else await rejectTag(candidateId, tagId);
        refresh();
      });
    } finally {
      setProcessing(prev => { const s = new Set(prev); s.delete(tagId); return s; });
    }
  };

  if (loading) return <div className="h-32 bg-gray-900 rounded-xl animate-pulse" />;

  if (tags.length === 0) {
    return (
      <div className="text-center py-12 text-gray-600">
        <p className="text-2xl mb-2">✓</p>
        <p>No pending AI suggestions.</p>
        <p className="text-xs mt-2">New suggestions come from the weekly scheduled tagging job — nothing to trigger manually.</p>
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
  const runAdminAction = useAdminAction();

  const { candidates, loading } = useCandidates(officeFilter || undefined, stateFilter || undefined);

  const handleAddTag = async () => {
    if (!selectedCandidate || !newIssue) return;
    setAddingTag(true);
    try {
      await runAdminAction(async () => {
        await addManualTag(selectedCandidate.id, newIssue);
        setNewIssue("");
      });
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

// ── Health summary banner ─────────────────────────────────────────────────────
// Purely presentational — takes the already-fetched `sources` prop rather
// than making its own call, so it doesn't duplicate the admin-key gate above
// it. Reuses SourceHealthSection's own classify()-derived aggregate so the
// count here can't drift from the cards below it (AC-3).

function HealthSummaryBanner({ sources, loading }: { sources: SourceRun[]; loading: boolean }) {
  if (loading || sources.length === 0) return null;

  const { total, flagged, allHealthy } = summarizeSourceHealth(sources);

  return (
    <div
      className={`text-sm rounded-lg px-4 py-3 border ${
        allHealthy
          ? "bg-green-950/20 border-gray-800 text-gray-300"
          : "bg-red-950/20 border-red-800/60 text-red-400"
      }`}
    >
      {allHealthy
        ? `All ${total} data sources current.`
        : `${flagged} of ${total} data source${total > 1 ? "s" : ""} need attention — see below.`}
    </div>
  );
}

// ── Main Admin Page ───────────────────────────────────────────────────────────

type AdminTab = "candidates" | "pending";

export function AdminPage() {
  const [tab, setTab] = useState<AdminTab>("candidates");
  const gate = useAdminGate();
  const { sources, loading: sourcesLoading, refresh: refreshSources } = useSourceRuns();

  // status-endpoint-auth: the sources fetch is gated, so prompt for the key
  // on page load (via the same gate write actions use) rather than waiting
  // for a write. Re-runs on the same 5-minute cadence the old self-polling
  // hook used; if the key is missing or wrong, the gate re-prompts each
  // cycle rather than failing silently.
  useEffect(() => {
    gate.runAdminAction(refreshSources);
    const id = setInterval(() => { gate.runAdminAction(refreshSources); }, 5 * 60 * 1000);
    return () => clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <AdminGateContext.Provider value={{ runAdminAction: gate.runAdminAction }}>
      <div className="min-h-screen bg-gray-950">
        <div className="max-w-4xl mx-auto px-4 py-8 space-y-6">
          <div className="space-y-1">
            <h2 className="text-xl font-bold text-white tracking-tight">Election Intelligence — Status &amp; Admin</h2>
            <p className="text-xs text-gray-600">
              Internal use only. The candidate browser and tag review need the admin key to make changes; the data-sources health view below needs it just to read.
            </p>
          </div>

          <HealthSummaryBanner sources={sources} loading={sourcesLoading} />

          {gate.error && (
            <div className="text-xs bg-red-950/50 border border-red-800 text-red-400 rounded-lg px-3 py-2">
              {gate.error}
            </div>
          )}

          {/* Our own data pipeline health — prominent (AC-4) */}
          <SourceHealthSection sources={sources} loading={sourcesLoading} />

          {/* Third-party dependency status — collapsed by default (AC-4/AC-5) */}
          <details className="group">
            <summary className="cursor-pointer select-none flex items-center gap-2 text-sm font-semibold text-gray-400 hover:text-gray-300 transition-colors">
              <span className="text-gray-600 transition-transform group-open:rotate-90">▸</span>
              Third-Party Service Status
            </summary>
            <div className="mt-4">
              <ServiceStatusSection />
            </div>
          </details>

          {/* Tabs — candidate browsing leads, tag review is secondary (AC-7) */}
          <div className="flex gap-1 border-b border-gray-800 pb-0">
            {([["candidates", "Candidate Browser"], ["pending", "Pending AI Tags"]] as [AdminTab, string][]).map(([id, label]) => (
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

          {tab === "candidates" && <CandidateBrowserTab />}
          {tab === "pending" && <PendingTagsTab />}
        </div>
      </div>

      {gate.promptOpen && (
        <AdminKeyPrompt
          keyInput={gate.keyInput}
          setKeyInput={gate.setKeyInput}
          submitKey={gate.submitKey}
          cancelPrompt={gate.cancelPrompt}
        />
      )}
    </AdminGateContext.Provider>
  );
}
