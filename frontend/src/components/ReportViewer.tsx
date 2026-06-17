import React from "react";
import { Download, FileText, CheckCircle, Copy, Check } from "lucide-react";

interface ReportViewerProps {
  report: string | null;
  onExport: (format: string) => void;
  isLoading: boolean;
}

const renderMarkdown = (text: string) => {
  if (!text) return null;
  
  const lines = text.split("\n");
  const renderedElements: React.ReactNode[] = [];
  
  let inCodeBlock = false;
  let codeBlockContent: string[] = [];
  let codeBlockLang = "";
  
  let inTable = false;
  let tableRows: string[][] = [];

  const parseFormatting = (t: string) => {
    // Parse citations like [1], [2] and bold text
    const boldParts = t.split(/\*\*(.*?)\*\*/g);
    return boldParts.map((part, index) => {
      if (index % 2 === 1) {
        return <strong key={index} className="font-bold text-slate-100">{part}</strong>;
      }
      
      // Parse citations [1] inside the regular parts
      const citationParts = part.split(/(\[\d+\])/g);
      return citationParts.map((subPart, subIdx) => {
        if (subPart.match(/^\[\d+\]$/)) {
          return (
            <span 
              key={`cite-${subIdx}`} 
              className="text-xs bg-indigo-950/80 text-indigo-400 border border-indigo-900 px-1 py-0.5 rounded font-bold cursor-help mx-0.5"
              title="Grounding reference source"
            >
              {subPart}
            </span>
          );
        }
        return subPart;
      });
    });
  };

  const renderCurrentTable = (rows: string[][], key: string) => {
    if (rows.length === 0) return null;
    const headerRow = rows[0];
    const dataRows = rows.slice(1).filter(r => !r.every(c => c.trim().startsWith("---") || c.trim() === ""));
    
    return (
      <div key={key} className="my-6 overflow-x-auto rounded-xl border border-slate-800 bg-slate-950/45 shadow-inner">
        <table className="min-w-full divide-y divide-slate-800 text-xs">
          <thead className="bg-slate-900/60 font-semibold text-slate-200">
            <tr>
              {headerRow.map((col, idx) => (
                <th key={idx} className="px-4 py-3 text-left tracking-wider border-r border-slate-800 last:border-r-0">
                  {col.trim()}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800 text-slate-300">
            {dataRows.map((row, rIdx) => (
              <tr key={rIdx} className="hover:bg-slate-900/20">
                {row.map((col, cIdx) => (
                  <td key={cIdx} className="px-4 py-2.5 border-r border-slate-800 last:border-r-0 max-w-xs truncate">
                    {parseFormatting(col.trim())}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  };

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const trimmed = line.trim();
    
    // Code block check
    if (trimmed.startsWith("```")) {
      if (inCodeBlock) {
        inCodeBlock = false;
        const codeText = codeBlockContent.join("\n");
        renderedElements.push(
          <CodeBlockContainer key={`code-${i}`} code={codeText} lang={codeBlockLang} />
        );
        codeBlockContent = [];
        codeBlockLang = "";
      } else {
        inCodeBlock = true;
        codeBlockLang = trimmed.substring(3).trim();
      }
      continue;
    }
    
    if (inCodeBlock) {
      codeBlockContent.push(line);
      continue;
    }

    // Markdown Table check
    if (trimmed.startsWith("|")) {
      inTable = true;
      const cols = line.split("|").map(c => c.trim()).filter((_, idx, arr) => idx > 0 && idx < arr.length - 1);
      tableRows.push(cols);
      continue;
    } else {
      if (inTable) {
        renderedElements.push(renderCurrentTable(tableRows, `table-${i}`));
        tableRows = [];
        inTable = false;
      }
    }
    
    if (!trimmed) continue;
    
    // Headers
    if (trimmed.startsWith("# ")) {
      renderedElements.push(
        <h1 key={i} className="text-2xl font-bold text-slate-100 mt-6 mb-4 border-b border-slate-800 pb-2">
          {parseFormatting(trimmed.substring(2))}
        </h1>
      );
    } else if (trimmed.startsWith("## ")) {
      renderedElements.push(
        <h2 key={i} className="text-xl font-semibold text-indigo-400 mt-5 mb-3">
          {parseFormatting(trimmed.substring(3))}
        </h2>
      );
    } else if (trimmed.startsWith("### ")) {
      renderedElements.push(
        <h3 key={i} className="text-lg font-semibold text-slate-300 mt-4 mb-2">
          {parseFormatting(trimmed.substring(4))}
        </h3>
      );
    } 
    // Unordered lists
    else if (trimmed.startsWith("* ") || trimmed.startsWith("- ")) {
      renderedElements.push(
        <li key={i} className="ml-6 list-disc text-slate-350 mb-1 text-sm leading-relaxed">
          {parseFormatting(trimmed.substring(2))}
        </li>
      );
    } 
    // Blockquotes
    else if (trimmed.startsWith("> ")) {
      renderedElements.push(
        <blockquote key={i} className="border-l-4 border-indigo-500 bg-indigo-950/10 px-4 py-2.5 my-4 rounded-r-lg text-slate-400 italic text-sm">
          {parseFormatting(trimmed.substring(2))}
        </blockquote>
      );
    }
    // Numbered lists
    else {
      const numMatch = trimmed.match(/^(\d+)\.\s(.*)/);
      if (numMatch) {
        renderedElements.push(
          <li key={i} className="ml-6 list-decimal text-slate-350 mb-1 text-sm leading-relaxed">
            {parseFormatting(numMatch[2])}
          </li>
        );
      } else {
        // Standard Paragraph
        renderedElements.push(
          <p key={i} className="text-slate-300 mb-4 leading-relaxed text-sm">
            {parseFormatting(trimmed)}
          </p>
        );
      }
    }
  }
  
  if (inTable && tableRows.length > 0) {
    renderedElements.push(renderCurrentTable(tableRows, "table-eof"));
  }
  
  if (inCodeBlock && codeBlockContent.length > 0) {
    const codeText = codeBlockContent.join("\n");
    renderedElements.push(
      <CodeBlockContainer key="code-eof" code={codeText} lang={codeBlockLang} />
    );
  }
  
  return renderedElements;
};

// Subcomponent for Code Block rendering with copy button
const CodeBlockContainer: React.FC<{ code: string; lang: string }> = ({ code, lang }) => {
  const [copied, setCopied] = React.useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="my-4 rounded-xl overflow-hidden border border-slate-800 bg-slate-950/80 font-mono text-xs text-slate-300 shadow-lg">
      <div className="bg-slate-900 px-4 py-2 border-b border-slate-850 flex justify-between items-center text-[10px] text-slate-500 font-semibold select-none">
        <span>{lang || "code"}</span>
        <button
          onClick={handleCopy}
          className="flex items-center gap-1 hover:text-white transition-colors cursor-pointer text-indigo-400"
        >
          {copied ? (
            <>
              <Check size={11} className="text-emerald-400" />
              <span className="text-emerald-400">Copied</span>
            </>
          ) : (
            <>
              <Copy size={11} />
              <span>Copy code</span>
            </>
          )}
        </button>
      </div>
      <pre className="p-4 overflow-x-auto scrollbar-thin"><code>{code}</code></pre>
    </div>
  );
};

export const ReportViewer: React.FC<ReportViewerProps> = ({
  report,
  onExport,
  isLoading,
}) => {
  if (isLoading) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center py-24 text-slate-400 gap-4">
        <div className="h-10 w-10 border-4 border-t-indigo-500 border-r-indigo-500/20 border-b-indigo-500/20 border-l-indigo-500/20 rounded-full animate-spin"></div>
        <div className="text-center space-y-1">
          <p className="text-sm font-medium animate-pulse text-slate-300">Executing Research Agents...</p>
          <p className="text-[10px] text-slate-500">Retrieving vector embeddings & building bibliography</p>
        </div>
      </div>
    );
  }

  if (!report) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center py-32 text-slate-500 gap-3 select-none">
        <FileText size={42} className="text-slate-800" />
        <p className="text-sm font-medium">Output details will be displayed here.</p>
        <p className="text-[10px] text-slate-600 text-center max-w-[280px]">
          Enter your topic in the input field above and upload any documents to get started.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Export Bar */}
      <div className="flex items-center justify-between p-3 bg-slate-900/40 border border-slate-900 rounded-xl">
        <div className="flex items-center gap-1.5 text-xs text-slate-400 font-semibold pl-2">
          <CheckCircle size={14} className="text-emerald-500" />
          <span>Output Ready</span>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => onExport("pdf")}
            className="flex items-center gap-1.5 px-2.5 py-1.5 bg-slate-850 hover:bg-slate-800 hover:text-white rounded border border-slate-800 text-xs font-semibold text-slate-300 transition-all cursor-pointer"
          >
            <Download size={11} />
            <span>PDF</span>
          </button>
          <button
            onClick={() => onExport("md")}
            className="flex items-center gap-1.5 px-2.5 py-1.5 bg-slate-850 hover:bg-slate-800 hover:text-white rounded border border-slate-800 text-xs font-semibold text-slate-300 transition-all cursor-pointer"
          >
            <Download size={11} />
            <span>Markdown</span>
          </button>
          <button
            onClick={() => onExport("docx")}
            className="flex items-center gap-1.5 px-2.5 py-1.5 bg-slate-850 hover:bg-slate-800 hover:text-white rounded border border-slate-800 text-xs font-semibold text-slate-300 transition-all cursor-pointer"
          >
            <Download size={11} />
            <span>DOCX</span>
          </button>
          <button
            onClick={() => onExport("json")}
            className="flex items-center gap-1.5 px-2.5 py-1.5 bg-slate-850 hover:bg-slate-800 hover:text-white rounded border border-slate-800 text-xs font-semibold text-slate-300 transition-all cursor-pointer"
          >
            <Download size={11} />
            <span>JSON</span>
          </button>
        </div>
      </div>

      {/* Markdown Document Content */}
      <div className="p-8 bg-slate-900/10 border border-slate-900/80 rounded-2xl shadow-xl prose-report max-w-none min-h-[500px]">
        {renderMarkdown(report)}
      </div>
    </div>
  );
};
