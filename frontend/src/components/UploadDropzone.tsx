import { useRef, useState, type DragEvent, type KeyboardEvent } from 'react'
import { UploadCloud } from 'lucide-react'
import { cx } from './ui'

/** Drag-and-drop / click-to-browse area. Emits the raw File list; validation happens in the page. */
export function UploadDropzone({ onFiles, disabled, maxMb }: { onFiles: (files: File[]) => void; disabled?: boolean; maxMb?: number }) {
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
      aria-label="Upload PDF files"
      onClick={open}
      onKeyDown={onKey}
      onDragOver={(e) => {
        e.preventDefault()
        if (!disabled) setDragging(true)
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={onDrop}
      className={cx(
        'flex flex-col items-center justify-center rounded-xl border-2 border-dashed px-6 py-12 text-center transition-colors',
        'focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-600',
        disabled ? 'cursor-not-allowed border-slate-200 bg-slate-50 opacity-60'
          : dragging ? 'cursor-copy border-indigo-500 bg-indigo-50' : 'cursor-pointer border-slate-300 bg-white hover:border-indigo-400 hover:bg-slate-50',
      )}
    >
      <div className={cx('mb-3 rounded-full p-3', dragging ? 'bg-indigo-100 text-indigo-600' : 'bg-slate-100 text-slate-500')}>
        <UploadCloud className="h-7 w-7" />
      </div>
      <p className="font-medium text-slate-900">{dragging ? 'Drop to add files' : 'Drag & drop PDFs here'}</p>
      <p className="mt-1 text-sm text-slate-500">
        or <span className="font-medium text-indigo-600">browse your computer</span>
        {maxMb ? ` · PDF only, up to ${maxMb} MB each` : ' · PDF only'}
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
