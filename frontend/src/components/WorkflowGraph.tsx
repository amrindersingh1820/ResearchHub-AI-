import React, { useMemo } from "react";
import { ReactFlow, Background, Position } from "@xyflow/react";
import type { Edge, Node } from "@xyflow/react";
import "@xyflow/react/dist/style.css";

interface WorkflowGraphProps {
  activeAgent: string | null;
  completedAgents: string[];
}

export const WorkflowGraph: React.FC<WorkflowGraphProps> = ({
  activeAgent = null,
  completedAgents = [],
}) => {
  const safeCompletedAgents = completedAgents || [];

  const { nodes, edges } = useMemo(() => {
    const list: Node[] = [];
    const connectionList: Edge[] = [];

    const getNodeState = (nameMatcher: string) => {
      const isCompleted = safeCompletedAgents.some(a => a && a.toLowerCase().includes(nameMatcher.toLowerCase()));
      const isActive = activeAgent ? activeAgent.toLowerCase().includes(nameMatcher.toLowerCase()) : false;
      return { isCompleted, isActive };
    };

    const getEdgeStyle = (isActive: boolean, isCompleted: boolean) => {
      if (isActive) {
        return { stroke: "#f59e0b", strokeWidth: 2.5, animated: true };
      }
      if (isCompleted) {
        return { stroke: "#10b981", strokeWidth: 2 };
      }
      return { stroke: "#475569", strokeWidth: 1.5 };
    };

    const router = getNodeState("router");
    const planner = getNodeState("planner");
    const researcher = getNodeState("researcher");
    const writer = getNodeState("writer");
    const coder = getNodeState("coder");
    const assistant = getNodeState("assistant");
    const memory = getNodeState("memory_context");

    // Helper to assign selection style when active or completed
    const getSelectionClassName = (isActive: boolean, isCompleted: boolean) => {
      if (isActive) return "node-executing selected";
      if (isCompleted) return "node-completed";
      return "";
    };

    // 1. Router Node
    list.push({
      id: "router",
      data: { label: "Router" },
      position: { x: 180, y: 10 },
      className: getSelectionClassName(router.isActive, router.isCompleted),
      sourcePosition: Position.Bottom,
      targetPosition: Position.Top,
    });

    // 2. Research Branch
    list.push({
      id: "planner",
      data: { label: "Planner" },
      position: { x: 10, y: 80 },
      className: getSelectionClassName(planner.isActive, planner.isCompleted),
      sourcePosition: Position.Bottom,
      targetPosition: Position.Top,
    });
    list.push({
      id: "researcher",
      data: { label: "Researcher" },
      position: { x: 10, y: 140 },
      className: getSelectionClassName(researcher.isActive, researcher.isCompleted),
      sourcePosition: Position.Bottom,
      targetPosition: Position.Top,
    });
    list.push({
      id: "writer",
      data: { label: "Writer" },
      position: { x: 10, y: 200 },
      className: getSelectionClassName(writer.isActive, writer.isCompleted),
      sourcePosition: Position.Bottom,
      targetPosition: Position.Top,
    });

    // 3. Code Branch
    list.push({
      id: "coder",
      data: { label: "Coder" },
      position: { x: 130, y: 80 },
      className: getSelectionClassName(coder.isActive, coder.isCompleted),
      sourcePosition: Position.Bottom,
      targetPosition: Position.Top,
    });

    // 4. Assistant Branch
    list.push({
      id: "assistant",
      data: { label: "Assistant" },
      position: { x: 250, y: 80 },
      className: getSelectionClassName(assistant.isActive, assistant.isCompleted),
      sourcePosition: Position.Bottom,
      targetPosition: Position.Top,
    });

    // 5. Memory Context / Follow-Up Branch
    list.push({
      id: "memory_context",
      data: { label: "Memory Context" },
      position: { x: 370, y: 80 },
      className: getSelectionClassName(memory.isActive, memory.isCompleted),
      sourcePosition: Position.Bottom,
      targetPosition: Position.Top,
    });

    // Connections from Router
    connectionList.push({
      id: "e-router-planner",
      source: "router",
      target: "planner",
      ...getEdgeStyle(planner.isActive || researcher.isActive || writer.isActive, planner.isCompleted || safeCompletedAgents.some(a => a && a.toLowerCase().includes("planner"))),
    });
    connectionList.push({
      id: "e-router-coder",
      source: "router",
      target: "coder",
      ...getEdgeStyle(coder.isActive, coder.isCompleted),
    });
    connectionList.push({
      id: "e-router-assistant",
      source: "router",
      target: "assistant",
      ...getEdgeStyle(assistant.isActive, assistant.isCompleted),
    });
    connectionList.push({
      id: "e-router-memory",
      source: "router",
      target: "memory_context",
      ...getEdgeStyle(memory.isActive, memory.isCompleted),
    });

    // Research branch inner connections
    connectionList.push({
      id: "e-planner-researcher",
      source: "planner",
      target: "researcher",
      ...getEdgeStyle(researcher.isActive, planner.isCompleted),
    });
    connectionList.push({
      id: "e-researcher-writer",
      source: "researcher",
      target: "writer",
      ...getEdgeStyle(writer.isActive, researcher.isCompleted),
    });

    return { nodes: list, edges: connectionList };
  }, [activeAgent, safeCompletedAgents]);

  return (
    <div className="h-[280px] w-full bg-slate-950/20 border border-slate-900 rounded-lg overflow-hidden relative">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        fitView
        fitViewOptions={{ padding: 0.15 }}
        nodesConnectable={false}
        nodesDraggable={false}
        zoomOnScroll={false}
        zoomOnPinch={false}
        panOnDrag={false}
        preventScrolling={true}
      >
        <Background color="#1e293b" gap={12} size={1} />
      </ReactFlow>
    </div>
  );
};
