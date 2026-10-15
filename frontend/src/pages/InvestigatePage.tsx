import { FlaskConical, GitCompare, Network, Quote, Search, Telescope } from 'lucide-react'
import { Alert, Card, CardHeader, PageHeader } from '../components/ui'

const PLANNED = [
  { icon: <Search className="h-4 w-4" />, title: 'Evidence retrieval', text: 'Semantic + keyword search over page-level evidence passages.' },
  { icon: <Network className="h-4 w-4" />, title: 'Multi-hop graph traversal', text: 'Follow methods and datasets across papers to connected results.' },
  { icon: <GitCompare className="h-4 w-4" />, title: 'Claim comparison', text: 'Surface agreements and contradictions between papers.' },
  { icon: <Telescope className="h-4 w-4" />, title: 'Candidate research gaps', text: 'Evidence-backed hypotheses — candidates to verify, not guaranteed novel findings.' },
  { icon: <Quote className="h-4 w-4" />, title: 'Cited reports', text: 'Every statement linked to the paper and page it came from.' },
]

/** Placeholder for the upcoming AI-agent integration. Nothing here calls an API yet. */
export function InvestigatePage() {
  return (
    <>
      <PageHeader title="Investigate" description="Ask research questions answered from your papers through graph tools — not a generic chatbot." />
      <div className="space-y-6">
        <Alert tone="info" title="Coming in the next phase">
          The investigation agent is not connected to this interface yet. Upload papers now so the knowledge graph is ready when it is.
        </Alert>
        <Card>
          <CardHeader title="Research question" subtitle="Preview of the upcoming workflow" />
          <div className="space-y-3 p-5">
            <textarea disabled rows={3} placeholder="e.g. Do graph attention models generalize to unseen proteins in drug-target prediction?"
              className="w-full cursor-not-allowed resize-none rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm text-slate-500" />
            <button disabled className="inline-flex cursor-not-allowed items-center gap-2 rounded-lg bg-indigo-300 px-3.5 py-2 text-sm font-medium text-white">
              <FlaskConical className="h-4 w-4" /> Run investigation (not available yet)
            </button>
          </div>
        </Card>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {PLANNED.map((p) => (
            <Card key={p.title} className="p-5">
              <div className="mb-2 inline-flex rounded-lg bg-indigo-50 p-2 text-indigo-600">{p.icon}</div>
              <p className="font-medium text-slate-900">{p.title}</p>
              <p className="mt-1 text-sm text-slate-500">{p.text}</p>
            </Card>
          ))}
        </div>
      </div>
    </>
  )
}
