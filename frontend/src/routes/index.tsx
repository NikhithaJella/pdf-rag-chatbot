import { createFileRoute } from "@tanstack/react-router";
import { useRef, useState, useEffect, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { Toaster } from "@/components/ui/sonner";
import { toast } from "sonner";
import {
  FileText,
  Send,
  Loader2,
  Sparkles,
  Upload,
  ExternalLink,
  AlertCircle,
  CheckCircle2,
  Globe,
  X,
  BookOpen,
} from "lucide-react";
import { cn } from "@/lib/utils";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "DocuMind AI" },
      { name: "description", content: "PDF RAG Assistant with Hybrid Retrieval" },
    ],
  }),
  component: Index,
});

type WebSource = { title: string; url: string };

type Message = {
  role: "user" | "assistant";
  content: string;
  isError?: boolean;
  citations?: string[];
  webSearchTriggered?: boolean;
  webSources?: WebSource[];
  sourceType?: "pdf" | "web" | "pdf_not_found";
};

type DocStatus = { filename: string; chunksLoaded: number } | null;

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function ThinkingIndicator() {
  return (
    <div className="flex justify-start">
      <div className="flex items-center gap-1.5 px-4 py-3.5 rounded-2xl rounded-tl-sm bg-white border border-zinc-100 shadow-sm">
        <span className="h-2 w-2 rounded-full bg-zinc-300 animate-bounce [animation-delay:-0.3s]" />
        <span className="h-2 w-2 rounded-full bg-zinc-300 animate-bounce [animation-delay:-0.15s]" />
        <span className="h-2 w-2 rounded-full bg-zinc-300 animate-bounce" />
      </div>
    </div>
  );
}

function MessageBubble({ message: m }: { message: Message }) {
  if (m.role === "user") {
    return (
      <div className="flex justify-end">
        <div className="max-w-[75%] rounded-2xl rounded-tr-sm bg-indigo-600 px-4 py-3 shadow-sm shadow-indigo-200">
          <p className="text-sm leading-relaxed whitespace-pre-wrap text-white">{m.content}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex justify-start">
      <div className="max-w-[85%] space-y-2.5">
        {/* Main answer card */}
        {m.isError ? (
          <div className="flex items-start gap-2.5 px-4 py-3 rounded-2xl rounded-tl-sm bg-red-50 border border-red-200">
            <AlertCircle className="h-4 w-4 text-red-500 shrink-0 mt-0.5" />
            <p className="text-sm text-red-700 leading-relaxed">{m.content}</p>
          </div>
        ) : (
          <div className="rounded-2xl rounded-tl-sm bg-white border border-zinc-100 shadow-sm px-4 py-3">
            <p className="text-sm text-zinc-800 leading-relaxed whitespace-pre-wrap">{m.content}</p>
          </div>
        )}

        {/* PDF citation badges */}
        {m.sourceType === "pdf" && m.citations && m.citations.length > 0 && (
          <div className="flex flex-wrap gap-1.5 pl-1">
            {m.citations.map((c, j) => (
              <button
                key={j}
                title="Click to copy"
                onClick={() => {
                  navigator.clipboard?.writeText(c);
                  toast.success("Citation copied to clipboard");
                }}
                className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-indigo-50 border border-indigo-100 text-[11px] text-indigo-600 font-medium hover:bg-indigo-100 hover:border-indigo-200 transition-colors cursor-pointer"
              >
                <FileText className="h-3 w-3 shrink-0" />
                {c}
              </button>
            ))}
          </div>
        )}

        {/* Web search indicator + source links */}
        {m.webSearchTriggered && (
          <div className="space-y-2 pl-1">
            <div className="flex items-center gap-1.5 text-[11px]">
              <Globe className="h-3.5 w-3.5 text-sky-500" />
              <span className="font-semibold text-sky-600">Web Search</span>
              <span className="text-zinc-400">· sourced from live web results</span>
            </div>
            {m.webSources && m.webSources.length > 0 && (
              <div className="space-y-1.5">
                {m.webSources.map((s, k) => (
                  <a
                    key={k}
                    href={s.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-start gap-1.5 group"
                  >
                    <ExternalLink className="h-3 w-3 mt-0.5 text-sky-400 shrink-0" />
                    <span className="text-[11px] text-sky-600 group-hover:text-sky-500 group-hover:underline break-all leading-snug">
                      {s.title || s.url}
                    </span>
                  </a>
                ))}
              </div>
            )}
          </div>
        )}

        {/* pdf_not_found indicator */}
        {m.sourceType === "pdf_not_found" && !m.isError && (
          <div className="flex items-center gap-1.5 pl-1">
            <div className="h-2 w-2 rounded-full bg-amber-400 shrink-0" />
            <p className="text-[11px] text-amber-600 font-medium">
              This question could not be answered from the indexed document
            </p>
          </div>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

function Index() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [question, setQuestion] = useState("");
  const [sending, setSending] = useState(false);

  const [docStatus, setDocStatus] = useState<DocStatus>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [isIndexing, setIsIndexing] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const [sidebarError, setSidebarError] = useState<string | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const isBusy = isUploading || isIndexing;

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, sending]);

  // Upload → auto-ingest pipeline triggered by file selection or drop
  const handleFile = useCallback(async (file: File) => {
    if (!file.name.toLowerCase().endsWith(".pdf")) {
      setSidebarError("Only PDF files are accepted. Please choose a valid .pdf file.");
      return;
    }

    setSidebarError(null);
    setDocStatus(null);
    setIsUploading(true);

    let uploadedPath = "";
    let uploadedFilename = "";

    try {
      const formData = new FormData();
      formData.append("file", file);
      const res = await fetch(`${API_BASE}/api/upload`, { method: "POST", body: formData });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail ?? `Upload failed (HTTP ${res.status})`);
      uploadedPath = data.path;
      uploadedFilename = data.filename;
    } catch (e) {
      setSidebarError(
        e instanceof Error ? e.message : "Upload failed — check that the backend server is running."
      );
      setIsUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
      return;
    }

    setIsUploading(false);
    setIsIndexing(true);

    try {
      const res = await fetch(`${API_BASE}/api/ingest`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ file_paths: [uploadedPath] }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail ?? `Indexing failed (HTTP ${res.status})`);
      const chunks = data.chunks_loaded ?? data.total_chunks ?? data.total ?? data.count ?? 0;
      setDocStatus({ filename: uploadedFilename, chunksLoaded: chunks });
    } catch (e) {
      setSidebarError(
        e instanceof Error
          ? e.message
          : "Indexing failed — the file may be corrupt or take too long to process."
      );
    } finally {
      setIsIndexing(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  }, []);

  const handleSend = async (e?: React.FormEvent<HTMLFormElement>) => {
    e?.preventDefault();
    const q = question.trim();
    if (!q || sending) return;

    setMessages((m) => [...m, { role: "user", content: q }]);
    setQuestion("");
    if (textareaRef.current) textareaRef.current.style.height = "auto";
    setSending(true);

    try {
      const res = await fetch(`${API_BASE}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: q }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail ?? `Server error (HTTP ${res.status})`);

      setMessages((m) => [
        ...m,
        {
          role: "assistant",
          content: data.answer ?? "(no answer)",
          citations: Array.isArray(data.citations) ? data.citations : [],
          webSearchTriggered: data.web_search_triggered === true,
          webSources: Array.isArray(data.web_sources) ? data.web_sources : [],
          sourceType: data.source_type ?? "pdf",
        },
      ]);
    } catch (e) {
      const msg =
        e instanceof Error ? e.message : "Request failed — check your network and backend.";
      setMessages((m) => [...m, { role: "assistant", content: msg, isError: true }]);
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="flex h-screen overflow-hidden bg-zinc-950">
      <Toaster />

      {/* ── Sidebar ─────────────────────────────────────────────────────── */}
      <aside className="w-72 flex-shrink-0 flex flex-col border-r border-zinc-800/60 bg-zinc-950">

        {/* Brand header */}
        <div className="px-5 py-5 border-b border-zinc-800/60">
          <div className="flex items-center gap-3">
            <div className="h-9 w-9 rounded-xl bg-indigo-600 grid place-items-center shadow-lg shadow-indigo-900/40 shrink-0">
              <BookOpen className="h-5 w-5 text-white" />
            </div>
            <div className="min-w-0">
              <h1 className="text-sm font-bold text-white tracking-tight">DocuMind AI</h1>
              <p className="text-[10px] text-zinc-500 leading-tight mt-0.5">
                PDF RAG Assistant with Hybrid Retrieval
              </p>
            </div>
          </div>
        </div>

        {/* Document controls */}
        <div className="flex-1 overflow-y-auto px-4 py-5 space-y-4">

          {/* Drag-and-drop / file picker zone */}
          <div
            role="button"
            tabIndex={0}
            aria-label="Upload PDF"
            onDragOver={(e) => { e.preventDefault(); if (!isBusy) setDragOver(true); }}
            onDragLeave={() => setDragOver(false)}
            onDrop={(e) => {
              e.preventDefault();
              setDragOver(false);
              if (!isBusy) {
                const file = e.dataTransfer.files[0];
                if (file) handleFile(file);
              }
            }}
            onClick={() => { if (!isBusy) fileInputRef.current?.click(); }}
            onKeyDown={(e) => {
              if ((e.key === "Enter" || e.key === " ") && !isBusy) {
                e.preventDefault();
                fileInputRef.current?.click();
              }
            }}
            className={cn(
              "relative flex flex-col items-center justify-center gap-2 p-6 rounded-xl border-2 border-dashed select-none transition-all duration-200",
              isBusy
                ? "border-zinc-700 opacity-70 cursor-not-allowed"
                : dragOver
                ? "border-indigo-500 bg-indigo-500/10 cursor-copy"
                : "border-zinc-700 hover:border-zinc-500 hover:bg-zinc-800/40 cursor-pointer"
            )}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf"
              className="hidden"
              onChange={(e) => { const f = e.target.files?.[0]; if (f) handleFile(f); }}
            />

            {isUploading ? (
              <>
                <Loader2 className="h-7 w-7 text-indigo-400 animate-spin" />
                <p className="text-xs font-semibold text-zinc-200">Uploading...</p>
                <p className="text-[10px] text-zinc-500 text-center">Transferring file to server</p>
              </>
            ) : isIndexing ? (
              <>
                <Loader2 className="h-7 w-7 text-indigo-400 animate-spin" />
                <p className="text-xs font-semibold text-zinc-200">Building index...</p>
                <p className="text-[10px] text-zinc-500 text-center">
                  Parsing and embedding document chunks
                </p>
              </>
            ) : (
              <>
                <div className={cn(
                  "h-11 w-11 rounded-xl grid place-items-center transition-all",
                  dragOver ? "bg-indigo-500/20" : "bg-zinc-800"
                )}>
                  <Upload className={cn(
                    "h-5 w-5 transition-colors",
                    dragOver ? "text-indigo-400" : "text-zinc-500"
                  )} />
                </div>
                <p className="text-xs font-semibold text-zinc-300">Drop PDF here</p>
                <p className="text-[10px] text-zinc-600">or click to browse files</p>
              </>
            )}
          </div>

          {/* Error banner */}
          {sidebarError && (
            <div className="flex items-start gap-2.5 p-3 rounded-lg bg-red-500/10 border border-red-500/20">
              <AlertCircle className="h-4 w-4 text-red-400 shrink-0 mt-0.5" />
              <p className="flex-1 text-[11px] text-red-300 leading-snug">{sidebarError}</p>
              <button
                onClick={() => setSidebarError(null)}
                className="shrink-0 text-red-500 hover:text-red-300 transition-colors"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            </div>
          )}

          {/* Success status card */}
          {docStatus && !isBusy && (
            <div className="flex items-start gap-2.5 p-3 rounded-lg bg-emerald-500/10 border border-emerald-500/20">
              <CheckCircle2 className="h-4 w-4 text-emerald-400 shrink-0 mt-0.5" />
              <div className="min-w-0">
                <p className="text-[11px] font-semibold text-emerald-300 truncate">
                  {docStatus.filename}
                </p>
                <p className="text-[10px] text-zinc-500 mt-0.5">
                  {docStatus.chunksLoaded} chunks indexed and ready
                </p>
              </div>
            </div>
          )}

          {/* Active document label */}
          <div className="border-t border-zinc-800/60 pt-4">
            <p className="text-[9px] uppercase tracking-[0.12em] text-zinc-600 font-semibold mb-2">
              Active Document
            </p>
            {docStatus ? (
              <div className="flex items-center gap-2">
                <div className="h-6 w-6 rounded-md bg-indigo-500/10 grid place-items-center shrink-0">
                  <FileText className="h-3.5 w-3.5 text-indigo-400" />
                </div>
                <span className="text-[11px] text-zinc-300 truncate">{docStatus.filename}</span>
              </div>
            ) : (
              <p className="text-[11px] text-zinc-700 italic">No document loaded</p>
            )}
          </div>
        </div>

        {/* Sidebar footer */}
        <div className="px-5 py-3 border-t border-zinc-800/60">
          <p className="text-[10px] text-zinc-700">
            Backend: <span className="font-mono text-zinc-600">{API_BASE}</span>
          </p>
        </div>
      </aside>

      {/* ── Main chat panel ──────────────────────────────────────────────── */}
      <main className="flex-1 flex flex-col min-w-0 bg-zinc-50">

        {/* Chat header */}
        <header className="flex items-center justify-between px-6 py-4 border-b border-zinc-200 bg-white shrink-0">
          <div>
            <h2 className="text-sm font-semibold text-zinc-900">Chat</h2>
            <p className="text-xs text-zinc-400 mt-0.5">
              {docStatus
                ? `Querying · ${docStatus.filename}`
                : "Upload and index a PDF to get started"}
            </p>
          </div>
          {docStatus && (
            <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-emerald-50 border border-emerald-200 shrink-0">
              <div className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
              <span className="text-[10px] font-medium text-emerald-700">
                {docStatus.chunksLoaded} chunks ready
              </span>
            </div>
          )}
        </header>

        {/* Messages scroll area */}
        <div ref={scrollRef} className="flex-1 overflow-y-auto">
          <div className="mx-auto max-w-3xl px-6 py-8 space-y-5">

            {/* Empty state */}
            {messages.length === 0 && (
              <div className="flex flex-col items-center justify-center py-24 text-center select-none">
                <div className="h-16 w-16 rounded-2xl bg-indigo-600 grid place-items-center mb-5 shadow-lg shadow-indigo-200">
                  <Sparkles className="h-8 w-8 text-white" />
                </div>
                <h3 className="text-base font-semibold text-zinc-700 mb-2">
                  Ask your document anything
                </h3>
                <p className="text-sm text-zinc-400 max-w-xs leading-relaxed">
                  Drop a PDF in the sidebar to index it, then ask any question about its contents.
                </p>
              </div>
            )}

            {messages.map((m, i) => (
              <MessageBubble key={i} message={m} />
            ))}

            {sending && <ThinkingIndicator />}
          </div>
        </div>

        {/* Input bar */}
        <div className="border-t border-zinc-200 bg-white px-6 py-4 shrink-0">
          <form
            onSubmit={handleSend}
            className="mx-auto max-w-3xl flex items-end gap-3"
          >
            <textarea
              ref={textareaRef}
              value={question}
              rows={1}
              disabled={sending}
              placeholder="Ask anything about your document..."
              onChange={(e) => {
                setQuestion(e.target.value);
                e.target.style.height = "auto";
                e.target.style.height = Math.min(e.target.scrollHeight, 160) + "px";
              }}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  handleSend();
                }
              }}
              className="flex-1 resize-none rounded-xl border border-zinc-200 bg-zinc-50 px-4 py-3 text-sm text-zinc-800 placeholder:text-zinc-400 focus:outline-none focus:ring-2 focus:ring-indigo-500/40 focus:border-indigo-400 transition-all disabled:opacity-50 min-h-[44px] max-h-40 leading-relaxed"
            />
            <Button
              type="submit"
              size="icon"
              disabled={sending || !question.trim()}
              className="h-11 w-11 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white shrink-0 disabled:opacity-40 transition-colors shadow-sm"
            >
              {sending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Send className="h-4 w-4" />
              )}
            </Button>
          </form>
          <p className="text-[10px] text-zinc-400 text-center mt-2.5 select-none">
            Enter to send · Shift+Enter for new line
          </p>
        </div>
      </main>
    </div>
  );
}
