// Decorative knowledge-graph drawings (inline SVG, theme-aware, no images to download).

/** One paper (centre) linked to its own methods and datasets: the shape of every ResearchMind graph. */
export function PaperGraphArt({ className }: { className?: string }) {
  const left = [[40, 50], [28, 120], [44, 190]]
  const right = [[300, 70], [312, 170]]
  return (
    <svg viewBox="0 0 340 240" className={className} aria-hidden>
      <g stroke="var(--line-strong)" strokeWidth="1.5" fill="none">
        {left.map(([x, y], i) => <path key={`l${i}`} d={`M${x + 22} ${y} C 120 ${y}, 120 120, 150 120`} />)}
        {right.map(([x, y], i) => <path key={`r${i}`} d={`M190 120 C 220 120, 220 ${y}, ${x - 22} ${y}`} />)}
      </g>
      {left.map(([x, y], i) => (
        <g key={`ln${i}`}><rect x={x - 22} y={y - 11} width="44" height="22" rx="6" fill="var(--surface)" stroke="var(--fg)" strokeWidth="1.5" /></g>
      ))}
      {right.map(([x, y], i) => (
        <g key={`rn${i}`}><rect x={x - 22} y={y - 11} width="44" height="22" rx="6" fill="var(--surface-3)" stroke="var(--fg-subtle)" strokeWidth="1.5" /></g>
      ))}
      <rect x="140" y="96" width="60" height="48" rx="10" fill="var(--brand)" />
      <path d="M156 112h28M156 120h28M156 128h18" stroke="#fff" strokeWidth="2.5" strokeLinecap="round" />
    </svg>
  )
}

/** Separate clusters that never touch: used on the 404 page ("this link connects to nothing"). */
export function DisconnectedArt({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 320 160" className={className} aria-hidden>
      <g stroke="var(--line-strong)" strokeWidth="1.5" strokeDasharray="4 5" fill="none">
        <path d="M70 80 L130 80" /><path d="M190 80 L250 80" />
      </g>
      <circle cx="50" cy="80" r="20" fill="var(--surface)" stroke="var(--fg)" strokeWidth="1.5" />
      <circle cx="160" cy="80" r="26" fill="var(--brand)" />
      <text x="160" y="87" textAnchor="middle" fontSize="20" fontWeight="600" fill="#fff" fontFamily="inherit">?</text>
      <circle cx="270" cy="80" r="20" fill="var(--surface-3)" stroke="var(--fg-subtle)" strokeWidth="1.5" />
    </svg>
  )
}
