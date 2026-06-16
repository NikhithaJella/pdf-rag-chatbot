import { r as reactExports, j as jsxRuntimeExports } from "../_libs/react.mjs";
import { S as Slot } from "../_libs/radix-ui__react-slot.mjs";
import { c as cva } from "../_libs/class-variance-authority.mjs";
import { c as clsx } from "../_libs/clsx.mjs";
import { t as twMerge } from "../_libs/tailwind-merge.mjs";
import { T as Toaster$1, t as toast } from "../_libs/sonner.mjs";
import { B as BookOpen, L as LoaderCircle, U as Upload, C as CircleAlert, X, a as CircleCheck, F as FileText, S as Sparkles, b as Send, G as Globe, E as ExternalLink } from "../_libs/lucide-react.mjs";
import "../_libs/radix-ui__react-compose-refs.mjs";
import "../_libs/react-dom.mjs";
import "util";
import "crypto";
import "async_hooks";
import "stream";
function cn(...inputs) {
  return twMerge(clsx(inputs));
}
const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md text-sm font-medium cursor-pointer transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-50 disabled:cursor-not-allowed [&_svg]:pointer-events-none [&_svg]:size-4 [&_svg]:shrink-0",
  {
    variants: {
      variant: {
        default: "bg-primary text-primary-foreground shadow hover:bg-primary/90",
        destructive: "bg-destructive text-destructive-foreground shadow-sm hover:bg-destructive/90",
        outline: "border border-input bg-background shadow-sm hover:bg-accent hover:text-accent-foreground",
        secondary: "bg-secondary text-secondary-foreground shadow-sm hover:bg-secondary/80",
        ghost: "hover:bg-accent hover:text-accent-foreground",
        link: "text-primary underline-offset-4 hover:underline"
      },
      size: {
        default: "h-9 px-4 py-2",
        sm: "h-8 rounded-md px-3 text-xs",
        lg: "h-10 rounded-md px-8",
        icon: "h-9 w-9"
      }
    },
    defaultVariants: {
      variant: "default",
      size: "default"
    }
  }
);
const Button = reactExports.forwardRef(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button";
    return /* @__PURE__ */ jsxRuntimeExports.jsx(Comp, { className: cn(buttonVariants({ variant, size, className })), ref, ...props });
  }
);
Button.displayName = "Button";
const Toaster = ({ ...props }) => {
  return /* @__PURE__ */ jsxRuntimeExports.jsx(
    Toaster$1,
    {
      className: "toaster group",
      toastOptions: {
        classNames: {
          toast: "group toast group-[.toaster]:bg-background group-[.toaster]:text-foreground group-[.toaster]:border-border group-[.toaster]:shadow-lg",
          description: "group-[.toast]:text-muted-foreground",
          actionButton: "group-[.toast]:bg-primary group-[.toast]:text-primary-foreground",
          cancelButton: "group-[.toast]:bg-muted group-[.toast]:text-muted-foreground"
        }
      },
      ...props
    }
  );
};
const API_BASE = "http://localhost:8000";
function ThinkingIndicator() {
  return /* @__PURE__ */ jsxRuntimeExports.jsx("div", { className: "flex justify-start", children: /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { className: "flex items-center gap-1.5 px-4 py-3.5 rounded-2xl rounded-tl-sm bg-white border border-zinc-100 shadow-sm", children: [
    /* @__PURE__ */ jsxRuntimeExports.jsx("span", { className: "h-2 w-2 rounded-full bg-zinc-300 animate-bounce [animation-delay:-0.3s]" }),
    /* @__PURE__ */ jsxRuntimeExports.jsx("span", { className: "h-2 w-2 rounded-full bg-zinc-300 animate-bounce [animation-delay:-0.15s]" }),
    /* @__PURE__ */ jsxRuntimeExports.jsx("span", { className: "h-2 w-2 rounded-full bg-zinc-300 animate-bounce" })
  ] }) });
}
function MessageBubble({
  message: m
}) {
  if (m.role === "user") {
    return /* @__PURE__ */ jsxRuntimeExports.jsx("div", { className: "flex justify-end", children: /* @__PURE__ */ jsxRuntimeExports.jsx("div", { className: "max-w-[75%] rounded-2xl rounded-tr-sm bg-indigo-600 px-4 py-3 shadow-sm shadow-indigo-200", children: /* @__PURE__ */ jsxRuntimeExports.jsx("p", { className: "text-sm leading-relaxed whitespace-pre-wrap text-white", children: m.content }) }) });
  }
  return /* @__PURE__ */ jsxRuntimeExports.jsx("div", { className: "flex justify-start", children: /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { className: "max-w-[85%] space-y-2.5", children: [
    m.isError ? /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { className: "flex items-start gap-2.5 px-4 py-3 rounded-2xl rounded-tl-sm bg-red-50 border border-red-200", children: [
      /* @__PURE__ */ jsxRuntimeExports.jsx(CircleAlert, { className: "h-4 w-4 text-red-500 shrink-0 mt-0.5" }),
      /* @__PURE__ */ jsxRuntimeExports.jsx("p", { className: "text-sm text-red-700 leading-relaxed", children: m.content })
    ] }) : /* @__PURE__ */ jsxRuntimeExports.jsx("div", { className: "rounded-2xl rounded-tl-sm bg-white border border-zinc-100 shadow-sm px-4 py-3", children: /* @__PURE__ */ jsxRuntimeExports.jsx("p", { className: "text-sm text-zinc-800 leading-relaxed whitespace-pre-wrap", children: m.content }) }),
    m.sourceType === "pdf" && m.citations && m.citations.length > 0 && /* @__PURE__ */ jsxRuntimeExports.jsx("div", { className: "flex flex-wrap gap-1.5 pl-1", children: m.citations.map((c, j) => /* @__PURE__ */ jsxRuntimeExports.jsxs("button", { title: "Click to copy", onClick: () => {
      navigator.clipboard?.writeText(c);
      toast.success("Citation copied to clipboard");
    }, className: "flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-indigo-50 border border-indigo-100 text-[11px] text-indigo-600 font-medium hover:bg-indigo-100 hover:border-indigo-200 transition-colors cursor-pointer", children: [
      /* @__PURE__ */ jsxRuntimeExports.jsx(FileText, { className: "h-3 w-3 shrink-0" }),
      c
    ] }, j)) }),
    m.webSearchTriggered && /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { className: "space-y-2 pl-1", children: [
      /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { className: "flex items-center gap-1.5 text-[11px]", children: [
        /* @__PURE__ */ jsxRuntimeExports.jsx(Globe, { className: "h-3.5 w-3.5 text-sky-500" }),
        /* @__PURE__ */ jsxRuntimeExports.jsx("span", { className: "font-semibold text-sky-600", children: "Web Search" }),
        /* @__PURE__ */ jsxRuntimeExports.jsx("span", { className: "text-zinc-400", children: "· sourced from live web results" })
      ] }),
      m.webSources && m.webSources.length > 0 && /* @__PURE__ */ jsxRuntimeExports.jsx("div", { className: "space-y-1.5", children: m.webSources.map((s, k) => /* @__PURE__ */ jsxRuntimeExports.jsxs("a", { href: s.url, target: "_blank", rel: "noopener noreferrer", className: "flex items-start gap-1.5 group", children: [
        /* @__PURE__ */ jsxRuntimeExports.jsx(ExternalLink, { className: "h-3 w-3 mt-0.5 text-sky-400 shrink-0" }),
        /* @__PURE__ */ jsxRuntimeExports.jsx("span", { className: "text-[11px] text-sky-600 group-hover:text-sky-500 group-hover:underline break-all leading-snug", children: s.title || s.url })
      ] }, k)) })
    ] }),
    m.sourceType === "pdf_not_found" && !m.isError && /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { className: "flex items-center gap-1.5 pl-1", children: [
      /* @__PURE__ */ jsxRuntimeExports.jsx("div", { className: "h-2 w-2 rounded-full bg-amber-400 shrink-0" }),
      /* @__PURE__ */ jsxRuntimeExports.jsx("p", { className: "text-[11px] text-amber-600 font-medium", children: "This question could not be answered from the indexed document" })
    ] })
  ] }) });
}
function Index() {
  const [messages, setMessages] = reactExports.useState([]);
  const [question, setQuestion] = reactExports.useState("");
  const [sending, setSending] = reactExports.useState(false);
  const [docStatus, setDocStatus] = reactExports.useState(null);
  const [isUploading, setIsUploading] = reactExports.useState(false);
  const [isIndexing, setIsIndexing] = reactExports.useState(false);
  const [dragOver, setDragOver] = reactExports.useState(false);
  const [sidebarError, setSidebarError] = reactExports.useState(null);
  const fileInputRef = reactExports.useRef(null);
  const scrollRef = reactExports.useRef(null);
  const textareaRef = reactExports.useRef(null);
  const isBusy = isUploading || isIndexing;
  reactExports.useEffect(() => {
    scrollRef.current?.scrollTo({
      top: scrollRef.current.scrollHeight,
      behavior: "smooth"
    });
  }, [messages, sending]);
  const handleFile = reactExports.useCallback(async (file) => {
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
      const res = await fetch(`${API_BASE}/api/upload`, {
        method: "POST",
        body: formData
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail ?? `Upload failed (HTTP ${res.status})`);
      uploadedPath = data.path;
      uploadedFilename = data.filename;
    } catch (e) {
      setSidebarError(e instanceof Error ? e.message : "Upload failed — check that the backend server is running.");
      setIsUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
      return;
    }
    setIsUploading(false);
    setIsIndexing(true);
    try {
      const res = await fetch(`${API_BASE}/api/ingest`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          file_paths: [uploadedPath]
        })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail ?? `Indexing failed (HTTP ${res.status})`);
      const chunks = data.chunks_loaded ?? data.total_chunks ?? data.total ?? data.count ?? 0;
      setDocStatus({
        filename: uploadedFilename,
        chunksLoaded: chunks
      });
    } catch (e) {
      setSidebarError(e instanceof Error ? e.message : "Indexing failed — the file may be corrupt or take too long to process.");
    } finally {
      setIsIndexing(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  }, []);
  const handleSend = async (e) => {
    e?.preventDefault();
    const q = question.trim();
    if (!q || sending) return;
    setMessages((m) => [...m, {
      role: "user",
      content: q
    }]);
    setQuestion("");
    if (textareaRef.current) textareaRef.current.style.height = "auto";
    setSending(true);
    try {
      const res = await fetch(`${API_BASE}/api/chat`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          question: q
        })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail ?? `Server error (HTTP ${res.status})`);
      setMessages((m) => [...m, {
        role: "assistant",
        content: data.answer ?? "(no answer)",
        citations: Array.isArray(data.citations) ? data.citations : [],
        webSearchTriggered: data.web_search_triggered === true,
        webSources: Array.isArray(data.web_sources) ? data.web_sources : [],
        sourceType: data.source_type ?? "pdf"
      }]);
    } catch (e2) {
      const msg = e2 instanceof Error ? e2.message : "Request failed — check your network and backend.";
      setMessages((m) => [...m, {
        role: "assistant",
        content: msg,
        isError: true
      }]);
    } finally {
      setSending(false);
    }
  };
  return /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { className: "flex h-screen overflow-hidden bg-zinc-950", children: [
    /* @__PURE__ */ jsxRuntimeExports.jsx(Toaster, {}),
    /* @__PURE__ */ jsxRuntimeExports.jsxs("aside", { className: "w-72 flex-shrink-0 flex flex-col border-r border-zinc-800/60 bg-zinc-950", children: [
      /* @__PURE__ */ jsxRuntimeExports.jsx("div", { className: "px-5 py-5 border-b border-zinc-800/60", children: /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { className: "flex items-center gap-3", children: [
        /* @__PURE__ */ jsxRuntimeExports.jsx("div", { className: "h-9 w-9 rounded-xl bg-indigo-600 grid place-items-center shadow-lg shadow-indigo-900/40 shrink-0", children: /* @__PURE__ */ jsxRuntimeExports.jsx(BookOpen, { className: "h-5 w-5 text-white" }) }),
        /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { className: "min-w-0", children: [
          /* @__PURE__ */ jsxRuntimeExports.jsx("h1", { className: "text-sm font-bold text-white tracking-tight", children: "DocuMind AI" }),
          /* @__PURE__ */ jsxRuntimeExports.jsx("p", { className: "text-[10px] text-zinc-500 leading-tight mt-0.5", children: "PDF RAG Assistant with Hybrid Retrieval" })
        ] })
      ] }) }),
      /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { className: "flex-1 overflow-y-auto px-4 py-5 space-y-4", children: [
        /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { role: "button", tabIndex: 0, "aria-label": "Upload PDF", onDragOver: (e) => {
          e.preventDefault();
          if (!isBusy) setDragOver(true);
        }, onDragLeave: () => setDragOver(false), onDrop: (e) => {
          e.preventDefault();
          setDragOver(false);
          if (!isBusy) {
            const file = e.dataTransfer.files[0];
            if (file) handleFile(file);
          }
        }, onClick: () => {
          if (!isBusy) fileInputRef.current?.click();
        }, onKeyDown: (e) => {
          if ((e.key === "Enter" || e.key === " ") && !isBusy) {
            e.preventDefault();
            fileInputRef.current?.click();
          }
        }, className: cn("relative flex flex-col items-center justify-center gap-2 p-6 rounded-xl border-2 border-dashed select-none transition-all duration-200", isBusy ? "border-zinc-700 opacity-70 cursor-not-allowed" : dragOver ? "border-indigo-500 bg-indigo-500/10 cursor-copy" : "border-zinc-700 hover:border-zinc-500 hover:bg-zinc-800/40 cursor-pointer"), children: [
          /* @__PURE__ */ jsxRuntimeExports.jsx("input", { ref: fileInputRef, type: "file", accept: ".pdf", className: "hidden", onChange: (e) => {
            const f = e.target.files?.[0];
            if (f) handleFile(f);
          } }),
          isUploading ? /* @__PURE__ */ jsxRuntimeExports.jsxs(jsxRuntimeExports.Fragment, { children: [
            /* @__PURE__ */ jsxRuntimeExports.jsx(LoaderCircle, { className: "h-7 w-7 text-indigo-400 animate-spin" }),
            /* @__PURE__ */ jsxRuntimeExports.jsx("p", { className: "text-xs font-semibold text-zinc-200", children: "Uploading..." }),
            /* @__PURE__ */ jsxRuntimeExports.jsx("p", { className: "text-[10px] text-zinc-500 text-center", children: "Transferring file to server" })
          ] }) : isIndexing ? /* @__PURE__ */ jsxRuntimeExports.jsxs(jsxRuntimeExports.Fragment, { children: [
            /* @__PURE__ */ jsxRuntimeExports.jsx(LoaderCircle, { className: "h-7 w-7 text-indigo-400 animate-spin" }),
            /* @__PURE__ */ jsxRuntimeExports.jsx("p", { className: "text-xs font-semibold text-zinc-200", children: "Building index..." }),
            /* @__PURE__ */ jsxRuntimeExports.jsx("p", { className: "text-[10px] text-zinc-500 text-center", children: "Parsing and embedding document chunks" })
          ] }) : /* @__PURE__ */ jsxRuntimeExports.jsxs(jsxRuntimeExports.Fragment, { children: [
            /* @__PURE__ */ jsxRuntimeExports.jsx("div", { className: cn("h-11 w-11 rounded-xl grid place-items-center transition-all", dragOver ? "bg-indigo-500/20" : "bg-zinc-800"), children: /* @__PURE__ */ jsxRuntimeExports.jsx(Upload, { className: cn("h-5 w-5 transition-colors", dragOver ? "text-indigo-400" : "text-zinc-500") }) }),
            /* @__PURE__ */ jsxRuntimeExports.jsx("p", { className: "text-xs font-semibold text-zinc-300", children: "Drop PDF here" }),
            /* @__PURE__ */ jsxRuntimeExports.jsx("p", { className: "text-[10px] text-zinc-600", children: "or click to browse files" })
          ] })
        ] }),
        sidebarError && /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { className: "flex items-start gap-2.5 p-3 rounded-lg bg-red-500/10 border border-red-500/20", children: [
          /* @__PURE__ */ jsxRuntimeExports.jsx(CircleAlert, { className: "h-4 w-4 text-red-400 shrink-0 mt-0.5" }),
          /* @__PURE__ */ jsxRuntimeExports.jsx("p", { className: "flex-1 text-[11px] text-red-300 leading-snug", children: sidebarError }),
          /* @__PURE__ */ jsxRuntimeExports.jsx("button", { onClick: () => setSidebarError(null), className: "shrink-0 text-red-500 hover:text-red-300 transition-colors", children: /* @__PURE__ */ jsxRuntimeExports.jsx(X, { className: "h-3.5 w-3.5" }) })
        ] }),
        docStatus && !isBusy && /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { className: "flex items-start gap-2.5 p-3 rounded-lg bg-emerald-500/10 border border-emerald-500/20", children: [
          /* @__PURE__ */ jsxRuntimeExports.jsx(CircleCheck, { className: "h-4 w-4 text-emerald-400 shrink-0 mt-0.5" }),
          /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { className: "min-w-0", children: [
            /* @__PURE__ */ jsxRuntimeExports.jsx("p", { className: "text-[11px] font-semibold text-emerald-300 truncate", children: docStatus.filename }),
            /* @__PURE__ */ jsxRuntimeExports.jsxs("p", { className: "text-[10px] text-zinc-500 mt-0.5", children: [
              docStatus.chunksLoaded,
              " chunks indexed and ready"
            ] })
          ] })
        ] }),
        /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { className: "border-t border-zinc-800/60 pt-4", children: [
          /* @__PURE__ */ jsxRuntimeExports.jsx("p", { className: "text-[9px] uppercase tracking-[0.12em] text-zinc-600 font-semibold mb-2", children: "Active Document" }),
          docStatus ? /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { className: "flex items-center gap-2", children: [
            /* @__PURE__ */ jsxRuntimeExports.jsx("div", { className: "h-6 w-6 rounded-md bg-indigo-500/10 grid place-items-center shrink-0", children: /* @__PURE__ */ jsxRuntimeExports.jsx(FileText, { className: "h-3.5 w-3.5 text-indigo-400" }) }),
            /* @__PURE__ */ jsxRuntimeExports.jsx("span", { className: "text-[11px] text-zinc-300 truncate", children: docStatus.filename })
          ] }) : /* @__PURE__ */ jsxRuntimeExports.jsx("p", { className: "text-[11px] text-zinc-700 italic", children: "No document loaded" })
        ] })
      ] }),
      /* @__PURE__ */ jsxRuntimeExports.jsx("div", { className: "px-5 py-3 border-t border-zinc-800/60", children: /* @__PURE__ */ jsxRuntimeExports.jsxs("p", { className: "text-[10px] text-zinc-700", children: [
        "Backend: ",
        /* @__PURE__ */ jsxRuntimeExports.jsx("span", { className: "font-mono text-zinc-600", children: API_BASE })
      ] }) })
    ] }),
    /* @__PURE__ */ jsxRuntimeExports.jsxs("main", { className: "flex-1 flex flex-col min-w-0 bg-zinc-50", children: [
      /* @__PURE__ */ jsxRuntimeExports.jsxs("header", { className: "flex items-center justify-between px-6 py-4 border-b border-zinc-200 bg-white shrink-0", children: [
        /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { children: [
          /* @__PURE__ */ jsxRuntimeExports.jsx("h2", { className: "text-sm font-semibold text-zinc-900", children: "Chat" }),
          /* @__PURE__ */ jsxRuntimeExports.jsx("p", { className: "text-xs text-zinc-400 mt-0.5", children: docStatus ? `Querying · ${docStatus.filename}` : "Upload and index a PDF to get started" })
        ] }),
        docStatus && /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { className: "flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-emerald-50 border border-emerald-200 shrink-0", children: [
          /* @__PURE__ */ jsxRuntimeExports.jsx("div", { className: "h-1.5 w-1.5 rounded-full bg-emerald-400" }),
          /* @__PURE__ */ jsxRuntimeExports.jsxs("span", { className: "text-[10px] font-medium text-emerald-700", children: [
            docStatus.chunksLoaded,
            " chunks ready"
          ] })
        ] })
      ] }),
      /* @__PURE__ */ jsxRuntimeExports.jsx("div", { ref: scrollRef, className: "flex-1 overflow-y-auto", children: /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { className: "mx-auto max-w-3xl px-6 py-8 space-y-5", children: [
        messages.length === 0 && /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { className: "flex flex-col items-center justify-center py-24 text-center select-none", children: [
          /* @__PURE__ */ jsxRuntimeExports.jsx("div", { className: "h-16 w-16 rounded-2xl bg-indigo-600 grid place-items-center mb-5 shadow-lg shadow-indigo-200", children: /* @__PURE__ */ jsxRuntimeExports.jsx(Sparkles, { className: "h-8 w-8 text-white" }) }),
          /* @__PURE__ */ jsxRuntimeExports.jsx("h3", { className: "text-base font-semibold text-zinc-700 mb-2", children: "Ask your document anything" }),
          /* @__PURE__ */ jsxRuntimeExports.jsx("p", { className: "text-sm text-zinc-400 max-w-xs leading-relaxed", children: "Drop a PDF in the sidebar to index it, then ask any question about its contents." })
        ] }),
        messages.map((m, i) => /* @__PURE__ */ jsxRuntimeExports.jsx(MessageBubble, { message: m }, i)),
        sending && /* @__PURE__ */ jsxRuntimeExports.jsx(ThinkingIndicator, {})
      ] }) }),
      /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { className: "border-t border-zinc-200 bg-white px-6 py-4 shrink-0", children: [
        /* @__PURE__ */ jsxRuntimeExports.jsxs("form", { onSubmit: handleSend, className: "mx-auto max-w-3xl flex items-end gap-3", children: [
          /* @__PURE__ */ jsxRuntimeExports.jsx("textarea", { ref: textareaRef, value: question, rows: 1, disabled: sending, placeholder: "Ask anything about your document...", onChange: (e) => {
            setQuestion(e.target.value);
            e.target.style.height = "auto";
            e.target.style.height = Math.min(e.target.scrollHeight, 160) + "px";
          }, onKeyDown: (e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              handleSend();
            }
          }, className: "flex-1 resize-none rounded-xl border border-zinc-200 bg-zinc-50 px-4 py-3 text-sm text-zinc-800 placeholder:text-zinc-400 focus:outline-none focus:ring-2 focus:ring-indigo-500/40 focus:border-indigo-400 transition-all disabled:opacity-50 min-h-[44px] max-h-40 leading-relaxed" }),
          /* @__PURE__ */ jsxRuntimeExports.jsx(Button, { type: "submit", size: "icon", disabled: sending || !question.trim(), className: "h-11 w-11 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white shrink-0 disabled:opacity-40 transition-colors shadow-sm", children: sending ? /* @__PURE__ */ jsxRuntimeExports.jsx(LoaderCircle, { className: "h-4 w-4 animate-spin" }) : /* @__PURE__ */ jsxRuntimeExports.jsx(Send, { className: "h-4 w-4" }) })
        ] }),
        /* @__PURE__ */ jsxRuntimeExports.jsx("p", { className: "text-[10px] text-zinc-400 text-center mt-2.5 select-none", children: "Enter to send · Shift+Enter for new line" })
      ] })
    ] })
  ] });
}
export {
  Index as component
};
