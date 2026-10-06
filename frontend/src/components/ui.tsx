import type { ReactNode } from "react"
import { avatarColor, cn } from "../format"

export function Pill({
  tone,
  children,
}: {
  tone: "rose" | "amber" | "moss" | "slate" | "teal"
  children: ReactNode
}) {
  const tones = {
    rose: "bg-blush text-rose",
    amber: "bg-cream text-amber",
    moss: "bg-sage text-moss",
    slate: "bg-[#efeae2] text-mute",
    teal: "bg-mist text-teal",
  }
  return <span className={cn("inline-flex items-center rounded-full px-2.5 py-1 text-xs font-medium", tones[tone])}>{children}</span>
}

export function Avatar({ name, initials, className }: { name: string; initials: string; className?: string }) {
  return (
    <span
      className={cn("grid h-10 w-10 shrink-0 place-items-center rounded-full text-sm font-medium text-white", className)}
      style={{ background: avatarColor(name) }}
    >
      {initials}
    </span>
  )
}

export function Panel({ children, className }: { children: ReactNode; className?: string }) {
  return <section className={cn("rounded-3xl bg-card p-5 shadow-card ring-1 ring-line md:p-6", className)}>{children}</section>
}

export function Eyebrow({ children }: { children: ReactNode }) {
  return <div className="text-[11px] font-medium uppercase tracking-[0.16em] text-mute">{children}</div>
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <Panel className="mx-auto max-w-2xl">
      <h2 className="font-serif text-3xl">The book didn't load</h2>
      <p className="mt-3 text-mute">{message}</p>
      <p className="mt-2 text-sm text-mute">From the backend folder, run uvicorn app.main:app --reload --port 8000.</p>
      {onRetry && (
        <button type="button" onClick={onRetry} className="mt-5 rounded-full bg-deep px-4 py-2 text-sm text-white">
          Try again
        </button>
      )}
    </Panel>
  )
}

export function LoadingBlock() {
  return (
    <div className="space-y-4">
      <div className="h-28 animate-pulse rounded-3xl bg-[#e7e1d8]" />
      <div className="grid gap-4 md:grid-cols-3">
        <div className="h-40 animate-pulse rounded-3xl bg-[#e7e1d8]" />
        <div className="h-40 animate-pulse rounded-3xl bg-[#e7e1d8] md:col-span-2" />
      </div>
    </div>
  )
}
