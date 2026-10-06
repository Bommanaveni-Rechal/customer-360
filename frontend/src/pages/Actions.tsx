import { useEffect, useState } from "react"
import { Link } from "react-router-dom"
import { getActions } from "../api"
import { ErrorState, Eyebrow, LoadingBlock, Panel, Pill } from "../components/ui"
import { bookLabel, priorityTone } from "../format"
import type { CustomerRow } from "../types"

const GROUPS = ["High", "Medium", "Low"]

export default function Actions() {
  const [rows, setRows] = useState<CustomerRow[] | null>(null)
  const [error, setError] = useState("")

  function load() {
    setError("")
    getActions()
      .then((result) => setRows(result.actions))
      .catch((reason: Error) => setError(reason.message))
  }

  useEffect(() => {
    load()
  }, [])

  if (error) return <ErrorState message={error} onRetry={load} />
  if (!rows) return <LoadingBlock />

  return (
    <div className="space-y-8">
      <div>
        <Eyebrow>Action queue</Eyebrow>
        <h1 className="mt-2 font-serif text-4xl">Work the files that can still move</h1>
        <p className="mt-3 max-w-2xl text-mute">Each item is a customer, not a task ticket. Open the file to see the evidence, then record what you did.</p>
      </div>
      {GROUPS.map((priority) => {
        const items = rows.filter((row) => row.nba.priority === priority)
        if (items.length === 0) return null
        return (
          <section key={priority}>
            <div className="mb-3 flex items-center gap-2">
              <h2 className="font-serif text-2xl">{priority} priority</h2>
              <span className="text-sm text-mute">{items.length}</span>
            </div>
            <div className="space-y-3">
              {items.map((row) => (
                <Panel key={row.id} className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
                  <div>
                    <div className="flex flex-wrap items-center gap-2">
                      <Pill tone={priorityTone(row.nba.priority)}>{priority}</Pill>
                      <span className="text-sm text-mute">
                        {row.name} · {row.city} · {bookLabel(row.book)}
                      </span>
                    </div>
                    <h3 className="mt-2 font-serif text-2xl">{row.nba.title}</h3>
                    <p className="mt-2 max-w-3xl text-sm leading-6 text-mute">{row.nba.reason}</p>
                    {row.nba.evidence_preview && <p className="mt-2 text-sm">{row.nba.evidence_preview}</p>}
                  </div>
                  <Link to={`/customers/${row.id}`} className="shrink-0 rounded-full bg-deep px-4 py-2 text-center text-sm text-white">
                    Open file
                  </Link>
                </Panel>
              ))}
            </div>
          </section>
        )
      })}
    </div>
  )
}
