import { useEffect, useState, type ReactNode } from "react"
import { Link } from "react-router-dom"
import { Bar, BarChart, Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts"
import { getDashboard } from "../api"
import { HowItWorksStrip } from "../components/HowItWorks"
import { ErrorState, Eyebrow, LoadingBlock, Panel, Pill } from "../components/ui"
import { bookLabel, greeting, money, percent, priorityTone, riskTone, sentimentTone } from "../format"
import type { CustomerRow, DashboardData } from "../types"

const SENTIMENT_COLOR: Record<string, string> = {
  Positive: "#1e6b45",
  Neutral: "#c4b49a",
  Negative: "#9d3144",
}
const RISK_COLOR: Record<string, string> = {
  High: "#9d3144",
  Medium: "#8d5b12",
  Low: "#1e6b45",
}

export default function Dashboard() {
  const [data, setData] = useState<DashboardData | null>(null)
  const [error, setError] = useState("")

  function load() {
    setError("")
    getDashboard()
      .then(setData)
      .catch((reason: Error) => setError(reason.message))
  }

  useEffect(() => {
    load()
  }, [])

  if (error) return <ErrorState message={error} onRetry={load} />
  if (!data) return <LoadingBlock />

  const high = data.queue.filter((row) => row.nba.priority === "High").length
  const kpis = [
    { label: "Customers", value: data.kpis.customers, hint: "Insurance, lending, and combined", href: "/customers" },
    { label: "High risk", value: data.kpis.high_risk, hint: "Score 55 or above", href: "/customers?risk=High" },
    { label: "Need action", value: data.kpis.needs_action, hint: "High and medium priority", href: "/customers?needs_action=true" },
    { label: "Negative sentiment", value: data.kpis.negative_sentiment, hint: "Latest conversation", href: "/customers?sentiment=Negative" },
    { label: "Open issues", value: data.kpis.open_issues, hint: "Claims, complaints, requests", href: "/customers?open_issue=true" },
    { label: "Churn risk", value: data.kpis.churn_cases, hint: "Estimated 45% or higher", href: "/customers?churn=true" },
    { label: "Recommended actions", value: data.kpis.recommended_actions, hint: "Anyone but a quiet file", href: "/actions" },
  ]

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <Eyebrow>Northline book</Eyebrow>
          <h1 className="mt-2 font-serif text-4xl tracking-tight md:text-5xl">{greeting()}</h1>
          <p className="mt-3 max-w-2xl text-mute">
            {high} high-priority actions are waiting. Policies, loans, and transcripts sit on one file, and every recommendation names the evidence.
          </p>
        </div>
      </div>

      <HowItWorksStrip />

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {kpis.map((kpi) => (
          <Link key={kpi.label} to={kpi.href} className="rounded-3xl bg-card px-4 py-4 shadow-card ring-1 ring-line transition hover:-translate-y-0.5">
            <Eyebrow>{kpi.label}</Eyebrow>
            <div className="mt-2 font-serif text-4xl">{kpi.value}</div>
            <div className="mt-1 text-sm text-mute">{kpi.hint}</div>
          </Link>
        ))}
      </div>

      <section>
        <div className="mb-3 flex items-end justify-between">
          <h2 className="font-serif text-2xl">Demo stories</h2>
          <span className="text-sm text-mute">Six files worth opening first</span>
        </div>
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {data.stories.map((story) => (
            <Link key={story.id} to={`/customers/${story.id}`} className="rounded-3xl bg-card p-5 shadow-card ring-1 ring-line transition hover:-translate-y-0.5">
              <Eyebrow>{story.story?.kicker}</Eyebrow>
              <div className="mt-2 font-serif text-2xl leading-tight">{story.story?.title}</div>
              <p className="mt-2 text-sm leading-6 text-mute">{story.story?.blurb}</p>
              <div className="mt-4 flex flex-wrap items-center gap-2 text-sm">
                <span className="font-medium">{story.name}</span>
                <Pill tone={priorityTone(story.nba.priority)}>{story.nba.priority === "None" ? "No action" : `${story.nba.priority} priority`}</Pill>
              </div>
            </Link>
          ))}
        </div>
      </section>

      <section className="grid gap-4 lg:grid-cols-2">
        <ChartCard title="Sentiment" subtitle="Latest customer-facing conversation">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie data={data.charts.sentiment} dataKey="value" nameKey="label" innerRadius={58} outerRadius={84} paddingAngle={2} stroke="none">
                {data.charts.sentiment.map((entry) => (
                  <Cell key={entry.label} fill={SENTIMENT_COLOR[entry.label] ?? "#0e6b64"} />
                ))}
              </Pie>
              <Tooltip />
              <Legend />
            </PieChart>
          </ResponsiveContainer>
        </ChartCard>
        <ChartCard title="Risk" subtitle="Score from open issues, payments, and language">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data.charts.risk}>
              <XAxis dataKey="label" tick={{ fill: "#5d6b7a", fontSize: 12 }} axisLine={false} tickLine={false} />
              <YAxis allowDecimals={false} tick={{ fill: "#5d6b7a", fontSize: 12 }} axisLine={false} tickLine={false} width={28} />
              <Tooltip />
              <Bar dataKey="value" radius={[8, 8, 0, 0]}>
                {data.charts.risk.map((entry) => (
                  <Cell key={entry.label} fill={RISK_COLOR[entry.label] ?? "#0e6b64"} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>
        <ChartCard title="Segments" subtitle="How the book is split">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data.charts.segments}>
              <XAxis dataKey="label" tick={{ fill: "#5d6b7a", fontSize: 12 }} axisLine={false} tickLine={false} />
              <YAxis allowDecimals={false} tick={{ fill: "#5d6b7a", fontSize: 12 }} axisLine={false} tickLine={false} width={28} />
              <Tooltip />
              <Bar dataKey="value" fill="#0e6b64" radius={[8, 8, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>
        <ChartCard title="Actions" subtitle="What the engine wants done">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data.charts.actions} layout="vertical" margin={{ left: 16, right: 8 }}>
              <XAxis type="number" hide />
              <YAxis type="category" dataKey="label" width={108} tick={{ fill: "#5d6b7a", fontSize: 12 }} axisLine={false} tickLine={false} />
              <Tooltip />
              <Bar dataKey="value" fill="#10262c" radius={[0, 8, 8, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>
      </section>

      <section>
        <div className="mb-3 flex items-end justify-between">
          <h2 className="font-serif text-2xl">Action queue</h2>
          <Link to="/actions" className="text-sm text-teal">
            Open the full queue
          </Link>
        </div>
        <Panel className="overflow-hidden p-0">
          <div className="divide-y divide-line">
            {data.queue.slice(0, 8).map((row) => (
              <QueueRow key={row.id} row={row} />
            ))}
          </div>
        </Panel>
      </section>
    </div>
  )
}

function ChartCard({ title, subtitle, children }: { title: string; subtitle: string; children: ReactNode }) {
  return (
    <Panel>
      <Eyebrow>{title}</Eyebrow>
      <p className="mt-1 text-sm text-mute">{subtitle}</p>
      <div className="mt-2 h-64">{children}</div>
    </Panel>
  )
}

function QueueRow({ row }: { row: CustomerRow }) {
  return (
    <Link to={`/customers/${row.id}`} className="grid gap-3 px-5 py-4 hover:bg-paper md:grid-cols-[1.2fr_1.4fr_auto] md:items-center">
      <div>
        <div className="font-medium">{row.name}</div>
        <div className="text-sm text-mute">
          {row.city} · {bookLabel(row.book)} · {money(row.customer_value)}
        </div>
      </div>
      <div>
        <div className="text-sm">{row.nba.title}</div>
        <div className="mt-1 text-xs text-mute">{row.nba.evidence_preview}</div>
      </div>
      <div className="flex flex-wrap gap-2">
        <Pill tone={priorityTone(row.nba.priority)}>{row.nba.priority}</Pill>
        <Pill tone={sentimentTone(row.sentiment)}>{row.sentiment}</Pill>
        <Pill tone={riskTone(row.risk_level)}>{row.risk_level} risk</Pill>
        <span className="text-xs text-mute">{percent(row.churn_probability)} churn</span>
      </div>
    </Link>
  )
}
