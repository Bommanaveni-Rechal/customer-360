import { useEffect, useState } from "react"
import { Link, useSearchParams } from "react-router-dom"
import { getCustomers } from "../api"
import { Avatar, ErrorState, Eyebrow, LoadingBlock, Pill } from "../components/ui"
import { bookLabel, money, priorityTone, riskTone, sentimentTone } from "../format"
import type { CustomerRow } from "../types"

const RISKS = ["", "High", "Medium", "Low"]
const SENTIMENTS = ["", "Negative", "Neutral", "Positive"]
const BOOKS = ["", "Insurance", "Lending", "Both"]
const SEGMENTS = ["", "Priority", "Affluent", "Retail", "Mass", "SME"]

export default function Customers() {
  const [params, setParams] = useSearchParams()
  const [rows, setRows] = useState<CustomerRow[] | null>(null)
  const [error, setError] = useState("")

  const filters = {
    q: params.get("q") ?? "",
    risk: params.get("risk") ?? "",
    sentiment: params.get("sentiment") ?? "",
    book: params.get("book") ?? "",
    segment: params.get("segment") ?? "",
    needs_action: params.get("needs_action") === "true",
    churn: params.get("churn") === "true",
    open_issue: params.get("open_issue") === "true",
    sort: params.get("sort") ?? "priority",
  }

  useEffect(() => {
    setRows(null)
    setError("")
    getCustomers(filters)
      .then((result) => setRows(result.customers))
      .catch((reason: Error) => setError(reason.message))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params])

  function update(next: Record<string, string | boolean>) {
    const search = new URLSearchParams(params)
    for (const [key, value] of Object.entries(next)) {
      if (value === "" || value === false) search.delete(key)
      else search.set(key, String(value))
    }
    setParams(search)
  }

  if (error) return <ErrorState message={error} onRetry={() => setParams(new URLSearchParams(params))} />

  return (
    <div className="space-y-6">
      <div>
        <Eyebrow>Customer book</Eyebrow>
        <h1 className="mt-2 font-serif text-4xl">Every relationship, with the next action attached</h1>
      </div>
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-6">
        <label className="xl:col-span-2">
          <span className="mb-1 block text-xs text-mute">Search</span>
          <input
            value={filters.q}
            onChange={(event) => update({ q: event.target.value })}
            placeholder="Name, city, policy, claim"
            className="w-full rounded-2xl border border-line bg-card px-3 py-2.5 text-sm"
          />
        </label>
        <Select label="Risk" value={filters.risk} options={RISKS} onChange={(risk) => update({ risk })} />
        <Select label="Sentiment" value={filters.sentiment} options={SENTIMENTS} onChange={(sentiment) => update({ sentiment })} />
        <Select label="Book" value={filters.book} options={BOOKS} onChange={(book) => update({ book })} />
        <Select label="Sort" value={filters.sort} options={["priority", "risk", "value", "name"]} onChange={(sort) => update({ sort })} />
      </div>
      <div className="flex flex-wrap gap-2">
        <Toggle on={filters.needs_action} onClick={() => update({ needs_action: !filters.needs_action })}>
          Needs action
        </Toggle>
        <Toggle on={filters.churn} onClick={() => update({ churn: !filters.churn })}>
          Churn risk
        </Toggle>
        <Toggle on={filters.open_issue} onClick={() => update({ open_issue: !filters.open_issue })}>
          Open issue
        </Toggle>
        <Select label="Segment" value={filters.segment} options={SEGMENTS} onChange={(segment) => update({ segment })} />
        <button type="button" onClick={() => setParams(new URLSearchParams())} className="text-sm text-teal">
          Clear
        </button>
      </div>

      {rows === null && <LoadingBlock />}
      {rows && rows.length === 0 && (
        <div className="rounded-3xl bg-card p-8 text-mute ring-1 ring-line">No customers match these filters.</div>
      )}
      {rows && rows.length > 0 && (
        <div className="overflow-hidden rounded-3xl bg-card shadow-card ring-1 ring-line">
          <div className="hidden grid-cols-[1.4fr_0.8fr_0.9fr_1.5fr_auto] gap-3 border-b border-line px-5 py-3 text-[11px] uppercase tracking-[0.14em] text-mute md:grid">
            <span>Customer</span>
            <span>Value</span>
            <span>Signals</span>
            <span>Next best action</span>
            <span>Priority</span>
          </div>
          {rows.map((row) => (
            <Link
              key={row.id}
              to={`/customers/${row.id}`}
              className="grid gap-3 border-b border-line px-5 py-4 last:border-b-0 hover:bg-paper md:grid-cols-[1.4fr_0.8fr_0.9fr_1.5fr_auto] md:items-center"
            >
              <div className="flex items-center gap-3">
                <Avatar name={row.name} initials={row.initials} />
                <div>
                  <div className="font-medium">{row.name}</div>
                  <div className="text-sm text-mute">
                    {row.id} · {row.city}, {row.region}
                  </div>
                  <div className="text-xs text-mute">
                    {bookLabel(row.book)} · {row.segment} · {row.headline_product}
                  </div>
                </div>
              </div>
              <div>
                <div className="font-medium">{money(row.customer_value)}</div>
                <div className="text-xs text-mute">{row.tenure_months} months</div>
              </div>
              <div className="flex flex-wrap gap-1.5">
                <Pill tone={sentimentTone(row.sentiment)}>{row.sentiment}</Pill>
                <Pill tone={riskTone(row.risk_level)}>{row.risk_level}</Pill>
              </div>
              <div className="text-sm">
                {row.nba.title}
                {row.next_renewal_days !== null && row.next_renewal_days <= 45 && (
                  <div className="mt-1 text-xs text-amber">Renews in {row.next_renewal_days} days</div>
                )}
              </div>
              <Pill tone={priorityTone(row.nba.priority)}>{row.nba.priority === "None" ? "None" : row.nba.priority}</Pill>
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}

function Select({ label, value, options, onChange }: { label: string; value: string; options: string[]; onChange: (value: string) => void }) {
  return (
    <label>
      <span className="mb-1 block text-xs text-mute">{label}</span>
      <select value={value} onChange={(event) => onChange(event.target.value)} className="w-full rounded-2xl border border-line bg-card px-3 py-2.5 text-sm">
        {options.map((option) => (
          <option key={option || "all"} value={option}>
            {option || "All"}
          </option>
        ))}
      </select>
    </label>
  )
}

function Toggle({ on, onClick, children }: { on: boolean; onClick: () => void; children: string }) {
  return (
    <button type="button" onClick={onClick} className={on ? "rounded-full bg-deep px-3 py-2 text-sm text-white" : "rounded-full bg-card px-3 py-2 text-sm ring-1 ring-line"}>
      {children}
    </button>
  )
}
