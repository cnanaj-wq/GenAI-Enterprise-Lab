import { Edge, Node, ReactFlow, Background, Controls, MiniMap } from "@xyflow/react";
import { GitBranch } from "@phosphor-icons/react";
import { Card, CardHeader } from "@/components/ui/Card";

export function AgentGraphPanel({ nodes, edges }: { nodes: Node[]; edges: Edge[] }) {
  return (
    <Card as="section" aria-label="Live agent graph" className="overflow-hidden">
      <CardHeader
        title="Live Agent Graph"
        description="NODE (LangGraph) spans orchestrate their TOOL / DATABASE / LLM / EVALUATION children."
        icon={<GitBranch size={18} weight="bold" />}
      />

      <div className="h-[420px] sm:h-[560px] xl:h-[720px]">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          fitView
          fitViewOptions={{ padding: 0.18 }}
        >
          <Background color="var(--color-border-subtle)" gap={20} />
          <Controls className="!rounded-[var(--radius-sm)] !border !border-[var(--color-border)] !bg-[var(--color-surface-raised)] !shadow-[var(--shadow-md)] [&_button]:!border-[var(--color-border)] [&_button]:!bg-transparent [&_button]:!fill-[var(--color-text-secondary)] [&_button:hover]:!bg-[var(--color-surface-hover)]" />
          <MiniMap
            pannable
            zoomable
            className="!rounded-[var(--radius-sm)] !border !border-[var(--color-border)] !bg-[var(--color-surface-raised)]"
            maskColor="rgba(5, 7, 13, 0.7)"
          />
        </ReactFlow>
      </div>
    </Card>
  );
}
