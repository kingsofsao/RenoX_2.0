// Header and footer for the public pages (home, privacy, terms, 404).
import { useEffect, useState, type ReactNode } from 'react'
import { Link, Outlet } from 'react-router-dom'
import { Menu, X } from 'lucide-react'
import { useAuth } from '../auth/AuthProvider'
import { SITE } from '../config/site'
import { useI18n } from '../i18n/I18nProvider'
import { openCookieSettings } from './ConsentBanner'
import { openContact } from './ContactWidget'
import { LanguageSelect, ThemeToggle } from './Preferences'
import { ButtonLink, Logo, cx } from './ui'

function useScrolled(threshold = 8) {
  const [scrolled, setScrolled] = useState(false)
  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > threshold)
    onScroll()
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [threshold])
  return scrolled
}

export function PublicLayout({ children }: { children?: ReactNode }) {
  const { t } = useI18n()
  const { status } = useAuth()
  const scrolled = useScrolled()
  const [menu, setMenu] = useState(false)
  const signedIn = status === 'signed-in'
  const sections = [
    { href: '/#how', label: t('landing.nav.how') },
    { href: '/#features', label: t('landing.nav.features') },
    { href: '/#faq', label: t('landing.nav.faq') },
  ]

  return (
    <div className="flex min-h-screen flex-col bg-canvas">
      <a href="#main" className="sr-only focus:not-sr-only focus:fixed focus:start-4 focus:top-4 focus:z-[80] focus:rounded-lg focus:bg-brand-solid focus:px-3 focus:py-2 focus:text-white">
        {t('nav.skip')}
      </a>
      <header className={cx('sticky top-0 z-40 border-b transition-colors duration-200 print:static',
        scrolled ? 'border-line bg-canvas/90 backdrop-blur-md' : 'border-transparent bg-canvas')}>
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between gap-4 px-4 sm:px-6">
          <Link to="/" className="flex shrink-0 items-center gap-2.5" aria-label={SITE.name}>
            <Logo className="h-8 w-8" />
            <span className="whitespace-nowrap font-semibold tracking-tight text-fg">ResearchMind <span className="text-brand">AI</span></span>
          </Link>
          <nav className="hidden items-center gap-1 md:flex" aria-label={t('nav.main')}>
            {sections.map((s) => (
              <a key={s.href} href={s.href} className="rounded-md px-3 py-2 text-sm text-fg-muted transition-colors hover:bg-surface-3 hover:text-fg">{s.label}</a>
            ))}
          </nav>
          <div className="hidden items-center gap-2 md:flex">
            <LanguageSelect />
            <ThemeToggle />
            {signedIn ? (
              <ButtonLink to="/" size="sm">{t('landing.openApp')}</ButtonLink>
            ) : (
              <>
                <Link to="/signin" className="rounded-md px-3 py-2 text-sm font-medium text-fg-muted transition-colors hover:text-fg">{t('auth.signin.title')}</Link>
                <ButtonLink to="/signup" size="sm">{t('landing.cta')}</ButtonLink>
              </>
            )}
          </div>
          <button type="button" onClick={() => setMenu((v) => !v)} aria-expanded={menu} aria-controls="public-menu"
            aria-label={menu ? t('nav.close') : t('nav.open')}
            className="rounded-md p-2 text-fg-muted transition-colors hover:bg-surface-3 hover:text-fg md:hidden">
            {menu ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
          </button>
        </div>
        {menu && (
          <div id="public-menu" className="animate-fade-in border-t border-line bg-canvas px-4 pb-5 pt-3 md:hidden">
            <nav className="flex flex-col" aria-label={t('nav.main')}>
              {sections.map((s) => (
                <a key={s.href} href={s.href} onClick={() => setMenu(false)} className="rounded-md px-2 py-2.5 text-sm text-fg">{s.label}</a>
              ))}
              {!signedIn && <Link to="/signin" onClick={() => setMenu(false)} className="rounded-md px-2 py-2.5 text-sm text-fg">{t('auth.signin.title')}</Link>}
            </nav>
            <div className="mt-3 flex items-center gap-2"><LanguageSelect /><ThemeToggle /></div>
            <ButtonLink to={signedIn ? '/' : '/signup'} className="mt-4 w-full" onClick={() => setMenu(false)}>
              {signedIn ? t('landing.openApp') : t('landing.cta')}
            </ButtonLink>
          </div>
        )}
      </header>

      <main id="main" className="min-h-svh flex-1">{children ?? <Outlet />}</main>

      <footer className="border-t border-line bg-surface print:hidden">
        <div className="mx-auto flex max-w-6xl flex-col gap-6 px-4 py-10 sm:flex-row sm:items-start sm:justify-between sm:px-6">
          <div className="max-w-xs">
            <div className="flex items-center gap-2.5">
              <Logo className="h-7 w-7" />
              <span className="font-semibold tracking-tight text-fg">{SITE.name}</span>
            </div>
            <p className="mt-3 text-sm text-fg-muted">{t('footer.about')}</p>
          </div>
          <nav aria-label={t('footer.legal')} className="flex flex-wrap gap-x-6 gap-y-2 text-sm">
            <Link to="/privacy" className="text-fg-muted transition-colors hover:text-fg">{t('legal.privacy')}</Link>
            <Link to="/terms" className="text-fg-muted transition-colors hover:text-fg">{t('legal.terms')}</Link>
            <button type="button" onClick={openContact} className="text-fg-muted transition-colors hover:text-fg">{t('contact.button')}</button>
            <button type="button" onClick={openCookieSettings} className="text-fg-muted transition-colors hover:text-fg">{t('consent.settings')}</button>
          </nav>
        </div>
        <div className="border-t border-line">
          <p className="mx-auto max-w-6xl px-4 py-4 text-xs text-fg-subtle sm:px-6">© {new Date().getFullYear()} {SITE.operator}</p>
        </div>
      </footer>
    </div>
  )
}
