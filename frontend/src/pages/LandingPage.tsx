import { ArrowRight, BookOpenCheck, Download, FileSearch, Languages, Lightbulb, Lock, Network, ScanText, Upload } from 'lucide-react'
import { Link } from 'react-router-dom'
import { PaperGraphArt } from '../components/GraphArt'
import { ButtonLink } from '../components/ui'
import { usePageMeta } from '../hooks/usePageMeta'
import { useI18n } from '../i18n/I18nProvider'
import type { MessageKey } from '../i18n/en'
import { useTheme } from '../theme/ThemeProvider'

/** Real screenshots of the product (light and dark), compressed WebP with explicit size to avoid layout shift. */
function ProductShot({ name, alt, width, height, priority }: { name: string; alt: string; width: number; height: number; priority?: boolean }) {
  const { resolved } = useTheme()
  return (
    <img src={`/images/${name}-${resolved}.webp`} alt={alt} width={width} height={height}
      srcSet={`/images/${name}-${resolved}-640.webp 640w, /images/${name}-${resolved}.webp 1200w`}
      sizes="(min-width: 1180px) 1100px, calc(100vw - 32px)"
      loading={priority ? 'eager' : 'lazy'} decoding="async" fetchPriority={priority ? 'high' : 'auto'}
      className="block h-auto w-full" />
  )
}

function Frame({ children, label }: { children: React.ReactNode; label: string }) {
  return (
    <figure className="overflow-hidden rounded-xl border border-line bg-surface shadow-pop">
      <div className="flex items-center gap-1.5 border-b border-line bg-surface-2 px-3 py-2" aria-hidden>
        <span className="h-2.5 w-2.5 rounded-full bg-line-strong" /><span className="h-2.5 w-2.5 rounded-full bg-line-strong" />
        <span className="h-2.5 w-2.5 rounded-full bg-line-strong" />
        <span className="ms-3 truncate text-[11px] text-fg-subtle">{label}</span>
      </div>
      {children}
    </figure>
  )
}

const STEPS: { icon: typeof Upload; title: MessageKey; text: MessageKey }[] = [
  { icon: Upload, title: 'landing.step1.title', text: 'landing.step1.text' },
  { icon: Network, title: 'landing.step2.title', text: 'landing.step2.text' },
  { icon: FileSearch, title: 'landing.step3.title', text: 'landing.step3.text' },
]

const FEATURES: { icon: typeof Upload; title: MessageKey; text: MessageKey }[] = [
  { icon: BookOpenCheck, title: 'landing.f.cited.title', text: 'landing.f.cited.text' },
  { icon: ScanText, title: 'landing.f.single.title', text: 'landing.f.single.text' },
  { icon: Lightbulb, title: 'landing.f.gaps.title', text: 'landing.f.gaps.text' },
  { icon: Languages, title: 'landing.f.lang.title', text: 'landing.f.lang.text' },
  { icon: Lock, title: 'landing.f.private.title', text: 'landing.f.private.text' },
  { icon: Download, title: 'landing.f.export.title', text: 'landing.f.export.text' },
]

const FAQ: { q: MessageKey; a: MessageKey }[] = [
  { q: 'faq.files.q', a: 'faq.files.a' },
  { q: 'faq.sources.q', a: 'faq.sources.a' },
  { q: 'faq.mistakes.q', a: 'faq.mistakes.a' },
  { q: 'faq.privacy.q', a: 'faq.privacy.a' },
  { q: 'faq.model.q', a: 'faq.model.a' },
  { q: 'faq.delete.q', a: 'faq.delete.a' },
  { q: 'faq.languages.q', a: 'faq.languages.a' },
]

export default function LandingPage() {
  const { t } = useI18n()
  usePageMeta('', t('meta.home.description'))

  return (
    <>
      {/* Hero: what it does, one call to action, and the real product. */}
      <section className="relative overflow-hidden border-b border-line">
        <div className="pointer-events-none absolute inset-0 opacity-[0.5] [background-image:radial-gradient(var(--line)_1px,transparent_1px)] [background-size:22px_22px] dark:opacity-30" aria-hidden />
        <div className="relative mx-auto grid max-w-6xl items-center gap-12 px-4 pb-16 pt-14 sm:px-6 lg:grid-cols-[1fr_1.1fr] lg:pb-24 lg:pt-20">
          <div className="animate-fade-up">
            <p className="mb-4 inline-flex items-center gap-2 rounded-md border border-line bg-surface px-2.5 py-1 text-xs font-medium text-fg-muted">
              <span className="h-1.5 w-1.5 rounded-full bg-brand" aria-hidden />{t('landing.kicker')}
            </p>
            <h1 className="text-[34px] font-semibold leading-[1.12] tracking-tight text-fg sm:text-5xl">{t('landing.title')}</h1>
            <p className="mt-5 max-w-xl text-[17px] leading-relaxed text-fg-muted">{t('landing.text')}</p>
            <div className="mt-8 flex flex-wrap items-center gap-4">
              <ButtonLink to="/signup" size="lg">{t('landing.cta')} <ArrowRight className="h-4 w-4 rtl:rotate-180" /></ButtonLink>
              <p className="text-sm text-fg-muted">
                {t('auth.signup.haveAccount')} <Link to="/signin" className="font-medium text-brand hover:text-brand-hover">{t('auth.signin.cta')}</Link>
              </p>
            </div>
          </div>
          <div className="animate-fade-up [animation-delay:120ms]">
            <Frame label={t('landing.shot.answer.label')}>
              <ProductShot name="product-answer" alt={t('landing.shot.answer.alt')} width={1200} height={760} priority />
            </Frame>
          </div>
        </div>
      </section>

      {/* How it works */}
      <section id="how" className="scroll-mt-20 border-b border-line">
        <div className="mx-auto max-w-6xl px-4 py-20 sm:px-6">
          <div className="grid items-center gap-12 lg:grid-cols-[1fr_1fr]">
            <div>
              <h2 className="text-3xl font-semibold tracking-tight text-fg">{t('landing.how.title')}</h2>
              <p className="mt-3 max-w-lg text-fg-muted">{t('landing.how.text')}</p>
              <ol className="mt-10 space-y-8">
                {STEPS.map(({ icon: Icon, title, text }, i) => (
                  <li key={title} className="flex gap-4">
                    <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border border-line bg-surface text-brand">
                      <Icon className="h-5 w-5" aria-hidden />
                    </span>
                    <div>
                      <h3 className="font-semibold text-fg"><span className="me-2 text-fg-subtle">{i + 1}.</span>{t(title)}</h3>
                      <p className="mt-1 text-sm leading-relaxed text-fg-muted">{t(text)}</p>
                    </div>
                  </li>
                ))}
              </ol>
            </div>
            <div className="rounded-2xl border border-line bg-surface p-8">
              <PaperGraphArt className="mx-auto h-auto w-full max-w-md" />
              <p className="mt-6 text-center text-sm text-fg-muted">{t('landing.how.caption')}</p>
            </div>
          </div>
        </div>
      </section>

      {/* Features */}
      <section id="features" className="scroll-mt-20 border-b border-line bg-surface">
        <div className="mx-auto max-w-6xl px-4 py-20 sm:px-6">
          <h2 className="text-3xl font-semibold tracking-tight text-fg">{t('landing.features.title')}</h2>
          <div className="mt-10 grid gap-px overflow-hidden rounded-xl border border-line bg-line sm:grid-cols-2 lg:grid-cols-3">
            {FEATURES.map(({ icon: Icon, title, text }) => (
              <div key={title} className="group bg-surface p-6 transition-colors hover:bg-surface-2">
                <Icon className="h-5 w-5 text-brand transition-transform duration-200 group-hover:-translate-y-0.5" aria-hidden />
                <h3 className="mt-4 font-semibold text-fg">{t(title)}</h3>
                <p className="mt-1.5 text-sm leading-relaxed text-fg-muted">{t(text)}</p>
              </div>
            ))}
          </div>
          <div className="mt-16 grid items-center gap-10 lg:grid-cols-[1.2fr_1fr]">
            <Frame label={t('landing.shot.graph.label')}>
              <ProductShot name="product-graph" alt={t('landing.shot.graph.alt')} width={1200} height={680} />
            </Frame>
            <div>
              <h3 className="text-xl font-semibold tracking-tight text-fg">{t('landing.graph.title')}</h3>
              <p className="mt-3 leading-relaxed text-fg-muted">{t('landing.graph.text')}</p>
            </div>
          </div>
        </div>
      </section>

      {/* FAQ */}
      <section id="faq" className="scroll-mt-20 border-b border-line">
        <div className="mx-auto max-w-3xl px-4 py-20 sm:px-6">
          <h2 className="text-3xl font-semibold tracking-tight text-fg">{t('landing.faq.title')}</h2>
          <div className="mt-8 divide-y divide-line rounded-xl border border-line bg-surface">
            {FAQ.map(({ q, a }) => (
              <details key={q} className="group">
                <summary className="flex cursor-pointer list-none items-center justify-between gap-4 px-5 py-4 font-medium text-fg transition-colors hover:bg-surface-2 [&::-webkit-details-marker]:hidden">
                  {t(q)}
                  <span className="relative h-3 w-3 shrink-0 text-fg-subtle" aria-hidden>
                    <span className="absolute inset-x-0 top-1/2 h-px -translate-y-1/2 bg-current" />
                    <span className="absolute inset-y-0 left-1/2 w-px -translate-x-1/2 bg-current transition-transform duration-200 group-open:rotate-90" />
                  </span>
                </summary>
                <p className="px-5 pb-5 text-sm leading-relaxed text-fg-muted">{t(a)}</p>
              </details>
            ))}
          </div>
        </div>
      </section>

      {/* Closing call to action (same single action as the hero) */}
      <section className="bg-black text-white">
        <div className="mx-auto flex max-w-6xl flex-col items-start gap-6 px-4 py-16 sm:px-6 md:flex-row md:items-center md:justify-between">
          <div>
            <h2 className="text-2xl font-semibold tracking-tight">{t('landing.final.title')}</h2>
            <p className="mt-2 text-white/70">{t('landing.final.text')}</p>
          </div>
          <ButtonLink to="/signup" size="lg">{t('landing.cta')} <ArrowRight className="h-4 w-4 rtl:rotate-180" /></ButtonLink>
        </div>
      </section>
    </>
  )
}
