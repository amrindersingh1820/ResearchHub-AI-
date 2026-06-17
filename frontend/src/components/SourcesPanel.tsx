import React from "react";
import { FileText, Globe, Database, ExternalLink } from "lucide-react";

interface Source {
  name: string;
  type: string;
  url_or_path?: string;
  snippet?: string;
}

interface SourcesPanelProps {
  sources: Source[];
  retrievedChunks: string[];
}

export const SourcesPanel: React.FC<SourcesPanelProps> = ({
  sources = [],
  retrievedChunks = [],
}) => {
  const safeSources = sources || [];
  const safeChunks = retrievedChunks || [];

  // Separate sources by type
  const docSources = safeSources.filter(s => s && (s.type === "pdf" || s.type === "txt" || s.type === "csv"));
  const webSources = safeSources.filter(s => s && s.type === "web");

  return (
    <div className="w-full bg-slate-900/10 border border-slate-900/60 rounded-xl p-5 space-y-6 overflow-y-auto max-h-[600px] scrollbar-thin">
      <div>
        <h3 className="text-sm font-bold text-slate-200 uppercase tracking-wider border-b border-slate-800 pb-2 flex items-center gap-2">
          <Database size={16} className="text-indigo-400" />
          <span>Knowledge & Sources</span>
        </h3>
      </div>

      {/* 1. Documents Used */}
      <div className="space-y-2">
        <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
          <FileText size={13} className="text-slate-500" />
          <span>Documents Grounded ({docSources.length})</span>
        </h4>
        {docSources.length === 0 ? (
          <div className="text-[11px] text-slate-600 italic pl-1">No uploaded files used.</div>
        ) : (
          <div className="space-y-1.5">
            {docSources.map((src, idx) => (
              <div key={idx} className="p-2 bg-slate-950/30 border border-slate-900 rounded flex items-center justify-between text-xs">
                <span className="text-slate-300 truncate font-mono max-w-[170px]">{src.name}</span>
                <span className="text-[9px] uppercase font-bold text-indigo-400 bg-indigo-950/40 px-1 py-0.5 rounded">
                  {src.type}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* 2. Web References */}
      <div className="space-y-2">
        <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
          <Globe size={13} className="text-slate-500" />
          <span>Web Citations ({webSources.length})</span>
        </h4>
        {webSources.length === 0 ? (
          <div className="text-[11px] text-slate-600 italic pl-1">No web search sources compiled.</div>
        ) : (
          <div className="space-y-2">
            {webSources.map((src, idx) => (
              <div key={idx} className="p-2.5 bg-slate-950/40 border border-slate-900 rounded space-y-1">
                <div className="flex items-start justify-between gap-1.5">
                  <h5 className="font-semibold text-xs text-slate-200 leading-tight truncate flex-1">
                    {src.name}
                  </h5>
                  {src.url_or_path && (
                    <a
                      href={src.url_or_path}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-indigo-400 hover:text-indigo-300"
                    >
                      <ExternalLink size={11} />
                    </a>
                  )}
                </div>
                {src.snippet && (
                  <p className="text-[10px] text-slate-500 italic line-clamp-2 leading-relaxed">
                    "{src.snippet}"
                  </p>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* 3. Retrieved Vector Segments */}
      <div className="space-y-2">
        <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
          <Database size={13} className="text-slate-500" />
          <span>Retrieved Vector Chunks ({safeChunks.length})</span>
        </h4>
        {safeChunks.length === 0 ? (
          <div className="text-[11px] text-slate-600 italic pl-1">No vector chunks indexed in this step.</div>
        ) : (
          <div className="space-y-2">
            {safeChunks.map((chunk, idx) => (
              <div key={idx} className="p-2.5 bg-indigo-950/5 border border-indigo-900/10 rounded">
                <p className="text-[10px] text-slate-400 leading-relaxed font-mono line-clamp-3 select-none">
                  {chunk ? chunk.replace(/\[Source: PDF.*?\]/g, "") : ""}
                </p>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
