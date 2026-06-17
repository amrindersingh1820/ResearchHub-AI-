import React, { useEffect, useRef } from "react";
import { Terminal } from "lucide-react";

interface LogLine {
  id?: number | string;
  agent_name: string;
  log_message: string;
  timestamp: string;
}

interface LiveMonitorProps {
  logs: LogLine[];
}

export const LiveMonitor: React.FC<LiveMonitorProps> = ({ logs = [] }) => {
  const terminalEndRef = useRef<HTMLDivElement>(null);
  const safeLogs = logs || [];

  useEffect(() => {
    // Keep scroll at bottom
    terminalEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [safeLogs]);

  // Color mapping based on agent name
  const getAgentColor = (name: string) => {
    const lowercase = name.toLowerCase();
    if (lowercase.includes("planner")) return "text-cyan-400";
    if (lowercase.includes("coordinator")) return "text-fuchsia-400";
    if (lowercase.includes("researcher")) return "text-sky-400";
    if (lowercase.includes("checker")) return "text-amber-400";
    if (lowercase.includes("critic")) return "text-orange-400";
    if (lowercase.includes("writer")) return "text-emerald-400";
    if (lowercase.includes("system")) return "text-red-400";
    return "text-slate-400";
  };

  return (
    <div className="flex flex-col h-[280px] bg-slate-950 border border-slate-800 rounded-lg overflow-hidden font-mono text-xs shadow-inner">
      <div className="px-4 py-2 border-b border-slate-800/80 bg-slate-900/50 flex justify-between items-center select-none">
        <div className="flex items-center gap-2 text-slate-400 font-semibold">
          <Terminal size={14} className="text-indigo-400" />
          <span>Execution Console Log</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse"></span>
          <span className="text-[10px] text-slate-500">Live Feedback</span>
        </div>
      </div>
      
      <div className="flex-1 overflow-y-auto p-4 space-y-1.5 scrollbar-thin">
        {safeLogs.length === 0 ? (
          <div className="text-slate-600 italic select-none">
            [System] Idle. Awaiting research query submission...
          </div>
        ) : (
          safeLogs.map((log, index) => {
            const timeStr = log.timestamp 
              ? new Date(log.timestamp).toLocaleTimeString() 
              : new Date().toLocaleTimeString();
            
            return (
              <div key={index} className="flex items-start gap-2 leading-relaxed">
                <span className="text-slate-600 select-none">[{timeStr}]</span>
                <span className={`font-bold select-none min-w-[70px] ${getAgentColor(log.agent_name)}`}>
                  [{log.agent_name}]
                </span>
                <span className="text-slate-300 flex-1 whitespace-pre-wrap">
                  {log.log_message}
                </span>
              </div>
            );
          })
        )}
        <div ref={terminalEndRef} />
      </div>
    </div>
  );
};
