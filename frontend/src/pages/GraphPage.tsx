import { useEffect, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { Background, Controls, MiniMap, Position, ReactFlow, useNodesState, type Edge, type Node } from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { Network, RefreshCw } from 'lucide-react'
import { DatabaseNotice } from '../components/DatabaseNotice'
import { Alert, Button, Card, EmptyState, LoadingBlock, PageHeader } from '../components/ui'
import { useAsync } from '../hooks/useAsync'
import { usePageMeta } from '../hooks/usePageMeta'
import { useI18n } from '../i18n/I18nProvider'
import { api } from '../services/api'
import { errorText } from '../services/errors'
import { useTheme } from '../theme/ThemeProvider'
import type { GraphOverview } from '../types/api'

type Kind = 'paper' | 'method' | 'dataset'

function palette(dark: boolean): Record<Kind, { bg: string; border: string; fg: string }> {
  return dark
    ? { paper: { bg: '#0d2342', border: '#2f7ff0', fg: '#f2f4f7' }, method: { bg: '#15181d', border: '#e6e9ee', fg: '#f2f4f7' }, dataset: { bg: '#15181d', border: '#7d8696', fg: '#c9ced8' } }
    : { paper: { bg: '#e8f0fc', border: '#1c69d4', fg: '#0b0d11' }, method: { bg: '#ffffff', border: '#0b0d11', fg: '#0b0d11' }, dataset: { bg: '#f4f5f7', border: '#7b8494', fg: '#4b5361' } }
}

/**
 * One cluster per paper: its methods on the left, the paper in the middle, its datasets on the right.
 * Papers never share nodes or edges (every paper's knowledge graph is separate), so clusters do not connect.
 */
function layout(data: GraphOverview, dark: boolean): { nodes: Node[]; edges: Edge[] } {
  const colors = palette(dark)
  const byId = new Map(data.nodes.map((n) => [n.id, n]))
  const children = new Map<string, { methods: string[]; datasets: string[] }>()
  for (const e of data.edges) {
    const entry = children.get(e.source) ?? { methods: [], datasets: [] }
    if (byId.get(e.target)?.type === 'method') entry.methods.push(e.target)
    else entry.datasets.push(e.target)
    children.set(e.source, entry)
  }
  const ROW = 56
  const nodes: Node[] = []
  let y = 0
  const style = (kind: Kind, width: number) => ({
    background: colors[kind].bg, border: `1.5px solid ${colors[kind].border}`, color: colors[kind].fg, borderRadius: 10,
    fontSize: 12, width, padding: 8, cursor: kind === 'paper' ? 'pointer' : 'default', boxShadow: kind === 'paper' ? '0 4px 14px -6px rgba(28,105,212,.45)' : 'none',
  })
  for (const paper of data.nodes.filter((n) => n.type === 'paper')) {
    const kids = children.get(paper.id) ?? { methods: [], datasets: [] }
    const rows = Math.max(1, kids.methods.length, kids.datasets.length)
    const height = rows * ROW
    // Left-to-right: methods -> paper -> datasets, so edges connect side to side.
    nodes.push({ id: paper.id, position: { x: 340, y: y + height / 2 - 24 }, data: { label: paper.label }, style: style('paper', 260),
      sourcePosition: Position.Right, targetPosition: Position.Left })
    kids.methods.forEach((id, i) => nodes.push({ id, position: { x: 0, y: y + i * ROW + (height - kids.methods.length * ROW) / 2 },
      data: { label: byId.get(id)?.label }, style: style('method', 200), sourcePosition: Position.Right, targetPosition: Position.Left }))
    kids.datasets.forEach((id, i) => nodes.push({ id, position: { x: 720, y: y + i * ROW + (height - kids.datasets.length * ROW) / 2 },
      data: { label: byId.get(id)?.label }, style: style('dataset', 200), sourcePosition: Position.Right, targetPosition: Position.Left }))
    y += height + 72
  }
  const edgeColor = dark ? '#3a404c' : '#cdd2da'
  const edges: Edge[] = data.edges.map((e) => {
    const method = byId.get(e.target)?.type === 'method'
    return { id: e.id, source: method ? e.target : e.source, target: method ? e.source : e.target, style: { stroke: edgeColor, strokeWidth: 1.5 } }
  })
  return { nodes, edges }
}

const isPaper = (id: string) => id.startsWith('p_') && !id.includes(':')

/**
 * The canvas keeps its own node state so React Flow can record each node's measured size
 * (the minimap and fitView need it); the layout is replaced whenever the data or theme changes.
 */
function GraphCanvas({ flow, dark }: { flow: { nodes: Node[]; edges: Edge[] }; dark: boolean }) {
  const navigate = useNavigate()
  const colors = palette(dark)
  const [nodes, setNodes, onNodesChange] = useNodesState(flow.nodes)
  useEffect(() => setNodes(flow.nodes), [flow, setNodes])
  return (
    <ReactFlow
      nodes={nodes}
      edges={flow.edges}
      onNodesChange={onNodesChange}
      fitView
      colorMode={dark ? 'dark' : 'light'}
      nodesConnectable={false}
      onNodeClick={(_, node) => { if (isPaper(node.id)) navigate(`/papers/${node.id}`) }}
      proOptions={{ hideAttribution: true }}
    >
      <Background gap={22} color={dark ? '#1c2027' : '#e3e6eb'} />
      <Controls showInteractive={false} />
      <MiniMap pannable zoomable nodeColor={(n) => (isPaper(n.id) ? colors.paper.border : n.id.startsWith('method') ? colors.method.border : colors.dataset.border)} />
    </ReactFlow>
  )
}

export default function GraphPage() {
  const { t } = useI18n()
  usePageMeta(t('graph.title'), undefined, { noindex: true })
  const { resolved } = useTheme()
  const { data, error, loading, reload } = useAsync(() => api.graphOverview(60), [])
  const dark = resolved === 'dark'
  const flow = useMemo(() => (data ? layout(data, dark) : null), [data, dark])
  const colors = palette(dark)

  return (
    <>
      <PageHeader title={t('graph.title')} description={t('graph.description')}
        actions={<Button variant="secondary" onClick={reload}><RefreshCw className="h-4 w-4" /> {t('common.refresh')}</Button>} />
      <div className="space-y-4">
        <DatabaseNotice />
        <Card className="overflow-hidden">
          {loading && !data ? (
            <LoadingBlock rows={6} />
          ) : error ? (
            <div className="p-5"><Alert tone="error" title={t('graph.loadFailed')}>{errorText(t, error)}</Alert></div>
          ) : flow && flow.nodes.length > 0 ? (
            <div className="h-[70vh] min-h-[420px]" dir="ltr">
              <GraphCanvas flow={flow} dark={dark} />
            </div>
          ) : (
            <EmptyState icon={<Network className="h-6 w-6" />} title={t('graph.empty.title')} description={t('graph.empty.text')} />
          )}
        </Card>
        <div className="flex flex-wrap gap-4 text-xs text-fg-muted">
          {(['method', 'paper', 'dataset'] as const).map((k) => (
            <span key={k} className="inline-flex items-center gap-1.5">
              <span className="h-3 w-3 rounded" style={{ background: colors[k].bg, border: `1.5px solid ${colors[k].border}` }} />
              {t(`graph.legend.${k}`)}
            </span>
          ))}
          <span className="text-fg-subtle">{t('graph.isolation')}</span>
        </div>
      </div>
    </>
  )
}
