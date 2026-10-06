import { X } from "lucide-react"

export const FLOW = [
  "Data",
  "Customer 360",
  "Interaction analysis",
  "AI insights",
  "Risk and sentiment",
  "NBA engine",
  "Action",
  "Outcome",
]

export function HowItWorksStrip() {
  return (
    <div className="rounded-3xl bg-card px-4 py-4 shadow-card ring-1 ring-line">
      <div className="text-[11px] uppercase tracking-[0.16em] text-mute">How Customer-360 works</div>
      <ol className="mt-3 flex flex-wrap items-center gap-2">
        {FLOW.map((step, index) => (
          <li key={step} className="flex items-center gap-2">
            <span className="rounded-full bg-paper px-3 py-1 text-sm">{step}</span>
            {index < FLOW.length - 1 && <span className="text-mute">→</span>}
          </li>
        ))}
      </ol>
    </div>
  )
}

export function HowItWorksModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  if (!open) return null
  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-ink/40 p-4">
      <div role="dialog" aria-modal="true" className="max-h-[90vh] w-full max-w-lg overflow-auto rounded-3xl bg-card p-6 shadow-card">
        <div className="flex items-start justify-between gap-3">
          <h2 className="font-serif text-3xl">How Customer-360 works</h2>
          <button type="button" aria-label="Close" onClick={onClose}>
            <X size={18} />
          </button>
        </div>
        <ol className="mt-5 space-y-2">
          {FLOW.map((step, index) => (
            <li key={step} className="flex items-center gap-3 text-sm">
              <span className="grid h-7 w-7 place-items-center rounded-full bg-paper text-xs text-mute">{index + 1}</span>
              <span>{step}</span>
            </li>
          ))}
        </ol>
        <p className="mt-5 text-sm leading-6 text-mute">
          Structured policies, loans, payments, and claims sit on the same file as calls and emails. Interaction analysis feeds sentiment, intent, and risk. The NBA engine evaluates customer signals, interaction insights, business rules, and eligibility conditions to select the highest-priority recommended action. Recording an outcome updates the file.
        </p>
      </div>
    </div>
  )
}
