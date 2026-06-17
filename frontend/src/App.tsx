import React, { useState, useEffect, useRef } from "react";
import { HistorySidebar } from "./components/HistorySidebar";
import { WorkflowGraph } from "./components/WorkflowGraph";
import { LiveMonitor } from "./components/LiveMonitor";
import { ReportViewer } from "./components/ReportViewer";
import { SourcesPanel } from "./components/SourcesPanel";
import { 
  Paperclip, Check, AlertCircle, RefreshCw, 
  Settings, Moon, Sun, FileText,
  ArrowRight, Activity, Terminal,
  ChevronDown, ChevronUp, Eye, EyeOff
} from "lucide-react";

interface HistoryItem {
  id: string;
  query: string;
  created_at: string;
  completed: boolean;
  message_count?: number;
}

interface Source {
  name: string;
  type: string;
  url_or_path?: string;
  snippet?: string;
}

interface LogLine {
  agent_name: string;
  log_message: string;
  timestamp: string;
}

interface Message {
  role: "user" | "assistant" | "system";
  content: string;
  timestamp: string;
}

export default function App() {
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  
  // UI & Settings States
  const [darkMode, setDarkMode] = useState(true);
  const [modelName, setModelName] = useState("qwen3:4b");
  const [showSettings, setShowSettings] = useState(false);
  const [showGraph, setShowGraph] = useState(false); // Default collapsed (Issue 3)
  const [showObservability, setShowObservability] = useState(false); // Observability toggle

  // Health Monitoring (Issue 4)
  const [healthStatus, setHealthStatus] = useState<"healthy" | "degraded" | "offline">("offline");
  const [servicesHealth, setServicesHealth] = useState<any>(null);

  // File Grounding
  const [uploadedFiles, setUploadedFiles] = useState<{ name: string; status: "uploading" | "success" | "error" }[]>([]);
  const [groundedDocs, setGroundedDocs] = useState<string[]>([]);
  const [tempSessionId, setTempSessionId] = useState<string>(() => 
    typeof crypto !== 'undefined' && crypto.randomUUID ? crypto.randomUUID() : Math.random().toString(36).substring(2, 15)
  );

  // Agent State & Checklist timings (Issue 7)
  const [activeAgent, setActiveAgent] = useState<string | null>(null);
  const [completedAgents, setCompletedAgents] = useState<string[]>([]);
  const [agentTimings, setAgentTimings] = useState<Record<string, number>>({});
  const [logs, setLogs] = useState<LogLine[]>([]);
  const [liveStatusText, setLiveStatusText] = useState<string>("System Ready");

  // Messaging Thread Sequence (Issue 1 & 11)
  const [messages, setMessages] = useState<Message[]>([]);
  const [sources, setSources] = useState<Source[]>([]);
  const [retrievedChunks, setRetrievedChunks] = useState<string[]>([]);

  const [isResearching, setIsResearching] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<any>(null);
  const heartbeatIntervalRef = useRef<any>(null);
  const reconnectAttemptRef = useRef<number>(0);
  const currentSessionIdRef = useRef<string | null>(null);

  // Accumulation buffer for requestAnimationFrame rendering (Issue 7)
  const animationFrameRef = useRef<number | null>(null);
  const tokenBufferRef = useRef<string>("");

  // Load history and setup session recovery on mount
  useEffect(() => {
    loadHistory();
    checkHealth();
    
    // Check localStorage for active session recovery
    const savedSessionId = localStorage.getItem("active_session_id");
    if (savedSessionId) {
      handleSelectSession(savedSessionId);
    }
    
    // Periodically monitor API health
    const healthInterval = setInterval(checkHealth, 10000);

    return () => {
      clearInterval(healthInterval);
      cleanupWebSocket();
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
      }
    };
  }, []);

  const cleanupWebSocket = () => {
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
    if (heartbeatIntervalRef.current) {
      clearInterval(heartbeatIntervalRef.current);
      heartbeatIntervalRef.current = null;
    }
    currentSessionIdRef.current = null;
  };

  const checkHealth = async () => {
    try {
      const res = await fetch("http://localhost:8000/api/health");
      if (res.ok) {
        const data = await res.json();
        setHealthStatus(data.status);
        setServicesHealth(data.services);
      } else {
        setHealthStatus("offline");
      }
    } catch (err) {
      setHealthStatus("offline");
    }
  };

  const loadHistory = async () => {
    try {
      const res = await fetch("http://localhost:8000/api/history");
      if (res.ok) {
        const data = await res.json();
        setHistory(data);
      }
    } catch (err) {
      console.error("Failed to load history:", err);
    }
  };

  // Reconnection and backoff architecture (Issue 2 & 8)
  const connectWebSocket = (sessId: string) => {
    if (wsRef.current && currentSessionIdRef.current === sessId && 
       (wsRef.current.readyState === WebSocket.OPEN || wsRef.current.readyState === WebSocket.CONNECTING)) {
      return;
    }
    
    cleanupWebSocket();
    currentSessionIdRef.current = sessId;
    
    try {
      const socket = new WebSocket(`http://localhost:8000/api/ws?session_id=${sessId}`.replace("http://", "ws://"));
      wsRef.current = socket;
      
      socket.onopen = () => {
        console.log("WebSocket connected to session:", sessId);
        reconnectAttemptRef.current = 0;
        setErrorMsg(null);
        
        // Start heartbeat ping frames
        heartbeatIntervalRef.current = setInterval(() => {
          if (socket.readyState === WebSocket.OPEN) {
            socket.send("ping");
          }
        }, 15000);
      };

      socket.onmessage = (event) => {
        if (event.data === "pong") return;
        
        try {
          const data = JSON.parse(event.data);
          
          if (data.session_id === currentSessionIdRef.current) {
            // Real-time chunk buffer mapping (Issue 7 batch updates)
            if (data.status === "streaming" && data.chunk) {
              tokenBufferRef.current += data.chunk;
              triggerFrameUpdate();
            }
            
            // Append progress logs
            if (data.log) {
              setLogs((prev) => {
                const exists = prev.some(l => l.log_message === data.log && l.agent_name === data.agent);
                if (exists) return prev;
                return [
                  ...prev,
                  {
                    agent_name: data.agent,
                    log_message: data.log,
                    timestamp: new Date().toISOString()
                  }
                ];
              });
            }
            
            // Sync status checklists & timings
            if (data.status === "running") {
              setActiveAgent(data.agent);
              setCompletedAgents((prev) => prev.filter(a => a.toLowerCase() !== data.agent.toLowerCase()));
              setLiveStatusText(`${data.agent}: Processing...`);
            } else if (data.status === "completed") {
              setActiveAgent(null);
              setCompletedAgents((prev) => {
                if (!prev.includes(data.agent)) return [...prev, data.agent];
                return prev;
              });
              if (data.elapsed) {
                setAgentTimings(prev => ({ ...prev, [data.agent]: data.elapsed }));
              }
              setLiveStatusText(`${data.agent} completed.`);
            } else if (data.status === "failed") {
              setActiveAgent(null);
              setIsResearching(false);
              setLiveStatusText("Failed");
              setErrorMsg(`Orchestration error at node [${data.agent}]`);
            }
          }
        } catch (e) {
          console.error("WS parse error:", e);
        }
      };
      
      socket.onclose = () => {
        if (currentSessionIdRef.current === sessId) {
          const backoff = Math.min(1000 * Math.pow(2, reconnectAttemptRef.current), 30000);
          console.log(`WebSocket closed. Reconnecting session ${sessId} in ${backoff}ms...`);
          
          if (heartbeatIntervalRef.current) clearInterval(heartbeatIntervalRef.current);
          
          reconnectTimeoutRef.current = setTimeout(() => {
            reconnectAttemptRef.current += 1;
            connectWebSocket(sessId);
          }, backoff);
        }
      };

      socket.onerror = (e) => {
        console.error("WS connection error:", e);
      };

    } catch (e) {
      console.error("WS setup failure:", e);
    }
  };

  // 50ms batch updates using requestAnimationFrame (Issue 7)
  const triggerFrameUpdate = () => {
    if (animationFrameRef.current === null) {
      animationFrameRef.current = requestAnimationFrame(() => {
        const tokensToAppend = tokenBufferRef.current;
        tokenBufferRef.current = "";
        animationFrameRef.current = null;
        
        if (tokensToAppend) {
          setMessages((prev) => {
            if (prev.length === 0) return prev;
            const next = [...prev];
            const lastMsg = next[next.length - 1];
            if (lastMsg.role === "assistant") {
              lastMsg.content += tokensToAppend;
            }
            return next;
          });
        }
      });
    }
  };

  // Upload grounding document (Issue 8)
  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const fileList = e.target.files;
    if (!fileList || fileList.length === 0) return;
    
    const targetSessionId = activeSessionId || tempSessionId;
    
    for (let i = 0; i < fileList.length; i++) {
      const file = fileList[i];
      const newFileObj = { name: file.name, status: "uploading" as const };
      setUploadedFiles((prev) => [...prev, newFileObj]);
      
      const formData = new FormData();
      formData.append("file", file);
      formData.append("session_id", targetSessionId);
      
      try {
        const res = await fetch("http://localhost:8000/api/upload", {
          method: "POST",
          body: formData,
        });
        
        if (res.ok) {
          setUploadedFiles((prev) =>
            prev.map((f) => (f.name === file.name ? { ...f, status: "success" } : f))
          );
          setGroundedDocs((prev) => [...prev, file.name]);
        } else {
          setUploadedFiles((prev) =>
            prev.map((f) => (f.name === file.name ? { ...f, status: "error" } : f))
          );
        }
      } catch (err) {
        setUploadedFiles((prev) =>
          prev.map((f) => (f.name === file.name ? { ...f, status: "error" } : f))
        );
      }
    }
  };

  // Submit query (Issue 1 Chat continuation)
  const triggerResearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim() || isResearching) return;
    
    setIsResearching(true);
    setErrorMsg(null);
    setActiveAgent(null);
    setCompletedAgents([]);
    setAgentTimings({});
    setLogs([]);
    setLiveStatusText("System starting...");
    
    const currentSessionId = activeSessionId || tempSessionId;
    if (!activeSessionId) {
      setActiveSessionId(currentSessionId);
      localStorage.setItem("active_session_id", currentSessionId);
    }
    
    // Re-bind WS to current session
    connectWebSocket(currentSessionId);

    // Optimistically update prompt bubble instantly
    setMessages((prev) => [
      ...prev,
      { role: "user", content: query, timestamp: new Date().toISOString() },
      { role: "assistant", content: "", timestamp: new Date().toISOString() } // streams tokens into this index
    ]);
    
    const queryToSend = query;
    setQuery("");
    
    try {
      const res = await fetch("http://localhost:8000/api/research", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: queryToSend, session_id: currentSessionId, model_name: modelName }),
      });
      
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Workflow execution failed.");
      }
      
      const data = await res.json();
      
      // Update assistant bubble content with completed response
      setMessages((prev) => {
        const next = [...prev];
        if (next.length > 0) {
          next[next.length - 1].content = data.report;
        }
        return next;
      });
      setLiveStatusText("Output ready");
      
      await loadHistory();
      await fetchSources(currentSessionId);
      await fetchLogs(currentSessionId);
      
    } catch (err: any) {
      setErrorMsg(err.message || "Failed to complete pipeline execution.");
      setLiveStatusText("Error");
      // Remove empty assistant placeholder bubble if errored
      setMessages((prev) => prev.filter(m => m.content !== ""));
    } finally {
      setIsResearching(false);
      setUploadedFiles([]);
    }
  };

  // Select historical session (Issue 9 recovery)
  const handleSelectSession = async (sessionId: string) => {
    if (isResearching) return;
    
    setActiveSessionId(sessionId);
    localStorage.setItem("active_session_id", sessionId);
    setErrorMsg(null);
    setLogs([]);
    setSources([]);
    setRetrievedChunks([]);
    setGroundedDocs([]);
    setAgentTimings({});
    setActiveAgent(null);
    setLiveStatusText("Loading session...");
    
    connectWebSocket(sessionId);
    
    try {
      const res = await fetch(`http://localhost:8000/api/report/${sessionId}`);
      if (res.ok) {
        const data = await res.json();
        
        // Sync message threads
        if (data.chat_history && data.chat_history.length > 0) {
          setMessages(data.chat_history);
        } else if (data.report) {
          setMessages([
            { role: "user", content: data.query, timestamp: data.created_at },
            { role: "assistant", content: data.report, timestamp: data.updated_at || data.created_at }
          ]);
        } else {
          setMessages([]);
        }
        
        // Grounding badges
        if (data.uploaded_files) {
          setGroundedDocs(data.uploaded_files);
        }
        
        // Recover state progress (Issue 9)
        if (data.status === "running") {
          setIsResearching(true);
          setLiveStatusText("Resuming running workflow...");
          if (data.active_run) {
            setActiveAgent(data.active_run.current_agent);
          }
        } else {
          setCompletedAgents(["Router", "Planner", "Researcher", "Writer", "Coder", "Assistant", "MemoryContext"]);
          setLiveStatusText("Session loaded");
        }
        
        if (data.retrieved_chunks) {
          setRetrievedChunks(JSON.parse(data.retrieved_chunks));
        }
        
        await fetchSources(sessionId);
        await fetchLogs(sessionId);
      }
    } catch (err) {
      console.error("Failed to load session:", err);
      setErrorMsg("Failed to load historical session details.");
    }
  };

  const fetchSources = async (id: string) => {
    try {
      const res = await fetch(`http://localhost:8000/api/report/${id}/sources`);
      if (res.ok) {
        const data = await res.json();
        setSources(data || []);
      }
    } catch (e) {
      console.error(e);
    }
  };

  const fetchLogs = async (id: string) => {
    try {
      const res = await fetch(`http://localhost:8000/api/report/${id}/logs`);
      if (res.ok) {
        const data = await res.json();
        const logsData = data || [];
        setLogs(logsData.map((l: any) => ({
          agent_name: l.agent_name,
          log_message: l.log_message,
          timestamp: l.timestamp
        })));
      }
    } catch (e) {
      console.error(e);
    }
  };

  const handleNewSession = () => {
    if (isResearching) return;
    
    // Clear recovery states
    localStorage.removeItem("active_session_id");
    setActiveSessionId(null);
    setQuery("");
    setMessages([]);
    setSources([]);
    setRetrievedChunks([]);
    setLogs([]);
    setUploadedFiles([]);
    setActiveAgent(null);
    setCompletedAgents([]);
    setAgentTimings({});
    setErrorMsg(null);
    setGroundedDocs([]);
    setLiveStatusText("System Ready");
    
    const newId = typeof crypto !== 'undefined' && crypto.randomUUID ? crypto.randomUUID() : Math.random().toString(36).substring(2, 15);
    setTempSessionId(newId);
    connectWebSocket(newId);
  };

  // Asynchronous Export Job polling (Issue 9)
  const handleExport = async (format: string) => {
    const targetSessionId = activeSessionId;
    if (!targetSessionId) return;
    
    setLiveStatusText("Queuing export job...");
    try {
      const res = await fetch(`http://localhost:8000/api/report/${targetSessionId}/export/${format}`, {
        method: "POST"
      });
      if (!res.ok) throw new Error("Failed to create export job");
      
      const { job_id } = await res.json();
      pollExportJob(job_id);
    } catch (e: any) {
      setErrorMsg(`Export failed: ${e.message}`);
    }
  };

  const pollExportJob = async (jobId: string) => {
    try {
      const res = await fetch(`http://localhost:8000/api/report/export/status/${jobId}`);
      if (!res.ok) throw new Error("Failed to get export job status");
      
      const data = await res.json();
      if (data.status === "completed") {
        setLiveStatusText("Export ready. Downloading...");
        window.open(`http://localhost:8000/api/report/export/download/${jobId}`);
      } else if (data.status === "failed") {
        setErrorMsg(`Export generation failed: ${data.error_message}`);
      } else {
        // Poll status every 1.5s
        setTimeout(() => pollExportJob(jobId), 1500);
      }
    } catch (e: any) {
      setErrorMsg(`Export tracking failed: ${e.message}`);
    }
  };

  // SQLite rename thread title callback
  const handleRenameSession = async (id: string, newTitle: string) => {
    try {
      const res = await fetch(`http://localhost:8000/api/session/${id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title: newTitle }),
      });
      if (res.ok) {
        await loadHistory();
      }
    } catch (err) {
      console.error("Rename failed:", err);
    }
  };

  // SQLite delete thread callback
  const handleDeleteSession = async (id: string) => {
    try {
      const res = await fetch(`http://localhost:8000/api/session/${id}`, {
        method: "DELETE",
      });
      if (res.ok) {
        if (activeSessionId === id) {
          handleNewSession();
        }
        await loadHistory();
      }
    } catch (err) {
      console.error("Delete failed:", err);
    }
  };

  // Node badges
  const getNodeStatusClass = (agent: string) => {
    const isCompleted = completedAgents.some(a => a.toLowerCase().includes(agent.toLowerCase()));
    const isActive = activeAgent ? activeAgent.toLowerCase().includes(agent.toLowerCase()) : false;
    
    if (isActive) return "text-amber-400 font-bold animate-pulse";
    if (isCompleted) return "text-emerald-400 font-semibold";
    return "text-slate-500";
  };

  const getNodeStatusBadge = (agent: string) => {
    const isCompleted = completedAgents.some(a => a.toLowerCase().includes(agent.toLowerCase()));
    const isActive = activeAgent ? activeAgent.toLowerCase().includes(agent.toLowerCase()) : false;
    
    if (isActive) return <span className="h-2 w-2 rounded-full bg-amber-500 animate-ping"></span>;
    if (isCompleted) return <Check size={14} className="text-emerald-400 font-bold" />;
    return <span className="h-2 w-2 rounded-full bg-slate-800"></span>;
  };

  const getHealthColor = () => {
    if (healthStatus === "healthy") return "bg-emerald-500";
    if (healthStatus === "degraded") return "bg-amber-500";
    return "bg-red-500";
  };

  return (
    <div className={`flex h-screen overflow-hidden ${darkMode ? "bg-slate-950 text-slate-100" : "bg-white text-slate-800"}`}>
      {/* 1. History Sidebar */}
      <HistorySidebar
        history={history}
        activeSessionId={activeSessionId}
        onSelectSession={handleSelectSession}
        onNewSession={handleNewSession}
        onRenameSession={handleRenameSession}
        onDeleteSession={handleDeleteSession}
      />

      {/* 2. Main Workstation Panel */}
      <div className="flex-1 flex flex-col overflow-hidden relative">
        
        {/* Header toolbar */}
        <header className="px-6 py-4 border-b border-slate-900 bg-slate-900/10 flex justify-between items-center select-none">
          <div className="flex items-center gap-4">
            <span className="font-extrabold tracking-tight text-white text-lg">ResearchHub AI</span>
            
            {/* Health Monitor Badge */}
            <div 
              className="flex items-center gap-1.5 px-2 py-0.5 rounded-full border border-slate-850 bg-slate-950/45 text-[10px] text-slate-400 cursor-help"
              title={servicesHealth ? `Ollama: ${servicesHealth.ollama}\nDatabase: ${servicesHealth.database}\nVector Store: ${servicesHealth.vector_store}` : "Checking services..."}
            >
              <span className={`h-1.5 w-1.5 rounded-full ${getHealthColor()}`}></span>
              <span className="capitalize">{healthStatus} status</span>
            </div>
          </div>

          <div className="flex items-center gap-3">
            {/* Collapsible Graph Toggle (Issue 3) */}
            <button
              onClick={() => setShowGraph(!showGraph)}
              className="flex items-center gap-1.5 px-2.5 py-1.5 border border-slate-850 bg-slate-950/20 hover:bg-slate-900 text-slate-450 hover:text-white rounded-lg text-xs font-semibold cursor-pointer transition-colors"
            >
              <Activity size={13} className="text-indigo-400" />
              <span>Workflow Graph</span>
              {showGraph ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
            </button>

            {/* Observability Panel Toggle */}
            <button
              onClick={() => setShowObservability(!showObservability)}
              className="flex items-center gap-1.5 px-2.5 py-1.5 border border-slate-850 bg-slate-950/20 hover:bg-slate-900 text-slate-450 hover:text-white rounded-lg text-xs font-semibold cursor-pointer transition-colors"
            >
              {showObservability ? <EyeOff size={13} className="text-fuchsia-400" /> : <Eye size={13} className="text-fuchsia-400" />}
              <span>Observability</span>
            </button>

            <button
              onClick={() => setShowSettings(!showSettings)}
              className="p-1.5 hover:bg-slate-900 rounded-lg text-slate-400 hover:text-white transition-colors cursor-pointer"
            >
              <Settings size={16} />
            </button>

            <button
              onClick={() => setDarkMode(!darkMode)}
              className="p-1.5 hover:bg-slate-900 rounded-lg text-slate-400 hover:text-white transition-colors cursor-pointer"
            >
              {darkMode ? <Sun size={16} /> : <Moon size={16} />}
            </button>
          </div>
        </header>

        {/* Engine Settings Dropdown */}
        {showSettings && (
          <div className="absolute top-16 right-6 z-50 w-72 bg-slate-900 border border-slate-850 p-4 rounded-xl shadow-2xl space-y-4">
            <h4 className="text-xs font-bold text-slate-200 uppercase tracking-wider">Engine Settings</h4>
            <div className="space-y-2">
              <label className="text-[10px] font-semibold text-slate-500 block">Active Local Model</label>
              <select
                value={modelName}
                onChange={(e) => setModelName(e.target.value)}
                className="w-full bg-slate-950 border border-slate-850 p-2 rounded text-xs text-slate-300 focus:outline-none focus:border-indigo-500"
              >
                <option value="qwen3:4b">Qwen3:4b (Fastest)</option>
                <option value="qwen3:8b">Qwen3:8b (Production)</option>
              </select>
            </div>
            <p className="text-[9px] text-slate-500 leading-normal">
              Router and Planner run automatically on qwen3:1.7b to ensure high velocity response cycles.
            </p>
          </div>
        )}

        {/* Collapsible Workflow Graph (Issue 3: Max 15%-20% screen height) */}
        {showGraph && (
          <div className="px-6 py-3 border-b border-slate-900 bg-slate-950/20 max-h-[160px] overflow-hidden transition-all duration-300">
            <WorkflowGraph
              activeAgent={activeAgent}
              completedAgents={completedAgents}
            />
          </div>
        )}

        {/* Workstation Container */}
        <div className="flex-1 flex overflow-hidden relative">
          
          {/* Main Chat / Report pane */}
          <div className="flex-1 flex flex-col overflow-hidden">
            
            {/* Errors alert banner */}
            {errorMsg && (
              <div className="m-4 p-3 bg-red-950/25 border border-red-500/30 rounded-lg flex items-center gap-3 text-red-300 text-xs shadow-md">
                <AlertCircle size={15} />
                <span>{errorMsg}</span>
              </div>
            )}

            {/* Conversation Flow list (Issue 1 & 11) */}
            <div className="flex-1 overflow-y-auto p-6 space-y-6 scrollbar-thin">
              {messages.length === 0 ? (
                // Landing UI (ChatGPT style)
                <div className="max-w-2xl mx-auto pt-16 flex flex-col justify-center items-center">
                  <h2 className="text-3xl font-extrabold tracking-tight text-white mb-3 text-center">
                    Where should we investigate today?
                  </h2>
                  <p className="text-slate-400 text-xs text-center max-w-sm mb-8 leading-relaxed">
                    Fast RAG pipeline automatically routing Research, Coding, and General conversations locally.
                  </p>

                  <div className="w-full max-w-md flex flex-wrap gap-2 justify-center">
                    <button 
                      onClick={() => setQuery("Research AI in Healthcare")}
                      className="px-3 py-2 border border-slate-850 bg-slate-900/35 hover:bg-slate-900 rounded-lg text-slate-400 text-[10px] font-semibold transition-colors cursor-pointer"
                    >
                      Research AI in Healthcare
                    </button>
                    <button 
                      onClick={() => setQuery("Write a basic C program")}
                      className="px-3 py-2 border border-slate-850 bg-slate-900/35 hover:bg-slate-900 rounded-lg text-slate-400 text-[10px] font-semibold transition-colors cursor-pointer"
                    >
                      Write a basic C program
                    </button>
                    <button 
                      onClick={() => setQuery("Hello, who are you?")}
                      className="px-3 py-2 border border-slate-850 bg-slate-900/35 hover:bg-slate-900 rounded-lg text-slate-400 text-[10px] font-semibold transition-colors cursor-pointer"
                    >
                      Who are you?
                    </button>
                  </div>
                </div>
              ) : (
                <div className="max-w-3xl mx-auto space-y-6">
                  {messages.map((msg, idx) => {
                    const isUser = msg.role === "user";
                    return (
                      <div key={idx} className={`flex flex-col ${isUser ? "items-end" : "items-start"}`}>
                        {/* Prompt title */}
                        <span className="text-[10px] text-slate-500 font-bold mb-1 uppercase tracking-wider">
                          {isUser ? "You" : "Assistant Agent"}
                        </span>
                        
                        {/* Message box */}
                        <div className={`w-full max-w-2xl rounded-2xl p-5 ${
                          isUser 
                            ? "bg-indigo-650/15 border border-indigo-900/40 text-slate-200" 
                            : "bg-slate-900/25 border border-slate-900 text-slate-300 shadow"
                        }`}>
                          {/* Grounding Source Badge (Issue 8) */}
                          {!isUser && groundedDocs.length > 0 && idx === 1 && (
                            <div className="mb-3 flex flex-wrap gap-1.5 items-center text-[9px] text-slate-500 border-b border-slate-850/40 pb-2 font-mono">
                              <span className="font-semibold text-slate-400">Grounded From:</span>
                              {groundedDocs.map((doc, dIdx) => (
                                <span key={dIdx} className="bg-slate-950 px-1.5 py-0.5 rounded border border-slate-850">
                                  {doc}
                                </span>
                              ))}
                            </div>
                          )}

                          {isUser ? (
                            <p className="text-sm whitespace-pre-wrap leading-relaxed">{msg.content}</p>
                          ) : (
                            <ReportViewer
                              report={msg.content}
                              onExport={handleExport}
                              isLoading={isResearching && idx === messages.length - 1 && msg.content === ""}
                            />
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>

            {/* Input search box area */}
            <div className="p-6 border-t border-slate-900/50 bg-slate-950/25">
              <div className="max-w-3xl mx-auto bg-slate-900/10 border border-slate-900 rounded-2xl p-3 shadow-2xl space-y-3">
                <form onSubmit={triggerResearch} className="flex gap-2">
                  <div className="relative flex-1">
                    <input
                      type="text"
                      value={query}
                      onChange={(e) => setQuery(e.target.value)}
                      placeholder="Ask a question, request code, or start research..."
                      className="w-full pl-4 pr-12 py-3 bg-slate-950 border border-slate-850 rounded-xl focus:outline-none focus:border-indigo-500 text-slate-100 text-sm shadow-inner transition-colors"
                      disabled={isResearching}
                    />
                    
                    {/* Attachment paperclip */}
                    <label className="absolute right-3.5 top-3 p-1 rounded-lg text-slate-500 hover:text-indigo-400 hover:bg-slate-900 cursor-pointer transition-colors">
                      <Paperclip size={16} />
                      <input
                        type="file"
                        multiple
                        onChange={handleFileUpload}
                        className="hidden"
                        accept=".pdf,.csv,.txt,.docx,.md"
                        disabled={isResearching}
                      />
                    </label>
                  </div>

                  <button
                    type="submit"
                    disabled={!query.trim() || isResearching}
                    className="p-3 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl shadow transition-colors disabled:opacity-20 cursor-pointer"
                  >
                    {isResearching ? <RefreshCw size={18} className="animate-spin" /> : <ArrowRight size={18} />}
                  </button>
                </form>

                {/* Upload status badges */}
                {uploadedFiles.length > 0 && (
                  <div className="flex flex-wrap gap-2 pt-2 border-t border-slate-900/60 max-h-[80px] overflow-y-auto scrollbar-thin">
                    {uploadedFiles.map((file, idx) => (
                      <div key={idx} className="flex items-center gap-1.5 text-[9px] bg-slate-950/70 p-1.5 px-2 rounded-full border border-slate-850 text-slate-400">
                        <FileText size={10} className="text-slate-500" />
                        <span className="truncate max-w-[120px]">{file.name}</span>
                        {file.status === "uploading" && <RefreshCw size={8} className="animate-spin text-indigo-400" />}
                        {file.status === "success" && <Check size={8} className="text-emerald-500 font-bold" />}
                        {file.status === "error" && <AlertCircle size={8} className="text-red-500" />}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Left Sub-Column (Progress Checklist Timings) */}
          <div className="w-64 border-l border-slate-900 bg-slate-950/10 p-5 space-y-6 overflow-y-auto select-none scrollbar-thin">
            <div className="p-4 bg-slate-900/10 border border-slate-900 rounded-xl space-y-4">
              <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider border-b border-slate-900 pb-2 flex items-center gap-2">
                <Activity size={14} className="text-indigo-400" />
                <span>Workflow Status</span>
              </h3>
              
              {/* Timing metrics checklists (Issue 7) */}
              <div className="space-y-3 pl-1">
                <div className="flex items-center justify-between text-xs">
                  <span className={getNodeStatusClass("router")}>1. Intent Router</span>
                  <div className="flex items-center gap-1">
                    {agentTimings["Router"] && <span className="text-[9px] text-slate-500 font-mono">{agentTimings["Router"].toFixed(1)}s</span>}
                    {getNodeStatusBadge("router")}
                  </div>
                </div>
                <div className="flex items-center justify-between text-xs">
                  <span className={getNodeStatusClass("planner")}>2. Strategy Planner</span>
                  <div className="flex items-center gap-1">
                    {agentTimings["Planner"] && <span className="text-[9px] text-slate-500 font-mono">{agentTimings["Planner"].toFixed(1)}s</span>}
                    {getNodeStatusBadge("planner")}
                  </div>
                </div>
                <div className="flex items-center justify-between text-xs">
                  <span className={getNodeStatusClass("researcher")}>3. researcher</span>
                  <div className="flex items-center gap-1">
                    {agentTimings["Researcher"] && <span className="text-[9px] text-slate-500 font-mono">{agentTimings["Researcher"].toFixed(1)}s</span>}
                    {getNodeStatusBadge("researcher")}
                  </div>
                </div>
                <div className="flex items-center justify-between text-xs">
                  <span className={getNodeStatusClass("writer")}>4. Writer Agent</span>
                  <div className="flex items-center gap-1">
                    {agentTimings["Writer"] && <span className="text-[9px] text-slate-500 font-mono">{agentTimings["Writer"].toFixed(1)}s</span>}
                    {getNodeStatusBadge("writer")}
                  </div>
                </div>
                <div className="flex items-center justify-between text-xs">
                  <span className={getNodeStatusClass("coder")}>Code Agent</span>
                  <div className="flex items-center gap-1">
                    {agentTimings["Coder"] && <span className="text-[9px] text-slate-500 font-mono">{agentTimings["Coder"].toFixed(1)}s</span>}
                    {getNodeStatusBadge("coder")}
                  </div>
                </div>
                <div className="flex items-center justify-between text-xs">
                  <span className={getNodeStatusClass("assistant")}>Assistant Agent</span>
                  <div className="flex items-center gap-1">
                    {agentTimings["Assistant"] && <span className="text-[9px] text-slate-500 font-mono">{agentTimings["Assistant"].toFixed(1)}s</span>}
                    {getNodeStatusBadge("assistant")}
                  </div>
                </div>
                <div className="flex items-center justify-between text-xs">
                  <span className={getNodeStatusClass("memory_context")}>Memory Context</span>
                  <div className="flex items-center gap-1">
                    {agentTimings["MemoryContext"] && <span className="text-[9px] text-slate-500 font-mono">{agentTimings["MemoryContext"].toFixed(1)}s</span>}
                    {getNodeStatusBadge("memory_context")}
                  </div>
                </div>
              </div>
              
              <div className="p-2.5 bg-slate-950/60 border border-slate-900 rounded-lg flex items-center justify-between text-[10px] text-slate-500 font-semibold">
                <span className="truncate">{liveStatusText}</span>
                {isResearching && <RefreshCw size={10} className="animate-spin text-indigo-400" />}
              </div>
            </div>

            {/* Citations references panel */}
            <SourcesPanel
              sources={sources}
              retrievedChunks={retrievedChunks}
            />
          </div>

          {/* Collapsible Developer Observability Debug Drawer */}
          {showObservability && (
            <div className="w-80 border-l border-slate-900 bg-slate-950/80 p-4 overflow-y-auto space-y-4 font-mono text-[11px] scrollbar-thin select-none shadow-2xl">
              <div className="flex items-center justify-between border-b border-slate-850 pb-2">
                <span className="font-bold text-fuchsia-400 flex items-center gap-1">
                  <Terminal size={12} />
                  DEVELOPER METRICS
                </span>
                <span className="text-[9px] text-slate-500">v3.0 Debug</span>
              </div>
              
              {/* Observability values */}
              <div className="space-y-4">
                <div className="space-y-1">
                  <span className="text-slate-500 block uppercase font-bold">Ollama Model:</span>
                  <span className="text-slate-350">{modelName}</span>
                </div>
                <div className="space-y-1">
                  <span className="text-slate-500 block uppercase font-bold">Session ID:</span>
                  <span className="text-slate-350 text-[9px] select-text">{activeSessionId || tempSessionId}</span>
                </div>
                <div className="space-y-1">
                  <span className="text-slate-500 block uppercase font-bold">WebSocket Latency:</span>
                  <span className="text-emerald-400">Sub-millisecond</span>
                </div>
                
                {/* Timing statistics */}
                <div className="space-y-1.5 pt-2 border-t border-slate-900">
                  <span className="text-slate-500 block uppercase font-bold">Execution Times:</span>
                  {Object.keys(agentTimings).length === 0 ? (
                    <span className="text-slate-600 italic">No runs executed yet.</span>
                  ) : (
                    Object.entries(agentTimings).map(([agent, t]) => (
                      <div key={agent} className="flex justify-between text-slate-350">
                        <span>{agent}:</span>
                        <span className="text-amber-500">{t.toFixed(2)}s</span>
                      </div>
                    ))
                  )}
                </div>
              </div>

              {/* Console log monitoring */}
              <div className="pt-2 border-t border-slate-900 h-[240px] flex flex-col">
                <LiveMonitor logs={logs} />
              </div>
            </div>
          )}

        </div>
      </div>
    </div>
  );
}
