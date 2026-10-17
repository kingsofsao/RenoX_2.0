import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Check, FolderPlus, Lock, Pencil, Trash2, X } from 'lucide-react'
import { Alert, Badge, Button, Card, CardHeader, Input, PageHeader, cx } from '../components/ui'
import { useProjects } from '../hooks/ProjectContext'
import { useI18n } from '../i18n/I18nProvider'
import { api } from '../services/api'
import { errorText } from '../services/errors'
import type { Project } from '../types/api'

function ProjectRow({ p, active, canDelete, onSelect, onChanged }: {
  p: Project; active: boolean; canDelete: boolean; onSelect: () => void; onChanged: (msg: string | null, err?: string) => void
}) {
  const { t, tn, formatDate } = useI18n()
  const [editing, setEditing] = useState(false)
  const [name, setName] = useState(p.name)
  const [deleting, setDeleting] = useState(false)
  const [confirm, setConfirm] = useState('')
  const [busy, setBusy] = useState(false)

  const save = async () => {
    setBusy(true)
    try { await api.updateProject(p.id, { name }); setEditing(false); onChanged(t('projects.renamed', { name: name.trim() })) }
    catch (e) { onChanged(null, errorText(t, e)) } finally { setBusy(false) }
  }
  const remove = async () => {
    setBusy(true)
    try { await api.deleteProject(p.id, confirm); onChanged(t('projects.deleted', { name: p.name })) }
    catch (e) { onChanged(null, errorText(t, e)) } finally { setBusy(false) }
  }

  return (
    <li className={cx('px-5 py-4 transition-colors', active && 'bg-brand-soft/40')}>
      <div className="flex flex-wrap items-center gap-3">
        <div className="min-w-0 flex-1">
          {editing ? (
            <form className="flex gap-2" onSubmit={(e) => { e.preventDefault(); void save() }}>
              <Input value={name} maxLength={80} onChange={(e) => setName(e.target.value)} autoFocus aria-label={t('projects.name')} />
              <Button type="submit" loading={busy} disabled={!name.trim()} aria-label={t('common.save')}><Check className="h-4 w-4" /></Button>
              <Button variant="secondary" onClick={() => { setEditing(false); setName(p.name) }} aria-label={t('common.cancel')}><X className="h-4 w-4" /></Button>
            </form>
          ) : (
            <>
              <p className="flex flex-wrap items-center gap-2 font-medium text-fg">{p.name}{active && <Badge tone="brand">{t('projects.active')}</Badge>}</p>
              {p.description && <p className="mt-0.5 text-sm text-fg-muted">{p.description}</p>}
              <p className="mt-0.5 text-xs text-fg-subtle">
                {p.paper_count != null ? tn('library.papers', p.paper_count) : '—'} · {tn('projects.investigations', p.investigation_count ?? 0)} · {t('projects.created', { date: formatDate(p.created_at, { dateStyle: 'medium' }) })}
              </p>
            </>
          )}
        </div>
        {!editing && (
          <div className="flex gap-2">
            {!active && <Button variant="secondary" size="sm" onClick={onSelect}>{t('projects.open')}</Button>}
            <Button variant="ghost" size="sm" onClick={() => setEditing(true)} title={t('projects.rename')} aria-label={t('projects.rename')}><Pencil className="h-4 w-4" /></Button>
            {canDelete && <Button variant="danger" size="sm" onClick={() => setDeleting((v) => !v)} title={t('common.delete')} aria-label={t('common.delete')}><Trash2 className="h-4 w-4" /></Button>}
          </div>
        )}
      </div>
      {deleting && (
        <div className="mt-3 animate-fade-up rounded-lg border border-bad/25 bg-bad-soft p-3 text-sm text-bad-fg">
          <p>{t('projects.delete.warning', { name: p.name })}</p>
          <div className="mt-2 flex gap-2">
            <Input value={confirm} onChange={(e) => setConfirm(e.target.value)} placeholder={p.name} aria-label={t('projects.delete.type')} />
            <Button variant="danger" onClick={() => void remove()} loading={busy} disabled={confirm !== p.name}>{t('projects.delete')}</Button>
          </div>
        </div>
      )}
    </li>
  )
}

export function ProjectsPage() {
  const { t } = useI18n()
  const { projects, activeId, select, refresh } = useProjects()
  const navigate = useNavigate()
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const create = async () => {
    setError(null); setBusy(true)
    try {
      const p = await api.createProject(name, description)
      await refresh()
      select(p.id)
      setName(''); setDescription('')
      navigate('/upload')
    } catch (e) { setError(errorText(t, e)) } finally { setBusy(false) }
  }
  const changed = async (msg: string | null, err?: string) => {
    setMessage(msg); setError(err ?? null)
    await refresh()
  }

  return (
    <>
      <PageHeader title={t('projects.title')} description={t('projects.description')} />
      <div className="space-y-6">
        {message && <Alert tone="success">{message}</Alert>}
        {error && <Alert tone="error">{error}</Alert>}
        <p className="flex items-center gap-2 text-xs text-fg-subtle"><Lock className="h-3.5 w-3.5 text-ok" />{t('projects.private')}</p>
        <Card>
          <CardHeader title={t('projects.new')} />
          <form className="grid gap-3 p-5 sm:grid-cols-[1fr_2fr_auto]" onSubmit={(e) => { e.preventDefault(); void create() }}>
            <Input placeholder={t('projects.name')} aria-label={t('projects.name')} value={name} maxLength={80} onChange={(e) => setName(e.target.value)} />
            <Input placeholder={t('projects.descriptionField')} aria-label={t('projects.descriptionField')} value={description} maxLength={500} onChange={(e) => setDescription(e.target.value)} />
            <Button type="submit" loading={busy} disabled={!name.trim()}><FolderPlus className="h-4 w-4" /> {t('projects.create')}</Button>
          </form>
        </Card>
        <Card>
          <CardHeader title={t('projects.yours', { count: projects.length })} />
          <ul className="divide-y divide-line">
            {projects.map((p) => (
              <ProjectRow key={`${p.id}:${p.name}`} p={p} active={p.id === activeId} canDelete={projects.length > 1}
                onSelect={() => { select(p.id); navigate('/') }} onChanged={changed} />
            ))}
          </ul>
        </Card>
      </div>
    </>
  )
}
