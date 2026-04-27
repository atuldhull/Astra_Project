/**
 * Commander Q&A page.
 *
 * Talk-to-the-database. Two-tier:
 *   * If a Phi-3.5 GGUF is on disk + llama-cpp-python installed → LLM
 *     answer over retrieved context.
 *   * Otherwise → rule-based intent matcher in services/rag.py.
 *
 * UI is a chat thread. Suggested prompts shown when empty.
 */
import { useEffect, useRef, useState } from "react";
import { Send, MessageCircle, Loader2, Sparkles, Cpu } from "lucide-react";
import { PageHeader } from "../components/PageHeader";
import { StatusPill } from "../components/StatusPill";
import { EmptyState } from "../components/EmptyState";
import { toast } from "../components/Toast";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "";

type Msg = {
  role: "user" | "astra";
  text: string;
  source?: "rule" | "llm" | "error";
  citations?: any[];
  ts: number;
};

const SUGGESTED = [
  "How many ships have we detected?",
  "What was the last engagement?",
  "Show me airframes ID'd today",
  "Verify the audit chain",
  "What's the federated state?",
];

export default function Chat() {
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [llmAvail, setLlmAvail] = useState<boolean | null>(null);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    fetch(`${API_BASE}/api/v1/chat/status`)
      .then((r) => r.json())
      .then((d) => setLlmAvail(!!d.llm_available))
      .catch(() => setLlmAvail(false));
  }, []);

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth" }); }, [msgs]);

  async function ask(q: string) {
    if (!q.trim() || busy) return;
    setBusy(true);
    setDraft("");
    setMsgs((m) => [...m, { role: "user", text: q, ts: Date.now() }]);
    try {
      const r = await fetch(`${API_BASE}/api/v1/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: q }),
      });
      if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
      const d = await r.json();
      setMsgs((m) => [...m, {
        role: "astra",
        text: d.answer,
        source: d.source,
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
          llmAvail
            ? "Talk to the database — Phi-3.5-mini-instruct retrieves over missions/alerts/audit."
            : "Talk to the database — rule-based intent matcher (no LLM needed). Drop a Phi-3.5 GGUF at D:/astra-data/models/ to upgrade."
        }
      />

      <div className="flex-1 grid grid-rows-[1fr_auto] overflow-hidden">
        {/* Conversation */}
        <div className="overflow-auto px-6 pt-6 pb-2">
          <div className="max-w-[860px] mx-auto space-y-3">
            {msgs.length === 0 ? (
              <EmptyState
                icon={MessageCircle}
                title="Ask anything about the mission state"
                body="Counts, engagements, airframes, audit chain, federated state — all queryable in plain English."
              />
            ) : msgs.map((m, i) => (
              <div key={i} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
                <div className={`max-w-[640px] rounded-lg px-4 py-2.5 ${m.role === "user" ? "bg-accent text-bg" : "glass border border-border"}`}>
                  <div className="text-2xs uppercase-wide font-mono tracking-wider mb-1 flex items-center gap-1.5 opacity-80">
                    {m.role === "user" ? "OPERATOR" : "ASTRA"}
                    {m.source === "llm" && <Sparkles size={9} />}
                    {m.source === "rule" && <Cpu size={9} />}
                    {m.source === "error" && <span className="text-threat-crit">ERR</span>}
                  </div>
                  <div className={`text-sm whitespace-pre-wrap ${m.role === "user" ? "text-bg" : "text-text"}`}>
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
            {msgs.length === 0 && (
              <div className="flex flex-wrap gap-2 mb-3">
                {SUGGESTED.map((q) => (
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
                placeholder="ask the commander console..."
                className="flex-1 bg-transparent text-sm focus:outline-none placeholder:text-muted2"
              />
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
