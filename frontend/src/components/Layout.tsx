import { CircleHelp, LayoutDashboard, ListChecks, Menu, RotateCcw, Search, Users, X } from "lucide-react"
import { useEffect, useState } from "react"
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom"
import { getHealth, getCustomers, resetDemo } from "../api"
import { HowItWorksModal } from "./HowItWorks"
import { SCENARIOS, cn } from "../format"
import type { CustomerRow } from "../types"

const NAV = [
  { to: "/", label: "Overview", icon: LayoutDashboard, end: true },
  { to: "/customers", label: "Customers", icon: Users, end: false },
  { to: "/actions", label: "Action queue", icon: ListChecks, end: false },
]

export default function Layout() {
  const location = useLocation()
  const navigate = useNavigate()
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState("")
  const [hits, setHits] = useState<CustomerRow[]>([])
  const [searching, setSearching] = useState(false)
  const [aiMode, setAiMode] = useState("rules")
  const [confirmReset, setConfirmReset] = useState(false)
  const [resetting, setResetting] = useState(false)
  const [howOpen, setHowOpen] = useState(false)
  const scenario = SCENARIOS.find((item) => location.pathname === `/customers/${item.customerId}`)?.id ?? ""

  useEffect(() => {
    setOpen(false)
    setQuery("")
    setHits([])
  }, [location.pathname])

  useEffect(() => {
    getHealth()
      .then((health) => setAiMode(health.ai_mode))
      .catch(() => setAiMode("offline"))
  }, [location.pathname])

  useEffect(() => {
    if (query.trim().length < 2) {
      setHits([])
      return
    }
    const handle = window.setTimeout(() => {
      setSearching(true)
      getCustomers({ q: query.trim() })
        .then((result) => setHits(result.customers.slice(0, 6)))
        .catch(() => setHits([]))
        .finally(() => setSearching(false))
    }, 200)
    return () => window.clearTimeout(handle)
  }, [query])

  async function onReset() {
    setResetting(true)
    try {
      await resetDemo()
      window.location.href = "/"
    } finally {
      setResetting(false)
    }
  }

  return (
    <div className="min-h-screen lg:flex">
      {open && <button type="button" aria-label="Close menu" className="fixed inset-0 z-30 bg-ink/40 lg:hidden" onClick={() => setOpen(false)} />}
      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-40 flex w-[260px] flex-col bg-deep px-4 py-5 text-white transition-transform lg:static lg:translate-x-0",
          open ? "translate-x-0" : "-translate-x-full",
        )}
      >
        <NavLink to="/" className="flex items-center gap-3 px-2">
          <span className="grid h-10 w-10 place-items-center rounded-xl bg-teal font-serif text-xl">C</span>
          <span>
            <span className="block text-lg font-medium tracking-tight">Customer-360</span>
          </span>
        </NavLink>
        <nav className="mt-8 space-y-1">
          {NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                cn(
                  "flex items-center gap-3 rounded-2xl px-3 py-2.5 text-sm",
                  isActive ? "bg-white/10 text-white" : "text-white/65 hover:bg-white/5 hover:text-white",
                )
              }
            >
              <item.icon size={18} />
              {item.label}
            </NavLink>
          ))}
        </nav>
        <div className="mt-auto space-y-3 px-2 pb-2">
          <div className="rounded-2xl bg-white/5 px-3 py-3 text-xs leading-5 text-white/70">
            {aiMode === "llm" ? "Language model connected for questions and re-reads." : aiMode === "offline" ? "API offline. Start the backend on port 8000." : "Rules engine active. No API key required."}
          </div>
          <button type="button" onClick={() => setHowOpen(true)} className="flex items-center gap-2 text-xs text-white/55 hover:text-white">
            <CircleHelp size={14} />
            How Customer-360 works
          </button>
          <button type="button" onClick={() => setConfirmReset(true)} className="flex items-center gap-2 text-xs text-white/55 hover:text-white">
            <RotateCcw size={14} />
            Reset demo data
          </button>
        </div>
      </aside>

      <div className="min-w-0 flex-1">
        <header className="sticky top-0 z-20 border-b border-line/80 bg-paper/90 px-4 py-3 backdrop-blur md:px-8">
          <div className="flex flex-wrap items-center gap-3">
            <button type="button" className="grid h-10 w-10 place-items-center rounded-xl bg-card ring-1 ring-line lg:hidden" onClick={() => setOpen(true)} aria-label="Open menu">
              <Menu size={18} />
            </button>
            <form
              className="relative min-w-0 flex-1"
              onSubmit={(event) => {
                event.preventDefault()
                if (hits[0]) navigate(`/customers/${hits[0].id}`)
              }}
            >
              <Search size={16} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-mute" />
              <input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Search a customer, policy, loan, or claim"
                aria-label="Search customers"
                className="w-full rounded-2xl border border-line bg-card py-2.5 pl-10 pr-4 text-sm outline-none"
              />
              {query.trim().length >= 2 && (
                <div className="absolute left-0 right-0 top-12 overflow-hidden rounded-2xl bg-card shadow-card ring-1 ring-line">
                  {searching && <div className="px-4 py-3 text-sm text-mute">Searching the book…</div>}
                  {!searching && hits.length === 0 && <div className="px-4 py-3 text-sm text-mute">No matching customer.</div>}
                  {hits.map((hit) => (
                    <button
                      key={hit.id}
                      type="button"
                      onClick={() => navigate(`/customers/${hit.id}`)}
                      className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left hover:bg-paper"
                    >
                      <span>
                        <span className="block text-sm font-medium">{hit.name}</span>
                        <span className="block text-xs text-mute">
                          {hit.id} · {hit.city} · {hit.headline_product}
                        </span>
                      </span>
                      <span className="text-xs text-mute">{hit.nba.priority === "None" ? "No action" : hit.nba.priority}</span>
                    </button>
                  ))}
                </div>
              )}
            </form>
            <label className="sr-only" htmlFor="demo-scenarios">
              Demo scenarios
            </label>
            <select
              id="demo-scenarios"
              aria-label="Demo scenarios"
              value={scenario}
              onChange={(event) => {
                const next = SCENARIOS.find((item) => item.id === event.target.value)
                if (next) navigate(`/customers/${next.customerId}`)
              }}
              className="shrink-0 rounded-2xl border border-line bg-card px-3 py-2.5 text-sm outline-none"
            >
              <option value="">Demo scenarios</option>
              {SCENARIOS.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.label}
                </option>
              ))}
            </select>
          </div>
        </header>
        <main className="px-4 py-6 md:px-8 md:py-8">
          <div className="mx-auto max-w-[1200px]">
            <Outlet />
          </div>
        </main>
      </div>

      <HowItWorksModal open={howOpen} onClose={() => setHowOpen(false)} />

      {confirmReset && (
        <div className="fixed inset-0 z-50 grid place-items-center bg-ink/40 p-4">
          <div role="dialog" aria-modal="true" className="w-full max-w-md rounded-3xl bg-card p-6 shadow-card">
            <div className="flex items-start justify-between gap-4">
              <h2 className="font-serif text-2xl">Reset the demo book?</h2>
              <button type="button" aria-label="Close" onClick={() => setConfirmReset(false)}>
                <X size={18} />
              </button>
            </div>
            <p className="mt-3 text-sm leading-6 text-mute">Recorded actions and case updates will be cleared. The 28 seeded customers come back as they were.</p>
            <div className="mt-5 flex justify-end gap-2">
              <button type="button" onClick={() => setConfirmReset(false)} className="rounded-full px-4 py-2 text-sm">
                Cancel
              </button>
              <button type="button" disabled={resetting} onClick={onReset} className="rounded-full bg-deep px-4 py-2 text-sm text-white disabled:opacity-60">
                {resetting ? "Resetting…" : "Reset demo"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
