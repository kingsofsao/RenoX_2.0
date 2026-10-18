import { useEffect, useState } from 'react'
import { SITE } from '../config/site'
import { usePageMeta } from '../hooks/usePageMeta'
import { useI18n } from '../i18n/I18nProvider'
import type { LangCode } from '../i18n/languages'
import en from '../i18n/legal/en'
import type { LegalTexts } from '../i18n/legal/types'

const loaders: Record<Exclude<LangCode, 'en'>, () => Promise<{ default: LegalTexts }>> = {
  es: () => import('../i18n/legal/es'),
  fr: () => import('../i18n/legal/fr'),
  de: () => import('../i18n/legal/de'),
  hi: () => import('../i18n/legal/hi'),
  ta: () => import('../i18n/legal/ta'),
  zh: () => import('../i18n/legal/zh'),
  ja: () => import('../i18n/legal/ja'),
  ar: () => import('../i18n/legal/ar'),
}

function useLegalTexts(lang: LangCode): LegalTexts {
  const [texts, setTexts] = useState<LegalTexts>(en)
  useEffect(() => {
    let cancelled = false
    if (lang === 'en') setTexts(en)
    else loaders[lang]().then((m) => { if (!cancelled) setTexts(m.default) }).catch(() => { if (!cancelled) setTexts(en) })
    return () => { cancelled = true }
  }, [lang])
  return texts
}

export default function LegalPage({ doc }: { doc: 'privacy' | 'terms' }) {
  const { lang, formatDate } = useI18n()
  const texts = useLegalTexts(lang)
  const page = texts[doc]
  usePageMeta(page.title, page.description)

  const contact = SITE.contactEmail ? texts.contactEmail.replace('{email}', SITE.contactEmail) : texts.contactForm
  const fill = (s: string) => s.replaceAll('{operator}', SITE.operator).replaceAll('{contact}', contact)

  // Jump to #section links (for example /privacy#cookies from the cookie banner) once the text is in place.
  useEffect(() => {
    const id = decodeURIComponent(window.location.hash.slice(1))
    if (id) requestAnimationFrame(() => document.getElementById(id)?.scrollIntoView())
  }, [page])

  return (
    <article className="mx-auto max-w-3xl px-4 py-14 sm:px-6 lg:py-20">
      <header className="border-b border-line pb-8">
        <h1 className="text-3xl font-semibold tracking-tight text-fg sm:text-4xl">{page.title}</h1>
        <p className="mt-3 text-sm text-fg-subtle">
          <time dateTime={SITE.legalUpdated}>{texts.updated.replace('{date}', formatDate(SITE.legalUpdated + 'T00:00:00Z', { dateStyle: 'long' }))}</time>
        </p>
        {texts.translationNote && <p className="mt-3 rounded-lg bg-surface-3 px-3 py-2 text-xs text-fg-muted">{texts.translationNote}</p>}
        <p className="mt-6 leading-relaxed text-fg-muted">{fill(page.intro)}</p>
      </header>
      <nav aria-label={texts.contents} className="border-b border-line py-6">
        <h2 className="text-xs font-semibold uppercase tracking-[0.12em] text-fg-subtle">{texts.contents}</h2>
        <ol className="mt-3 grid gap-x-6 gap-y-1.5 text-sm sm:grid-cols-2">
          {page.sections.map((s, i) => (
            <li key={s.id}><a href={`#${s.id}`} className="text-brand underline-offset-2 hover:underline">{i + 1}. {s.heading}</a></li>
          ))}
        </ol>
      </nav>
      <div className="space-y-10 pt-10">
        {page.sections.map((s, i) => {
          const items = s.body.filter((p) => p.startsWith('- '))
          const paragraphs = s.body.filter((p) => !p.startsWith('- '))
          return (
            <section key={s.id} id={s.id} className="scroll-mt-24">
              <h2 className="text-lg font-semibold text-fg">{i + 1}. {s.heading}</h2>
              {paragraphs.map((p, j) => <p key={j} className="mt-3 leading-relaxed text-fg-muted">{fill(p)}</p>)}
              {items.length > 0 && (
                <ul className="mt-3 list-disc space-y-2 ps-5 leading-relaxed text-fg-muted marker:text-fg-subtle">
                  {items.map((p, j) => <li key={j}>{fill(p.slice(2))}</li>)}
                </ul>
              )}
            </section>
          )
        })}
      </div>
    </article>
  )
}
