import React, { useState } from "react";
import { Clock, ChevronRight, CheckCircle, Database, Trash2, Edit2, Search, ArrowUpDown, AlertTriangle } from "lucide-react";

interface HistoryItem {
  id: string;
  query: string;
  created_at: string;
  completed: boolean;
  message_count?: number;
}

interface HistorySidebarProps {
  history: HistoryItem[];
  activeSessionId: string | null;
  onSelectSession: (id: string) => void;
  onNewSession: () => void;
  onRenameSession: (id: string, newTitle: string) => Promise<void>;
  onDeleteSession: (id: string) => Promise<void>;
}

export const HistorySidebar: React.FC<HistorySidebarProps> = ({
  history,
  activeSessionId,
  onSelectSession,
  onNewSession,
  onRenameSession,
  onDeleteSession,
}) => {
  const [searchQuery, setSearchQuery] = useState("");
  const [sortBy, setSortBy] = useState<"newest" | "oldest" | "active">("newest");
  
  const safeHistory = history || [];

  // State for renaming a thread
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState("");

  // State for confirmation modal
  const [deleteConfirmId, setDeleteConfirmId] = useState<string | null>(null);

  const handleStartEdit = (e: React.MouseEvent, item: HistoryItem) => {
    e.stopPropagation();
    setEditingId(item.id);
    setEditTitle(item.query);
  };

  const handleSaveRename = async (e: React.FormEvent, id: string) => {
    e.preventDefault();
    if (editTitle.trim() && editTitle !== safeHistory.find(h => h && h.id === id)?.query) {
      await onRenameSession(id, editTitle.trim());
    }
    setEditingId(null);
  };

  const handleDelete = (e: React.MouseEvent, id: string) => {
    e.preventDefault();
    e.stopPropagation();
    setDeleteConfirmId(id);
  };

  const deleteConfirmItem = safeHistory.find(h => h && h.id === deleteConfirmId);

  // Filter and sort conversation threads
  const filteredHistory = safeHistory
    .filter((item) =>
      item && item.query && item.query.toLowerCase().includes(searchQuery.toLowerCase())
    )
    .sort((a, b) => {
      if (!a || !b) return 0;
      if (sortBy === "oldest") {
        return new Date(a.created_at).getTime() - new Date(b.created_at).getTime();
      }
      if (sortBy === "active") {
        return (b.message_count || 0) - (a.message_count || 0);
      }
      // Default: newest
      return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
    });

  return (
    <div className="w-80 h-full border-r border-slate-800 bg-slate-900/30 flex flex-col select-none">
      {/* Title & New Run Button */}
      <div className="p-4 border-b border-slate-800 flex justify-between items-center bg-slate-950/20">
        <div className="flex items-center gap-2 text-indigo-400 font-bold text-lg">
          <Database size={20} />
          <span className="tracking-tight text-white">Research Hub</span>
        </div>
        <button
          onClick={onNewSession}
          className="px-3 py-1.5 bg-indigo-650 hover:bg-indigo-600 active:bg-indigo-750 text-white rounded text-xs font-semibold shadow transition-all cursor-pointer"
        >
          + New Chat
        </button>
      </div>

      {/* Filter and Sort controls */}
      <div className="p-3 border-b border-slate-850 space-y-2">
        {/* Search */}
        <div className="relative">
          <Search size={13} className="absolute left-2.5 top-2.5 text-slate-500" />
          <input
            type="text"
            placeholder="Search conversations..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-8 pr-3 py-1.5 bg-slate-950/60 border border-slate-850 rounded text-xs text-slate-350 focus:outline-none focus:border-indigo-500 transition-colors"
          />
        </div>

        {/* Sort selector */}
        <div className="flex items-center justify-between text-[10px] text-slate-400">
          <span className="flex items-center gap-1 font-semibold text-slate-500">
            <ArrowUpDown size={10} />
            SORT BY
          </span>
          <div className="flex gap-2 font-medium">
            <button
              onClick={() => setSortBy("newest")}
              className={`hover:text-slate-200 transition-colors ${sortBy === "newest" ? "text-indigo-400 font-bold" : ""}`}
            >
              Newest
            </button>
            <button
              onClick={() => setSortBy("oldest")}
              className={`hover:text-slate-200 transition-colors ${sortBy === "oldest" ? "text-indigo-400 font-bold" : ""}`}
            >
              Oldest
            </button>
            <button
              onClick={() => setSortBy("active")}
              className={`hover:text-slate-200 transition-colors ${sortBy === "active" ? "text-indigo-400 font-bold" : ""}`}
            >
              Active
            </button>
          </div>
        </div>
      </div>

      {/* Threads List */}
      <div className="flex-1 overflow-y-auto p-3 space-y-2 scrollbar-thin">
        <h3 className="text-slate-500 text-[10px] font-bold tracking-wider uppercase px-2 mb-2">
          Conversations
        </h3>
        
        {filteredHistory.length === 0 ? (
          <div className="text-center text-slate-500 py-8 text-xs px-2 italic">
            No research sessions found.
          </div>
        ) : (
          filteredHistory.map((item) => {
            const isActive = activeSessionId === item.id;
            const dateStr = new Date(item.created_at).toLocaleDateString();
            
            return (
              <div
                key={item.id}
                onClick={() => onSelectSession(item.id)}
                className={`w-full group relative text-left p-3 rounded-lg flex items-start gap-3 transition-all cursor-pointer border ${
                  isActive
                    ? "bg-indigo-950/20 border-indigo-500/30 text-indigo-200 shadow"
                    : "bg-slate-900/40 hover:bg-slate-800/40 border-transparent text-slate-350"
                }`}
              >
                {/* Status indicator */}
                <div className="mt-1 flex-shrink-0">
                  {item.completed ? (
                    <CheckCircle size={14} className="text-emerald-500" />
                  ) : (
                    <Clock size={14} className="text-amber-500" />
                  )}
                </div>
                
                {/* Title and date */}
                <div className="flex-1 min-w-0 pr-8">
                  {editingId === item.id ? (
                    <form onSubmit={(e) => handleSaveRename(e, item.id)} className="w-full">
                      <input
                        type="text"
                        value={editTitle}
                        onChange={(e) => setEditTitle(e.target.value)}
                        onBlur={(e) => handleSaveRename(e, item.id)}
                        autoFocus
                        className="w-full bg-slate-950 border border-indigo-500 px-1 py-0.5 rounded text-xs text-white focus:outline-none"
                      />
                    </form>
                  ) : (
                    <>
                      <p className="font-semibold text-xs truncate leading-normal">
                        {item.query}
                      </p>
                      <span className="text-[9px] text-slate-500 block mt-1">
                        {dateStr} • {item.message_count || 1} msg
                      </span>
                    </>
                  )}
                </div>
                
                {/* Operations buttons (visible on hover) */}
                {editingId !== item.id && (
                  <div className="absolute right-2.5 top-3 flex gap-1.5 opacity-0 group-hover:opacity-100 transition-opacity bg-transparent">
                    <button
                      onClick={(e) => handleStartEdit(e, item)}
                      className="p-1 hover:bg-slate-800 rounded text-slate-400 hover:text-white transition-colors"
                      title="Rename Thread"
                    >
                      <Edit2 size={11} />
                    </button>
                    <button
                      onClick={(e) => handleDelete(e, item.id)}
                      className="p-1 hover:bg-red-950 rounded text-slate-400 hover:text-red-400 transition-colors"
                      title="Delete Thread"
                    >
                      <Trash2 size={11} />
                    </button>
                  </div>
                )}
                
                {editingId !== item.id && (
                  <ChevronRight
                    size={12}
                    className={`mt-1.5 transition-transform flex-shrink-0 group-hover:opacity-0 ${
                      isActive ? "translate-x-0.5 text-indigo-400" : "text-slate-650"
                    }`}
                  />
                )}
              </div>
            );
          })
        )}
      </div>

      {/* Delete Confirmation Modal Overlay */}
      {deleteConfirmId && deleteConfirmItem && (
        <div 
          className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-slate-950/75 backdrop-blur-xs animate-in fade-in duration-200"
          onClick={() => setDeleteConfirmId(null)}
        >
          <div 
            className="bg-slate-900 border border-slate-800/80 rounded-2xl max-w-sm w-full p-6 shadow-2xl space-y-5 transform scale-100 transition-all duration-200 animate-in zoom-in-95"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center gap-3 border-b border-slate-800/60 pb-3">
              <div className="p-2 bg-red-500/10 rounded-lg text-red-400">
                <AlertTriangle size={18} />
              </div>
              <h3 className="text-sm font-bold text-white">Delete Thread</h3>
            </div>

            <div className="space-y-2">
              <p className="text-xs text-slate-400 leading-relaxed">
                Are you sure you want to permanently delete this research thread?
              </p>
              <p className="text-xs font-mono font-bold bg-slate-950/60 p-3 rounded-lg border border-slate-850 text-slate-200 break-words leading-normal max-h-[80px] overflow-y-auto scrollbar-thin select-text">
                {deleteConfirmItem.query}
              </p>
              <p className="text-[10px] text-red-400/80 font-medium">
                This will erase all logs, reports, and citations associated with it.
              </p>
            </div>

            <div className="flex justify-end gap-2 pt-2 border-t border-slate-800/40">
              <button
                type="button"
                onClick={() => setDeleteConfirmId(null)}
                className="px-3 py-2 bg-slate-800 hover:bg-slate-750 text-slate-300 hover:text-white rounded-lg text-xs font-semibold transition-colors cursor-pointer select-none"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={async () => {
                  const id = deleteConfirmId;
                  setDeleteConfirmId(null);
                  await onDeleteSession(id);
                }}
                className="px-3 py-2 bg-red-650 hover:bg-red-600 text-white rounded-lg text-xs font-semibold shadow-md transition-colors cursor-pointer select-none"
              >
                Delete
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
