// Split layout for sign-in and sign-up: a black brand panel and the form.
import type { ReactNode } from 'react'
import { BookOpenCheck, Network, ShieldCheck } from 'lucide-react'
import { useI18n } from '../i18n/I18nProvider'
import { LanguageSelect, ThemeToggle } from './Preferences'
import { Logo } from './ui'

export function AuthShell({ title, subtitle, children, footer }: { title: string; subtitle: string; children: ReactNode; footer: ReactNode }) {
  const { t } = useI18n()
  const points = [
    { icon: Network, title: t('auth.point.graph.title'), text: t('auth.point.graph.text') },
    { icon: BookOpenCheck, title: t('auth.point.cited.title'), text: t('auth.point.cited.text') },
    { icon: ShieldCheck, title: t('auth.point.private.title'), text: t('auth.point.private.text') },
  ]
  return (
    <div className="flex min-h-screen bg-canvas">
      <aside className="relative hidden w-[46%] max-w-[640px] overflow-hidden bg-black text-white lg:flex lg:flex-col">
        {/* Soft blue light and a fine grid: depth without imagery. */}
        <div className="pointer-events-none absolute -top-40 -start-40 h-[520px] w-[520px] rounded-full bg-[#1c69d4]/35 blur-[120px]" />
        <div className="pointer-events-none absolute bottom-[-180px] end-[-120px] h-[420px] w-[420px] rounded-full bg-[#1c69d4]/20 blur-[110px]" />
        <div className="pointer-events-none absolute inset-0 opacity-[0.07] [background-image:linear-gradient(#fff_1px,transparent_1px),linear-gradient(90deg,#fff_1px,transparent_1px)] [background-size:44px_44px]" />
        <div className="relative flex flex-1 flex-col justify-between p-12">
          <div className="flex items-center gap-3">
            <Logo className="h-9 w-9" />
            <span className="text-lg font-semibold tracking-tight">ResearchMind <span className="text-[#5ea2ff]">AI</span></span>
          </div>
          <div className="animate-fade-up">
            <h2 className="max-w-md text-[34px] font-semibold leading-[1.15] tracking-tight">{t('auth.hero.title')}</h2>
            <p className="mt-4 max-w-md text-[15px] leading-relaxed text-white/65">{t('auth.hero.text')}</p>
            <ul className="mt-10 space-y-5">
              {points.map(({ icon: Icon, title: pt, text }) => (
                <li key={pt} className="flex gap-4">
                  <span className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-white/[0.06] ring-1 ring-white/10">
                    <Icon className="h-4.5 w-4.5 text-[#5ea2ff]" />
                  </span>
                  <span>
                    <span className="block text-sm font-medium">{pt}</span>
                    <span className="block text-sm text-white/55">{text}</span>
                  </span>
                </li>
              ))}
            </ul>
          </div>
          <div className="flex items-center gap-2 text-xs text-white/40">
            <span className="h-px w-8 bg-[#1c69d4]" />
            {t('auth.footer')}
          </div>
        </div>
      </aside>

      <main className="flex flex-1 flex-col">
        <div className="flex items-center justify-between gap-3 px-5 py-4 sm:px-8">
          <div className="flex min-w-0 items-center gap-2.5 lg:invisible">
            <Logo className="h-8 w-8 shrink-0" />
            <span className="hidden whitespace-nowrap font-semibold tracking-tight text-fg sm:inline">ResearchMind AI</span>
          </div>
          <div className="flex items-center gap-2">
            <LanguageSelect />
            <ThemeToggle />
          </div>
        </div>
        <div className="flex flex-1 items-center justify-center px-5 pb-16 sm:px-8">
          <div className="w-full max-w-[400px] animate-fade-up">
            <h1 className="text-2xl font-semibold tracking-tight text-fg">{title}</h1>
            <p className="mt-1.5 text-sm text-fg-muted">{subtitle}</p>
            <div className="mt-8">{children}</div>
            <div className="mt-8 border-t border-line pt-6 text-center text-sm text-fg-muted">{footer}</div>
          </div>
        </div>
      </main>
    </div>
  )
}
