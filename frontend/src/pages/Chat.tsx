/**
 * Commander Q&A page.
 *
 * Round-3:
 *   * Threads are persisted in Postgres (chat_messages table), scoped
 *     to the active mission. Refresh, switch tabs, or reopen — same
 *     conversation comes back.
 *   * Active mission picked via localStorage 'astra:lastMissionId' (set
 *     by the Mission page when a file is ingested) or via the small
 *     selector in the header.
 *   * 'note: <text>' or the explicit "Save note" button persists a free-
 *     form note attached to the current mission. The next briefing pulls
 *     those notes into the OPERATOR NOTES section.
 *   * 'details of mission #N' / 'brief me on mission 14' returns a full
 *     formatted briefing.
 */
import { useEffect, useRef, useState } from "react";
import { Send, MessageCircle, Loader2, Sparkles, Cpu, RotateCcw, StickyNote, ChevronDown } from "lucide-react";
import { PageHeader } from "../components/PageHeader";
import { StatusPill } from "../components/StatusPill";
import { EmptyState } from "../components/EmptyState";
import { toast } from "../components/Toast";
import { api, type Mission, type ChatMessage as DbChatMessage } from "../lib/api";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "";

type Msg = {
  role: "user" | "astra";
  text: string;
  source?: "rule" | "llm" | "error" | "note" | "briefing";
  citations?: Record<string, unknown>[];
  ts: number;
};

const SUGGESTED_GLOBAL = [
  "How many ships have we detected?",
  "What was the last engagement?",
  "Show me airframes ID'd today",
  "Verify the audit chain",
  "What's the federated state?",
];

const SUGGESTED_MISSION = (id: number) => [
  `Details of mission #${id}`,
  `Brief me on mission ${id}`,
  `note: visual confirmed, awaiting clearance`,
];

function dbToMsg(m: DbChatMessage): Msg {
  return {
    role: m.role,
    text: m.text,
    source: (m.source ?? undefined) as Msg["source"],
    citations: m.citations,
    ts: m.created_at ? new Date(m.created_at).getTime() : Date.now(),
  };
}

export default function Chat() {
  const [activeMissionId, setActiveMissionId] = useState<number | null>(() => {
    const v = localStorage.getItem("astra:lastMissionId");
    return v ? Number(v) : null;
  });
  const [missionList, setMissionList] = useState<Mission[]>([]);
  const [showPicker, setShowPicker] = useState(false);

  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [llmAvail, setLlmAvail] = useState<boolean | null>(null);
  const [loadingThread, setLoadingThread] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);

  // LLM status check
  useEffect(() => {
    fetch(`${API_BASE}/api/v1/chat/status`)
      .then((r) => r.json())
      .then((d) => setLlmAvail(!!d.llm_available))
      .catch(() => setLlmAvail(false));
  }, []);

  // Load recent missions for the picker
  useEffect(() => {
    api.listMissions(50).then(setMissionList).catch(() => setMissionList([]));
  }, []);

  // Load persisted thread whenever the active mission changes
  useEffect(() => {
    let cancelled = false;
    setLoadingThread(true);
    api.chatThread(activeMissionId)
      .then((rows) => {
        if (cancelled) return;
        setMsgs(rows.map(dbToMsg));
      })
      .catch(() => { if (!cancelled) setMsgs([]); })
      .finally(() => { if (!cancelled) setLoadingThread(false); });
    return () => { cancelled = true; };
  }, [activeMissionId]);

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth" }); }, [msgs]);

  const activeMission = missionList.find((m) => m.id === activeMissionId) ?? null;

  async function ask(q: string) {
    if (!q.trim() || busy) return;
    setBusy(true);
    setDraft("");
    setMsgs((m) => [...m, { role: "user", text: q, ts: Date.now() }]);
    try {
      const d = await api.chatAsk({ question: q, mission_id: activeMissionId });
      setMsgs((m) => [...m, {
        role: "astra",
        text: d.answer,
        source: d.source as Msg["source"],
        citations: d.citations,
        ts: Date.now(),
      }]);
    } catch (e) {
      toast.crit("Q&A failed", (e as Error).message);
      setMsgs((m) => [...m, { role: "astra", text: `error: ${(e as Error).message}`, source: "error", ts: Date.now() }]);
    } finally {
      setBusy(false);
    }
  }

  async function saveQuickNote() {
    if (activeMissionId == null) {
      toast.crit("No active mission", "Pick a mission first using the selector.");
      return;
    }
    const text = draft.trim();
    if (!text) return;
    setBusy(true);
    try {
      const saved = await api.chatNote({ text, mission_id: activeMissionId });
      setMsgs((m) => [
        ...m,
        { role: "user", text: `note: ${saved.text}`, source: "note", ts: Date.now() },
        { role: "astra", text: `Note saved to mission #${saved.mission_id} (#${saved.id}). It will appear in the next briefing.`, source: "note", ts: Date.now() },
      ]);
      setDraft("");
      toast.success("Note saved", `Mission #${saved.mission_id}`);
    } catch (e) {
      toast.crit("Note failed", (e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  function newThread() {
    // We don't actually delete from DB here — that would erase audit. We
    // simply navigate to a fresh global thread (mission_id = null) and let
    // the user pick a different mission.
    setActiveMissionId(null);
    localStorage.removeItem("astra:lastMissionId");
  }

  function pickMission(id: number | null) {
    setActiveMissionId(id);
    if (id != null) localStorage.setItem("astra:lastMissionId", String(id));
    else localStorage.removeItem("astra:lastMissionId");
    setShowPicker(false);
  }

  const suggested = activeMissionId != null ? SUGGESTED_MISSION(activeMissionId) : SUGGESTED_GLOBAL;

  return (
    <div className="h-full flex flex-col">
      <PageHeader
        icon={MessageCircle}
        title="Commander Q&A"
        badge={
          llmAvail == null ? (
            <StatusPill variant="neutral" size="sm">checking...</StatusPill>
          ) : llmAvail ? (
            <StatusPill variant="ok" size="sm"><Sparkles size={9} className="mr-1" /> Phi-3.5 LLM</StatusPill>
          ) : (
            <StatusPill variant="info" size="sm"><Cpu size={9} className="mr-1" /> rule-based</StatusPill>
          )
        }
        subtitle={
          activeMission
            ? `Scoped to mission #${activeMission.id} ${activeMission.name} — every turn is persisted in the DB and surfaces in the briefing.`
            : "No active mission — answers run against the full database. Pick a mission to bind the thread."
        }
        actions={
          <>
            {/* Mission selector */}
            <div className="relative">
              <button
                onClick={() => setShowPicker((v) => !v)}
                className="flex items-center gap-2 glass border border-border px-3 py-1.5 rounded text-xs hover:bg-panel2 transition-fast"
                title="Bind this chat thread to a specific mission"
              >
                {activeMissionId != null
                  ? <span className="font-mono text-accent">MSN #{activeMissionId}</span>
                  : <span className="text-muted">no mission</span>}
                <ChevronDown size={11} className="text-muted" />
              </button>
              {showPicker && (
                <div className="absolute right-0 top-full mt-1 z-30 glass-strong border border-border rounded shadow-2xl w-72 max-h-96 overflow-auto">
                  <button
                    onClick={() => pickMission(null)}
                    className={`w-full text-left px-3 py-2 text-xs hover:bg-panel2 border-b border-border ${activeMissionId == null ? "text-accent" : "text-muted"}`}
                  >
                    — global (no mission scope) —
                  </button>
                  {missionList.length === 0 ? (
                    <div className="px-3 py-3 text-xs text-muted">No missions yet. Ingest one first.</div>
                  ) : missionList.map((m) => (
                    <button
                      key={m.id}
                      onClick={() => pickMission(m.id)}
                      className={`w-full text-left px-3 py-2 text-xs hover:bg-panel2 font-mono ${m.id === activeMissionId ? "text-accent bg-panel2" : ""}`}
                    >
                      <div>#{m.id} {m.name}</div>
                      <div className="text-[10px] text-muted">{new Date(m.created_at).toLocaleString()}</div>
                    </button>
                  ))}
                </div>
              )}
            </div>
            {msgs.length > 0 && (
              <button
                onClick={newThread}
                className="flex items-center gap-2 glass border border-border px-3 py-1.5 rounded text-xs hover:bg-panel2 transition-fast text-muted hover:text-text"
                title="Switch to global thread. Mission threads stay in the DB."
              >
                <RotateCcw size={12} /> New thread
              </button>
            )}
          </>
        }
      />

      <div className="flex-1 grid grid-rows-[1fr_auto] overflow-hidden">
        {/* Conversation */}
        <div className="overflow-auto px-6 pt-6 pb-2">
          <div className="max-w-[860px] mx-auto space-y-3">
            {loadingThread ? (
              <div className="flex items-center gap-2 text-xs text-muted">
                <Loader2 size={12} className="animate-spin" /> Loading thread for mission #{activeMissionId}...
              </div>
            ) : msgs.length === 0 ? (
              <EmptyState
                icon={MessageCircle}
                title={activeMission ? `Mission #${activeMission.id} thread is empty` : "Ask anything about the mission state"}
                body={activeMission
                  ? `Ask questions, save notes, request a briefing — all persisted against this mission.`
                  : "Counts, engagements, airframes, audit chain, federated state — all queryable. Bind a mission via the selector to scope the thread."}
              />
            ) : msgs.map((m, i) => (
              <div key={i} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
                <div className={`max-w-[720px] rounded-lg px-4 py-2.5 ${m.role === "user" ? "bg-accent text-bg" : "glass border border-border"}`}>
                  <div className="text-2xs uppercase-wide font-mono tracking-wider mb-1 flex items-center gap-1.5 opacity-80">
                    {m.role === "user" ? "OPERATOR" : "ASTRA"}
                    {m.source === "llm" && <Sparkles size={9} />}
                    {m.source === "rule" && <Cpu size={9} />}
                    {m.source === "briefing" && <span className="text-2xs">BRIEFING</span>}
                    {m.source === "note" && <StickyNote size={9} />}
                    {m.source === "error" && <span className="text-threat-crit">ERR</span>}
                  </div>
                  <div className={`text-sm whitespace-pre-wrap ${m.role === "user" ? "text-bg" : "text-text"} ${m.source === "briefing" ? "font-mono text-xs leading-relaxed" : ""}`}>
                    {m.text}
                  </div>
                  {m.citations && m.citations.length > 0 && (
                    <div className="mt-2 pt-2 border-t border-border/60 text-2xs text-muted2 font-mono">
                      {m.citations.length} citation{m.citations.length !== 1 ? "s" : ""} ·
                      {" " + m.citations.slice(0, 4).map((c: any) => c.id ? `#${c.id}` : (c.name || c.class_name || "?")).join(" ")}
                      {m.citations.length > 4 && " …"}
                    </div>
                  )}
                </div>
              </div>
            ))}
            <div ref={endRef} />
          </div>
        </div>

        {/* Input */}
        <div className="border-t border-border bg-panel/40 px-6 py-3">
          <div className="max-w-[860px] mx-auto">
            {msgs.length === 0 && !loadingThread && (
              <div className="flex flex-wrap gap-2 mb-3">
                {suggested.map((q) => (
                  <button
                    key={q}
                    onClick={() => ask(q)}
                    className="text-xs glass border border-border rounded-full px-3 py-1 hover:border-accent transition-fast text-muted hover:text-text"
                  >
                    {q}
                  </button>
                ))}
              </div>
            )}
            <form
              onSubmit={(e) => { e.preventDefault(); ask(draft); }}
              className="flex items-center gap-2 glass-strong rounded-md px-3 py-2"
            >
              <input
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                disabled={busy}
                placeholder={activeMissionId != null
                  ? `ask about mission #${activeMissionId}, or type 'note: <text>' to save…`
                  : "ask the commander console..."}
                className="flex-1 bg-transparent text-sm focus:outline-none placeholder:text-muted2"
              />
              {activeMissionId != null && draft.trim() && (
                <button
                  type="button"
                  onClick={saveQuickNote}
                  disabled={busy}
                  className="flex items-center gap-1 glass border border-border px-2.5 py-1.5 rounded text-xs hover:bg-panel2 disabled:opacity-50 transition-fast"
                  title="Save text as a note attached to the active mission"
                >
                  <StickyNote size={11} /> note
                </button>
              )}
              <button
                type="submit"
                disabled={busy || !draft.trim()}
                className="flex items-center gap-1 bg-accent text-bg px-3 py-1.5 rounded text-xs font-medium hover:brightness-110 disabled:opacity-50 transition-fast"
              >
                {busy ? <Loader2 size={12} className="animate-spin" /> : <Send size={12} />}
                send
              </button>
            </form>
          </div>
        </div>
      </div>
    </div>
  );
}
