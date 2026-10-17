// Language and theme controls, used on the sign-in pages, in the sidebar and in Settings.
import { Globe, Monitor, Moon, Sun } from 'lucide-react'
import { useAuth } from '../auth/AuthProvider'
import { useI18n } from '../i18n/I18nProvider'
import { LANGUAGES, isLang } from '../i18n/languages'
import { useTheme } from '../theme/ThemeProvider'
import type { ThemeSetting } from '../types/api'
import { cx } from './ui'

export function LanguageSelect({ className, tone = 'default' }: { className?: string; tone?: 'default' | 'dark' }) {
  const { lang, t } = useI18n()
  const { setLanguage } = useAuth()
  return (
    <label className={cx('relative inline-flex items-center', className)}>
      <span className="sr-only">{t('settings.language')}</span>
      <Globe className={cx('pointer-events-none absolute start-2.5 h-4 w-4', tone === 'dark' ? 'text-white/60' : 'text-fg-subtle')} />
      <select value={lang} onChange={(e) => { if (isLang(e.target.value)) setLanguage(e.target.value) }}
        className={cx('cursor-pointer appearance-none rounded-lg border py-1.5 ps-8 pe-3 text-sm transition-colors focus:outline-none focus:ring-2 focus:ring-brand/40',
          tone === 'dark' ? 'border-white/15 bg-white/5 text-white hover:bg-white/10' : 'border-line bg-surface text-fg hover:bg-surface-2')}>
        {LANGUAGES.map((l) => <option key={l.code} value={l.code} className="text-black">{l.name}</option>)}
      </select>
    </label>
  )
}

const THEMES: { value: ThemeSetting; icon: typeof Sun }[] = [
  { value: 'light', icon: Sun },
  { value: 'dark', icon: Moon },
  { value: 'system', icon: Monitor },
]

/** Compact segmented control: light / dark / follow the system. */
export function ThemeToggle({ className, tone = 'default' }: { className?: string; tone?: 'default' | 'dark' }) {
  const { t } = useI18n()
  const { setting } = useTheme()
  const { setTheme } = useAuth()
  return (
    <div role="radiogroup" aria-label={t('settings.theme')}
      className={cx('inline-flex rounded-lg p-0.5', tone === 'dark' ? 'bg-white/5 ring-1 ring-white/10' : 'bg-surface-3', className)}>
      {THEMES.map(({ value, icon: Icon }) => {
        const active = setting === value
        return (
          <button key={value} type="button" role="radio" aria-checked={active} title={t(`theme.${value}`)}
            onClick={() => setTheme(value)}
            className={cx('rounded-md p-1.5 transition-all duration-150 active:scale-90',
              active ? (tone === 'dark' ? 'bg-white/15 text-white' : 'bg-surface text-fg shadow-sm')
                : tone === 'dark' ? 'text-white/55 hover:text-white' : 'text-fg-subtle hover:text-fg')}>
            <Icon className="h-4 w-4" />
            <span className="sr-only">{t(`theme.${value}`)}</span>
          </button>
        )
      })}
    </div>
  )
}
