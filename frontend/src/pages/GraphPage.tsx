import { useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { Background, Controls, MarkerType, MiniMap, ReactFlow, type Edge, type Node } from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { Network, RefreshCw } from 'lucide-react'
import { DatabaseNotice } from '../components/DatabaseNotice'
import { Alert, Button, Card, EmptyState, LoadingBlock, PageHeader } from '../components/ui'
import { useAsync } from '../hooks/useAsync'
import { api } from '../services/api'
import type { GraphOverview } from '../types/api'

const COLORS = {
  paper: { bg: '#eef2ff', border: '#6366f1' },
  method: { bg: '#ecfdf5', border: '#10b981' },
  dataset: { bg: '#fff7ed', border: '#f97316' },
}

/** Three-column layout: methods | papers | datasets. Simple and readable for small graphs. */
function layout(data: GraphOverview): { nodes: Node[]; edges: Edge[] } {
  const columns = { method: 0, paper: 380, dataset: 760 }
  const rows = { method: 0, paper: 0, dataset: 0 }
  const gap = { method: 64, paper: 110, dataset: 64 }
  const nodes: Node[] = data.nodes.map((n) => {
    const y = rows[n.type]++ * gap[n.type]
    const c = COLORS[n.type]
    return {
      id: n.id,
      position: { x: columns[n.type], y },
      data: { label: n.label },
      style: {
        background: c.bg, border: `1.5px solid ${c.border}`, borderRadius: 10, fontSize: 12,
        width: n.type === 'paper' ? 260 : 180, padding: 8, color: '#0f172a',
        cursor: n.type === 'paper' ? 'pointer' : 'default',
      },
    }
  })
  const edges: Edge[] = data.edges.map((e) =>
    e.type === 'CONTRADICTS'
      ? { id: e.id, source: e.source, target: e.target, label: `conflict ${e.score ?? ''}`, animated: true,
          style: { stroke: '#dc2626', strokeWidth: 2 }, labelStyle: { fill: '#dc2626', fontSize: 11 },
          markerEnd: { type: MarkerType.ArrowClosed, color: '#dc2626' } }
      : { id: e.id, source: e.type === 'USES_METHOD' ? e.target : e.source, target: e.type === 'USES_METHOD' ? e.source : e.target,
          style: { stroke: '#94a3b8' } },
  )
  return { nodes, edges }
}

export default function GraphPage() {
  const navigate = useNavigate()
  const { data, error, loading, reload } = useAsync(() => api.graphOverview(60), [])
  const flow = useMemo(() => (data ? layout(data) : null), [data])

  return (
    <>
      <PageHeader
        title="Knowledge graph"
        description="Papers connected through shared methods and datasets, with detected contradictions between findings. Click a paper to open it."
        actions={<Button variant="secondary" onClick={reload}><RefreshCw className="h-4 w-4" /> Refresh</Button>}
      />
      <div className="space-y-4">
        <DatabaseNotice />
        <Card className="overflow-hidden">
          {loading && !data ? (
            <LoadingBlock label="Loading graph…" />
          ) : error ? (
            <div className="p-5"><Alert tone="error" title="Could not load the graph">{error.message}</Alert></div>
          ) : flow && flow.nodes.length > 0 ? (
            <div className="h-[70vh] min-h-[420px]">
              <ReactFlow
                nodes={flow.nodes}
                edges={flow.edges}
                fitView
                nodesConnectable={false}
                onNodeClick={(_, node) => { if (node.id.startsWith('p_')) navigate(`/papers/${node.id}`) }}
                proOptions={{ hideAttribution: true }}
              >
                <Background gap={20} color="#e2e8f0" />
                <Controls showInteractive={false} />
                <MiniMap pannable zoomable nodeColor={(n) => (n.id.startsWith('p_') ? '#6366f1' : n.id.startsWith('method') ? '#10b981' : '#f97316')} />
              </ReactFlow>
            </div>
          ) : (
            <EmptyState icon={<Network className="h-6 w-6" />} title="The graph is empty" description="Processed papers and their methods and datasets will appear here." />
          )}
        </Card>
        <div className="flex flex-wrap gap-4 text-xs text-slate-600">
          {(['method', 'paper', 'dataset'] as const).map((t) => (
            <span key={t} className="inline-flex items-center gap-1.5">
              <span className="h-3 w-3 rounded" style={{ background: COLORS[t].bg, border: `1.5px solid ${COLORS[t].border}` }} />
              {t[0].toUpperCase() + t.slice(1)}s
            </span>
          ))}
          <span className="inline-flex items-center gap-1.5"><span className="h-0.5 w-5 bg-red-600" /> Contradicting findings</span>
        </div>
      </div>
    </>
  )
}
