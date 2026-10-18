import { useRef, useState, type DragEvent, type KeyboardEvent } from 'react'
import { UploadCloud } from 'lucide-react'
import { useI18n } from '../i18n/I18nProvider'
import { cx } from './ui'

/** Drag-and-drop / click-to-browse area. Emits the raw File list; validation happens in the page. */
export function UploadDropzone({ onFiles, disabled, maxMb }: { onFiles: (files: File[]) => void; disabled?: boolean; maxMb?: number }) {
  const { t } = useI18n()
  const input = useRef<HTMLInputElement>(null)
  const [dragging, setDragging] = useState(false)

  const open = () => !disabled && input.current?.click()
  const onDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    setDragging(false)
    if (!disabled && e.dataTransfer.files.length) onFiles(Array.from(e.dataTransfer.files))
  }
  const onKey = (e: KeyboardEvent<HTMLDivElement>) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault()
      open()
    }
  }

  return (
    <div
      role="button"
      tabIndex={disabled ? -1 : 0}
      aria-disabled={disabled}
      aria-label={t('upload.drop.aria')}
      onClick={open}
      onKeyDown={onKey}
      onDragOver={(e) => {
        e.preventDefault()
        if (!disabled) setDragging(true)
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={onDrop}
      className={cx(
        'group flex flex-col items-center justify-center rounded-2xl border-2 border-dashed px-6 py-14 text-center transition-all duration-200',
        'focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand',
        disabled ? 'cursor-not-allowed border-line bg-surface-2 opacity-60'
          : dragging ? 'scale-[1.01] cursor-copy border-brand bg-brand-soft' : 'cursor-pointer border-line-strong bg-surface hover:border-brand/60 hover:bg-surface-2',
      )}
    >
      <div className={cx('mb-4 rounded-2xl p-3.5 transition-all duration-200', dragging ? 'scale-110 bg-brand-solid text-white' : 'bg-brand-soft text-brand group-hover:-translate-y-0.5')}>
        <UploadCloud className="h-7 w-7" />
      </div>
      <p className="font-medium text-fg">{dragging ? t('upload.drop.release') : t('upload.drop.title')}</p>
      <p className="mt-1 text-sm text-fg-muted">
        {t('upload.drop.or')} <span className="font-medium text-brand">{t('upload.drop.browse')}</span>
        {maxMb ? ` · ${t('upload.drop.limit', { mb: maxMb })}` : ''}
      </p>
      <input
        ref={input}
        type="file"
        accept="application/pdf,.pdf"
        multiple
        hidden
        onChange={(e) => {
          if (e.target.files?.length) onFiles(Array.from(e.target.files))
          e.target.value = '' // allow selecting the same file again
        }}
      />
    </div>
  )
}
