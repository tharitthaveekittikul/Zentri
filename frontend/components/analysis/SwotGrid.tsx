type SwotData = {
  strengths: string[]
  weaknesses: string[]
  opportunities: string[]
  threats: string[]
}

type SwotGridProps = {
  swot: SwotData
}

const quadrants = [
  { key: 'strengths' as const, label: 'Strengths', colorVar: '--color-success' },
  { key: 'weaknesses' as const, label: 'Weaknesses', colorVar: '--color-destructive' },
  { key: 'opportunities' as const, label: 'Opportunities', colorVar: '--color-info' },
  { key: 'threats' as const, label: 'Threats', colorVar: '--color-warning' },
]

export function SwotGrid({ swot }: SwotGridProps) {
  return (
    <div className="grid grid-cols-2 gap-3">
      {quadrants.map(({ key, label, colorVar }) => (
        <div
          key={key}
          className="rounded-lg border p-3"
          style={{ borderColor: `var(${colorVar})` }}
        >
          <p
            className="mb-2 text-xs font-semibold uppercase tracking-wide"
            style={{ color: `var(${colorVar})` }}
          >
            {label}
          </p>
          <ul className="space-y-1">
            {swot[key].map((item, i) => (
              <li key={i} className="text-sm text-[var(--color-text-secondary)]">
                • {item}
              </li>
            ))}
            {swot[key].length === 0 && (
              <li className="text-sm text-[var(--color-text-muted)] italic">None identified</li>
            )}
          </ul>
        </div>
      ))}
    </div>
  )
}
