import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Check, FolderPlus, Pencil, Trash2, X } from 'lucide-react'
import { Alert, Button, Card, CardHeader, PageHeader, cx } from '../components/ui'
import { useProjects } from '../hooks/ProjectContext'
import { api, toApiError } from '../services/api'
import { formatDate } from '../services/format'
import type { Project } from '../types/api'

const input = 'w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/20'

function ProjectRow({ p, active, onSelect, onChanged }: { p: Project; active: boolean; onSelect: () => void; onChanged: (msg: string | null, err?: string) => void }) {
  const [editing, setEditing] = useState(false)
  const [name, setName] = useState(p.name)
  const [deleting, setDeleting] = useState(false)
  const [confirm, setConfirm] = useState('')
  const [busy, setBusy] = useState(false)

  const save = async () => {
    setBusy(true)
    try { await api.updateProject(p.id, { name }); setEditing(false); onChanged(`Renamed to "${name.trim()}".`) } catch (e) { onChanged(null, toApiError(e).message) } finally { setBusy(false) }
  }
  const remove = async () => {
    setBusy(true)
    try { await api.deleteProject(p.id, confirm); onChanged(`Deleted project "${p.name}" with its papers and saved investigations.`) } catch (e) { onChanged(null, toApiError(e).message) } finally { setBusy(false) }
  }

  return (
    <li className={cx('px-5 py-4', active && 'bg-indigo-50/40')}>
      <div className="flex flex-wrap items-center gap-3">
        <div className="min-w-0 flex-1">
          {editing ? (
            <div className="flex gap-2">
              <input className={input} value={name} maxLength={80} onChange={(e) => setName(e.target.value)} autoFocus />
              <Button onClick={save} disabled={busy || !name.trim()}><Check className="h-4 w-4" /></Button>
              <Button variant="secondary" onClick={() => { setEditing(false); setName(p.name) }}><X className="h-4 w-4" /></Button>
            </div>
          ) : (
            <>
              <p className="font-medium text-slate-900">{p.name}{p.is_default && <span className="ml-2 rounded bg-slate-100 px-1.5 py-0.5 text-[10px] uppercase text-slate-500">default</span>}{active && <span className="ml-2 rounded bg-indigo-100 px-1.5 py-0.5 text-[10px] uppercase text-indigo-700">active</span>}</p>
              <p className="text-xs text-slate-500">{p.paper_count ?? '?'} papers · {p.investigation_count ?? 0} saved investigations · created {formatDate(p.created_at)}</p>
            </>
          )}
        </div>
        {!editing && (
          <div className="flex gap-2">
            {!active && <Button variant="secondary" onClick={onSelect}>Open</Button>}
            <Button variant="ghost" onClick={() => setEditing(true)} title="Rename"><Pencil className="h-4 w-4" /></Button>
            {!p.is_default && <Button variant="danger" onClick={() => setDeleting((v) => !v)} title="Delete"><Trash2 className="h-4 w-4" /></Button>}
          </div>
        )}
      </div>
      {deleting && (
        <div className="mt-3 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-900">
          <p>This permanently deletes the project's knowledge graph, uploaded PDFs and saved investigations. Type <b>{p.name}</b> to confirm.</p>
          <div className="mt-2 flex gap-2">
            <input className={input} value={confirm} onChange={(e) => setConfirm(e.target.value)} placeholder={p.name} />
            <Button variant="danger" onClick={remove} disabled={busy || confirm !== p.name}>Delete project</Button>
          </div>
        </div>
      )}
    </li>
  )
}

export function ProjectsPage() {
  const { projects, activeId, select, refresh } = useProjects()
  const navigate = useNavigate()
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const create = async () => {
    setError(null)
    try {
      const p = await api.createProject(name, description)
      await refresh()
      select(p.id)
      setName(''); setDescription('')
      navigate('/upload')
    } catch (e) { setError(toApiError(e).message) }
  }
  const changed = async (msg: string | null, err?: string) => {
    setMessage(msg); setError(err ?? null)
    await refresh()
  }

  return (
    <>
      <PageHeader title="Projects" description="Each project has its own papers, knowledge graph and saved investigations. Evidence never crosses between projects." />
      <div className="space-y-6">
        {message && <Alert tone="success">{message}</Alert>}
        {error && <Alert tone="error">{error}</Alert>}
        <Alert tone="warning" title="Single-user mode">
          There is no login yet: anyone who can reach this app can see and change every project. Do not expose it publicly.
        </Alert>
        <Card>
          <CardHeader title="New project" />
          <form className="grid gap-3 p-5 sm:grid-cols-[1fr_2fr_auto]" onSubmit={(e) => { e.preventDefault(); void create() }}>
            <input className={input} placeholder="Project name" value={name} maxLength={80} onChange={(e) => setName(e.target.value)} />
            <input className={input} placeholder="Description (optional)" value={description} maxLength={500} onChange={(e) => setDescription(e.target.value)} />
            <Button type="submit" disabled={!name.trim()}><FolderPlus className="h-4 w-4" /> Create</Button>
          </form>
        </Card>
        <Card>
          <CardHeader title={`Your projects (${projects.length})`} />
          <ul className="divide-y divide-slate-100">
            {projects.map((p) => (
              <ProjectRow key={`${p.id}:${p.name}`} p={p} active={p.id === activeId}
                onSelect={() => { select(p.id); navigate('/') }} onChanged={changed} />
            ))}
          </ul>
        </Card>
      </div>
    </>
  )
}
