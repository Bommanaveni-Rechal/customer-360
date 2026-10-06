import { Briefcase, ChevronDown, Mail, MapPin, Phone, X } from "lucide-react"
import { useEffect, useState } from "react"
import { Link, useParams } from "react-router-dom"
import { askCustomer, getCustomer, recordAction, recordOutcome, rereadCustomer, updateCase } from "../api"
import { ErrorState, Eyebrow, LoadingBlock, Panel, Pill } from "../components/ui"
import {
  ACTION_OPTIONS,
  QUESTIONS,
  RESULT_OPTIONS,
  bookLabel,
  money,
  percent,
  prettyDate,
  priorityTone,
  relativeDay,
  riskTone,
  sentimentTone,
} from "../format"
import type { Answer, CustomerDetail, ServiceCase, TimelineItem } from "../types"

export default function Customer360() {
  const { id } = useParams()
  const [data, setData] = useState<CustomerDetail | null>(null)
  const [error, setError] = useState("")
  const [expanded, setExpanded] = useState<string | null>(null)
  const [highlight, setHighlight] = useState<string | null>(null)
  const [banner, setBanner] = useState("")
  const [showPayments, setShowPayments] = useState(false)
  const [modal, setModal] = useState(false)
  const [saving, setSaving] = useState(false)
  const [formError, setFormError] = useState("")
  const [form, setForm] = useState({
    action_type: "retention_call",
    title: "",
    outcome: "Completed",
    note: "",
    owner: "Relationship manager",
    due_on: "",
    priority: "High",
    result: "",
  })
  const [question, setQuestion] = useState("")
  const [asking, setAsking] = useState(false)
  const [messages, setMessages] = useState<Answer[]>([])
  const [rereading, setRereading] = useState(false)
  const [pendingCase, setPendingCase] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)

  useEffect(() => {
    if (!id) return
    setData(null)
    setMessages([])
    setBanner("")
    setError("")
    setHighlight(null)
    setExpanded(null)
    getCustomer(id)
      .then(setData)
      .catch((reason: Error) => setError(reason.message))
  }, [id])

  if (!id) return null
  if (error) {
    return (
      <ErrorState
        message={error}
        onRetry={() => {
          setError("")
          getCustomer(id)
            .then(setData)
            .catch((reason: Error) => setError(reason.message))
        }}
      />
    )
  }
  if (!data) return <LoadingBlock />

  const customer = data.customer
  const nba = data.nba
  const calm = nba.action_type === "no_action"
  const payments = showPayments ? data.payments : data.payments.slice(0, 6)
  const riskColor = data.risk.level === "High" ? "#9d3144" : data.risk.level === "Medium" ? "#8d5b12" : "#1e6b45"

  function dueIn(days: number) {
    const date = new Date()
    date.setDate(date.getDate() + days)
    return date.toISOString().slice(0, 10)
  }

  function openAction() {
    const outcome: string = nba.action_type === "no_action" ? "Dismissed" : "Completed"
    setForm({
      action_type: nba.action_type,
      title: nba.title,
      outcome,
      note: nba.suggested_note,
      owner: "Relationship manager",
      due_on: dueIn(outcome === "Scheduled" ? 3 : 0),
      priority: nba.priority === "None" ? "Low" : nba.priority,
      result: "",
    })
    setFormError("")
    setModal(true)
  }

  function focusEvidence(timelineId: string | null, delay = 50) {
    if (!timelineId) return
    setExpanded(timelineId)
    setHighlight(timelineId)
    window.setTimeout(() => {
      document.getElementById(`timeline-${timelineId}`)?.scrollIntoView({ behavior: "smooth", block: "center" })
    }, delay)
  }

  async function submitAction() {
    setSaving(true)
    setFormError("")
    try {
      const next = await recordAction(id!, { ...form, due_on: form.due_on || null, result: form.outcome === "Completed" ? form.result : "" })
      setData(next)
      setModal(false)
      const saved = next.actions[0]
      const shift = saved?.risk_before && saved.risk_after && saved.risk_before !== saved.risk_after ? ` ${saved.risk_before} risk → ${saved.risk_after} risk.` : ""
      const moved = saved?.nba_before && saved.nba_after && saved.nba_before !== saved.nba_after ? " The recommendation was recalculated." : ""
      setBanner(`Action recorded. It is now on the timeline.${shift}${moved}`)
      if (saved) focusEvidence(`action-${saved.id}`, 200)
    } catch (reason) {
      setFormError(reason instanceof Error ? reason.message : "Could not record the action.")
    } finally {
      setSaving(false)
    }
  }

  async function saveOutcome(actionId: number, result: string) {
    setSaving(true)
    try {
      const next = await recordOutcome(actionId, result)
      setData(next)
      const saved = next.actions.find((item) => item.id === actionId)
      const shift = saved?.risk_before && saved.risk_after ? ` ${saved.risk_before} risk → ${saved.risk_after} risk.` : ""
      const moved = saved?.nba_before && saved.nba_after && saved.nba_before !== saved.nba_after ? " The recommendation was recalculated." : ""
      setBanner(`Outcome recorded.${shift}${moved}`)
    } catch (reason) {
      setBanner(reason instanceof Error ? reason.message : "Could not record the outcome.")
    } finally {
      setSaving(false)
    }
  }

  async function resolveCase(caseId: string) {
    setSaving(true)
    try {
      const next = await updateCase(caseId, "Resolved")
      setData(next)
      setPendingCase(null)
      setBanner("Case marked resolved. The next best action was recalculated from the file.")
    } catch (reason) {
      setBanner(reason instanceof Error ? reason.message : "Could not update the case.")
    } finally {
      setSaving(false)
    }
  }

  async function reread() {
    setRereading(true)
    try {
      const next = await rereadCustomer(id!)
      setData(next)
      setBanner(next.insights.source === "llm" ? "Interactions re-read with the language model." : "Interactions re-read with the rules engine.")
    } catch (reason) {
      setBanner(reason instanceof Error ? reason.message : "Could not re-read the file.")
    } finally {
      setRereading(false)
    }
  }

  async function ask(text: string) {
    const cleaned = text.trim()
    if (!cleaned) return
    setAsking(true)
    setQuestion("")
    try {
      const answer = await askCustomer(id!, cleaned)
      setMessages((current) => [...current, answer])
    } catch (reason) {
      setMessages((current) => [
        ...current,
        {
          question: cleaned,
          answer: reason instanceof Error ? reason.message : "The question failed.",
          recommended_action: nba.title,
          priority: nba.priority,
          source: "rules",
        },
      ])
    } finally {
      setAsking(false)
    }
  }

  return (
    <div className="space-y-6">
      <Link to="/customers" className="text-sm text-teal">
        Back to the book
      </Link>

      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="flex flex-wrap items-center gap-2 text-sm text-mute">
            <span>{customer.id}</span>
            <button
              type="button"
              className="text-teal"
              onClick={() => {
                const write = navigator.clipboard?.writeText(customer.id)
                if (!write) return
                write
                  .then(() => {
                    setCopied(true)
                    window.setTimeout(() => setCopied(false), 1200)
                  })
                  .catch(() => setCopied(false))
              }}
            >
              {copied ? "Copied" : "Copy ID"}
            </button>
          </div>
          <h1 className="mt-1 font-serif text-4xl tracking-tight md:text-5xl">{customer.name}</h1>
          <p className="mt-2 text-mute">
            {customer.occupation} · {customer.city}, {customer.region} · {bookLabel(customer.book)} · {customer.segment}
          </p>
          <div className="mt-4 flex flex-wrap gap-2">
            <Pill tone={riskTone(data.risk.level)}>{data.risk.level} risk</Pill>
            <Pill tone={sentimentTone(data.insights.sentiment)}>{data.insights.sentiment}</Pill>
            <Pill tone="teal">{money(customer.customer_value)} value</Pill>
            {customer.high_value && <Pill tone="amber">High value</Pill>}
            {data.next_renewal_days !== null && <Pill tone="slate">Renews in {data.next_renewal_days} days</Pill>}
            <Pill tone={priorityTone(nba.priority)}>{nba.priority === "None" ? "No action" : `${nba.priority} priority`}</Pill>
          </div>
        </div>
        <button type="button" onClick={openAction} className="rounded-full bg-deep px-5 py-2.5 text-sm text-white">
          Record action
        </button>
      </header>

      {banner && <div className="rounded-2xl bg-mist px-4 py-3 text-sm text-teal">{banner}</div>}

      <section className={calm ? "rounded-3xl bg-card p-6 shadow-card ring-1 ring-line md:p-8" : "rounded-3xl bg-deep p-6 text-white shadow-card md:p-8"}>
        <div className="flex flex-wrap items-end justify-between gap-3">
          <Eyebrow>
            <span className={calm ? "" : "text-white/60"}>{nba.priority === "None" ? "No outreach" : `${nba.priority} priority`}</span>
          </Eyebrow>
          <div className={calm ? "text-right" : "text-right text-white"}>
            <div className="font-serif text-3xl">{nba.confidence}%</div>
            <div className={calm ? "text-xs text-mute" : "text-xs text-white/60"}>{nba.confidence_note}</div>
          </div>
        </div>
        <h2 className="mt-2 max-w-3xl font-serif text-3xl leading-tight md:text-4xl">{nba.title}</h2>
        <p className={calm ? "mt-4 max-w-3xl leading-7 text-mute" : "mt-4 max-w-3xl leading-7 text-white/80"}>{nba.reason}</p>
        <p className={calm ? "mt-3 max-w-3xl text-sm leading-6 text-mute" : "mt-3 max-w-3xl text-sm leading-6 text-white/70"}>{nba.selection}</p>
        <div className="mt-6 grid gap-6 md:grid-cols-2">
          <div>
            <div className={calm ? "text-[11px] uppercase tracking-[0.16em] text-mute" : "text-[11px] uppercase tracking-[0.16em] text-white/50"}>Expected impact</div>
            <p className="mt-2 text-sm leading-6">{nba.expected_impact}</p>
          </div>
          <div>
            <div className={calm ? "text-[11px] uppercase tracking-[0.16em] text-mute" : "text-[11px] uppercase tracking-[0.16em] text-white/50"}>How to open</div>
            <p className="mt-2 text-sm leading-6">{nba.talk_track}</p>
          </div>
        </div>
        <div className="mt-6 grid gap-6 lg:grid-cols-2">
          <div>
            <div className={calm ? "text-[11px] uppercase tracking-[0.16em] text-mute" : "text-[11px] uppercase tracking-[0.16em] text-white/50"}>Evidence</div>
            <ul className="mt-2 space-y-2 text-sm leading-6">
              {(nba.evidence_links?.length ? nba.evidence_links : nba.evidence.map((text) => ({ text, timeline_id: null }))).map((item) => (
                <li key={item.text}>
                  <button
                    type="button"
                    disabled={!item.timeline_id}
                    onClick={() => focusEvidence(item.timeline_id)}
                    className={
                      calm
                        ? "border-l-2 border-teal pl-3 text-left enabled:hover:underline disabled:cursor-default"
                        : "border-l-2 border-white/30 pl-3 text-left enabled:hover:underline disabled:cursor-default"
                    }
                  >
                    {item.text}
                  </button>
                </li>
              ))}
            </ul>
          </div>
          <div>
            <div className={calm ? "text-[11px] uppercase tracking-[0.16em] text-mute" : "text-[11px] uppercase tracking-[0.16em] text-white/50"}>Why this action</div>
            <ol className="mt-2 space-y-2 text-sm leading-6">
              {nba.reasoning.map((item, index) => (
                <li key={item}>
                  {index + 1}. {item}
                </li>
              ))}
            </ol>
          </div>
        </div>
        {nba.alternatives?.length > 0 && (
          <div className="mt-6">
            <div className={calm ? "text-[11px] uppercase tracking-[0.16em] text-mute" : "text-[11px] uppercase tracking-[0.16em] text-white/50"}>Considered alternatives</div>
            <ul className="mt-2 space-y-2 text-sm leading-6">
              {nba.alternatives.map((item) => (
                <li key={item.action_type} className={calm ? "text-mute" : "text-white/80"}>
                  <span className={calm ? "font-medium text-ink" : "font-medium text-white"}>{item.title}.</span> {item.reason}
                </li>
              ))}
            </ul>
          </div>
        )}
        <button type="button" onClick={openAction} className={calm ? "mt-6 rounded-full bg-deep px-4 py-2 text-sm text-white" : "mt-6 rounded-full bg-white px-4 py-2 text-sm text-deep"}>
          Record this action
        </button>
      </section>

      <div className="grid gap-4 lg:grid-cols-3">
        <Panel>
          <Eyebrow>Customer profile</Eyebrow>
          <dl className="mt-4 space-y-3 text-sm">
            <Row label="Name" value={customer.name} />
            <Row label="Age" value={String(customer.age)} />
            <Row label="Location" value={`${customer.city}, ${customer.region}`} />
            <Row label="Occupation" value={customer.occupation} />
            <Row label="Tenure" value={customer.tenure_label} />
            <Row label="Joined" value={prettyDate(customer.joined_on)} />
            <Row label="Segment" value={customer.segment} />
            <Row label="Book" value={bookLabel(customer.book)} />
          </dl>
          <div className="mt-5 space-y-2 text-sm">
            <a className="flex items-center gap-2 text-teal" href={`mailto:${customer.email}`}>
              <Mail size={15} /> {customer.email}
            </a>
            <a className="flex items-center gap-2 text-teal" href={`tel:${customer.phone}`}>
              <Phone size={15} /> {customer.phone}
            </a>
            <div className="flex items-center gap-2 text-mute">
              <MapPin size={15} /> {customer.city}, {customer.region}
            </div>
            <div className="flex items-center gap-2 text-mute">
              <Briefcase size={15} /> {customer.occupation}
            </div>
          </div>
          <div className="mt-5">
            <div className="flex items-center justify-between text-xs text-mute">
              <span>Risk score {data.risk.score}</span>
              <span>{percent(data.risk.churn_probability)} churn</span>
            </div>
            <div className="mt-2 h-1.5 rounded-full bg-[#efeae2]">
              <div className="h-1.5 rounded-full" style={{ width: `${data.risk.score}%`, background: riskColor }} />
            </div>
            <ul className="mt-3 space-y-2 text-sm leading-6 text-mute">
              {data.risk.factors.map((factor) => (
                <li key={factor}>{factor}</li>
              ))}
            </ul>
          </div>
        </Panel>

        <Panel className="lg:col-span-2">
          <Eyebrow>Financial and product relationship</Eyebrow>
          <div className="mt-4 grid gap-3 md:grid-cols-2">
            {data.products.map((product) => (
              <div key={product.id} className="rounded-2xl bg-paper p-4">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="text-xs text-mute">{product.kind === "Loan" ? "Loan" : "Policy"} · {product.number}</div>
                    <div className="mt-1 font-medium">{product.name}</div>
                  </div>
                  <Pill tone={product.health === "Overdue" || product.health === "Lapsed" ? "rose" : product.health === "Renewal due" ? "amber" : "moss"}>{product.health}</Pill>
                </div>
                <div className="mt-4 grid grid-cols-2 gap-3 text-sm">
                  <div>
                    <div className="text-xs text-mute">{product.kind === "Loan" ? "EMI" : "Premium"}</div>
                    <div>{money(product.installment)} / {product.frequency.toLowerCase()}</div>
                  </div>
                  <div>
                    <div className="text-xs text-mute">{product.kind === "Loan" ? "Outstanding" : "Limit / cover"}</div>
                    <div>{money(product.kind === "Loan" ? product.outstanding : product.cover)}</div>
                  </div>
                  <div>
                    <div className="text-xs text-mute">{product.kind === "Loan" ? "Next due" : "Renewal"}</div>
                    <div>{product.kind === "Loan" ? prettyDate(product.next_due_on) : product.renewal_in_days === null ? "—" : product.renewal_in_days < 0 ? "Lapsed" : `${product.renewal_in_days} days`}</div>
                  </div>
                  <div>
                    <div className="text-xs text-mute">Since</div>
                    <div>{prettyDate(product.started_on)}</div>
                  </div>
                </div>
              </div>
            ))}
          </div>

          <div className="mt-6">
            <h3 className="text-sm font-medium">Claims and service history</h3>
            {data.cases.length === 0 && <p className="mt-2 text-sm text-mute">No claims, complaints, or service requests.</p>}
            <div className="mt-3 space-y-3">
              {data.cases.map((item) => (
                <CaseRow key={item.id} item={item} pending={pendingCase === item.id} saving={saving} onAsk={() => setPendingCase(item.id)} onCancel={() => setPendingCase(null)} onResolve={() => resolveCase(item.id)} />
              ))}
            </div>
          </div>

          <div className="mt-6">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-medium">Payment history</h3>
              {data.payments.length > 6 && (
                <button type="button" className="text-sm text-teal" onClick={() => setShowPayments((value) => !value)}>
                  {showPayments ? "Show recent" : "Show full ledger"}
                </button>
              )}
            </div>
            <div className="mt-3 overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="text-xs uppercase tracking-wide text-mute">
                  <tr>
                    <th className="py-2 font-medium">Date</th>
                    <th className="py-2 font-medium">Product</th>
                    <th className="py-2 font-medium">Amount</th>
                    <th className="py-2 font-medium">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {payments.map((payment) => (
                    <tr key={payment.id} className="border-t border-line">
                      <td className="py-2">{prettyDate(payment.paid_on)}</td>
                      <td className="py-2">{payment.product_name}</td>
                      <td className="py-2">{money(payment.amount)}</td>
                      <td className="py-2">
                        <Pill tone={payment.status === "Paid" ? "moss" : payment.status === "Late" ? "amber" : "rose"}>{payment.status}</Pill>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </Panel>
      </div>

      <Panel>
        <div className="flex flex-wrap items-end justify-between gap-3">
          <Eyebrow>Sources</Eyebrow>
          <p className="text-xs text-mute">
            Last updated {prettyDate(data.sources.last_updated)} · {data.sources.analyzed_interactions} interaction{data.sources.analyzed_interactions === 1 ? "" : "s"} analyzed
          </p>
        </div>
        <div className="mt-4 flex flex-wrap gap-2">
          {data.sources.items.map((item) => (
            <span key={item.name} className={item.count ? "rounded-full bg-paper px-3 py-1.5 text-sm" : "rounded-full bg-paper px-3 py-1.5 text-sm text-mute"}>
              {item.name} · {item.count}
            </span>
          ))}
        </div>
      </Panel>

      <Panel>
        <Eyebrow>Interaction timeline</Eyebrow>
        <p className="mt-2 text-sm text-mute">Calls, emails, complaints, service events, and actions you record.</p>
        <ol className="mt-5 space-y-3">
          {data.timeline.map((item) => (
            <TimelineRow
              key={item.id}
              item={item}
              open={expanded === item.id}
              highlighted={highlight === item.id}
              onToggle={() => {
                setExpanded(expanded === item.id ? null : item.id)
                setHighlight(item.id)
              }}
            />
          ))}
        </ol>
      </Panel>

      <div className="grid gap-4 lg:grid-cols-5">
        <Panel className="lg:col-span-2">
          <div className="flex items-start justify-between gap-3">
            <div>
              <Eyebrow>AI insights</Eyebrow>
              <p className="mt-1 text-xs text-mute">{data.insights.source === "llm" ? "Re-read by a language model" : data.insights.source === "mixed" ? "Mixed rules and model readings" : "Deterministic reading of the transcripts"}</p>
            </div>
            <button type="button" disabled={rereading} onClick={reread} className="rounded-full px-3 py-1.5 text-xs ring-1 ring-line disabled:opacity-60">
              {rereading ? "Reading…" : "Re-read interactions"}
            </button>
          </div>
          <p className="mt-4 text-sm leading-7">{data.insights.summary}</p>
          <div className="mt-4 flex flex-wrap gap-2">
            <Pill tone={sentimentTone(data.insights.sentiment)}>{data.insights.sentiment}</Pill>
            {data.insights.trend && <Pill tone="slate">{data.insights.trend}</Pill>}
            <Pill tone="teal">{data.insights.intent}</Pill>
            <Pill tone={data.insights.urgency === "High" ? "rose" : data.insights.urgency === "Medium" ? "amber" : "slate"}>{data.insights.urgency} urgency</Pill>
          </div>
          <InsightList title="Main concerns" items={data.insights.concerns} empty="No strong concern extracted." />
          <InsightList title="Churn indicators" items={data.insights.churn_indicators} empty="No churn language on the file." />
          <InsightList title="Extracted facts" items={data.insights.facts} empty="No facts extracted." />
          {data.insights.topics.length > 0 && (
            <div className="mt-4 flex flex-wrap gap-2">
              {data.insights.topics.map((topic) => (
                <Pill key={topic} tone="slate">{topic}</Pill>
              ))}
            </div>
          )}
        </Panel>

        <Panel className="lg:col-span-3">
          <Eyebrow>Ask about this customer</Eyebrow>
          <p className="mt-2 text-sm text-mute">Answers use this file only, and end with a practical action.</p>
          <div className="mt-4 flex flex-wrap gap-2">
            {QUESTIONS.map((item) => (
              <button key={item} type="button" disabled={asking} onClick={() => ask(item)} className="rounded-full bg-paper px-3 py-1.5 text-left text-xs ring-1 ring-line hover:bg-mist disabled:opacity-50">
                {item}
              </button>
            ))}
          </div>
          <form
            className="mt-4 flex gap-2"
            onSubmit={(event) => {
              event.preventDefault()
              void ask(question)
            }}
          >
            <input
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              placeholder="Ask a question about this file"
              aria-label="Question about this customer"
              className="min-w-0 flex-1 rounded-2xl border border-line bg-paper px-3 py-2.5 text-sm"
            />
            <button type="submit" disabled={asking || question.trim().length < 2} className="rounded-full bg-deep px-4 py-2 text-sm text-white disabled:opacity-50">
              {asking ? "Reading…" : "Ask"}
            </button>
          </form>
          <div className="mt-5 space-y-4">
            {messages.length === 0 && <p className="text-sm text-mute">Nothing asked yet. Try “Why is this customer at risk?”</p>}
            {messages.map((message, index) => (
              <article key={`${message.question}-${index}`} className="rounded-2xl bg-paper p-4">
                <div className="text-xs uppercase tracking-[0.14em] text-mute">{message.question}</div>
                <p className="mt-2 whitespace-pre-wrap text-sm leading-7">{message.answer}</p>
                <div className="mt-3 flex flex-wrap items-center gap-2">
                  <Pill tone={priorityTone(message.priority)}>{message.recommended_action}</Pill>
                  <span className="text-xs text-mute">{message.source === "llm" ? "Language model" : "Rules engine"}</span>
                </div>
              </article>
            ))}
          </div>
        </Panel>
      </div>

      {data.actions.length > 0 && (
        <Panel>
          <Eyebrow>Actions on file</Eyebrow>
          <ul className="mt-3 space-y-3">
            {data.actions.map((action) => (
              <li key={action.id} className="rounded-2xl bg-paper p-4 text-sm">
                <div className="font-medium">{action.outcome}: {action.title}</div>
                <p className="mt-1 text-mute">
                  {action.owner || "Unassigned"}
                  {action.priority ? ` · ${action.priority} priority` : ""}
                  {action.due_on ? ` · due ${prettyDate(action.due_on)}` : ""}
                  {" · "}
                  {prettyDate(action.created_on)}
                </p>
                {action.note && <p className="mt-2">{action.note}</p>}
                {action.result && (
                  <p className="mt-2">
                    Outcome: {action.result}
                    {action.risk_before && action.risk_after ? ` · ${action.risk_before} risk → ${action.risk_after} risk` : ""}
                  </p>
                )}
                {action.outcome === "Completed" && !action.result && (
                  <label className="mt-3 block text-xs text-mute">
                    Record outcome
                    <select
                      defaultValue=""
                      disabled={saving}
                      onChange={(event) => {
                        if (event.target.value) void saveOutcome(action.id, event.target.value)
                      }}
                      className="mt-1 w-full rounded-2xl border border-line bg-card px-3 py-2 text-sm text-ink"
                    >
                      <option value="">Choose an outcome</option>
                      {RESULT_OPTIONS.map((item) => (
                        <option key={item}>{item}</option>
                      ))}
                    </select>
                  </label>
                )}
              </li>
            ))}
          </ul>
        </Panel>
      )}

      {modal && (
        <div className="fixed inset-0 z-50 grid place-items-center bg-ink/40 p-4">
          <div role="dialog" aria-modal="true" className="max-h-[90vh] w-full max-w-lg overflow-auto rounded-3xl bg-card p-6 shadow-card">
            <div className="flex items-start justify-between gap-3">
              <div>
                <Eyebrow>Record an action</Eyebrow>
                <h2 className="mt-1 font-serif text-3xl">What did you do?</h2>
              </div>
              <button type="button" aria-label="Close" onClick={() => setModal(false)}>
                <X size={18} />
              </button>
            </div>
            <form
              className="mt-5 space-y-4"
              onSubmit={(event) => {
                event.preventDefault()
                void submitAction()
              }}
            >
              <label className="block text-sm">
                Action
                <select
                  value={form.action_type}
                  onChange={(event) => setForm({ ...form, action_type: event.target.value })}
                  className="mt-1 w-full rounded-2xl border border-line bg-paper px-3 py-2.5"
                >
                  {ACTION_OPTIONS.map(([value, label]) => (
                    <option key={value} value={value}>
                      {label}
                    </option>
                  ))}
                </select>
              </label>
              <label className="block text-sm">
                Title
                <input value={form.title} onChange={(event) => setForm({ ...form, title: event.target.value })} className="mt-1 w-full rounded-2xl border border-line bg-paper px-3 py-2.5" required />
              </label>
              <div className="grid gap-4 sm:grid-cols-2">
                <label className="block text-sm">
                  Owner
                  <input value={form.owner} onChange={(event) => setForm({ ...form, owner: event.target.value })} className="mt-1 w-full rounded-2xl border border-line bg-paper px-3 py-2.5" />
                </label>
                <label className="block text-sm">
                  Due date
                  <input type="date" value={form.due_on} onChange={(event) => setForm({ ...form, due_on: event.target.value })} className="mt-1 w-full rounded-2xl border border-line bg-paper px-3 py-2.5" />
                </label>
              </div>
              <div className="grid gap-4 sm:grid-cols-2">
                <label className="block text-sm">
                  Priority
                  <select value={form.priority} onChange={(event) => setForm({ ...form, priority: event.target.value })} className="mt-1 w-full rounded-2xl border border-line bg-paper px-3 py-2.5">
                    <option>High</option>
                    <option>Medium</option>
                    <option>Low</option>
                  </select>
                </label>
                <label className="block text-sm">
                  Status
                  <select
                    value={form.outcome}
                    onChange={(event) => setForm({ ...form, outcome: event.target.value, result: event.target.value === "Completed" ? form.result : "" })}
                    className="mt-1 w-full rounded-2xl border border-line bg-paper px-3 py-2.5"
                  >
                    <option>Completed</option>
                    <option>Scheduled</option>
                    <option>Dismissed</option>
                  </select>
                </label>
              </div>
              {form.outcome === "Completed" && (
                <label className="block text-sm">
                  Outcome
                  <select value={form.result} onChange={(event) => setForm({ ...form, result: event.target.value })} className="mt-1 w-full rounded-2xl border border-line bg-paper px-3 py-2.5">
                    <option value="">Record later</option>
                    {RESULT_OPTIONS.map((item) => (
                      <option key={item} value={item}>
                        {item}
                      </option>
                    ))}
                  </select>
                </label>
              )}
              <label className="block text-sm">
                Notes
                <textarea value={form.note} onChange={(event) => setForm({ ...form, note: event.target.value })} rows={4} className="mt-1 w-full rounded-2xl border border-line bg-paper px-3 py-2.5" />
              </label>
              {formError && <p className="text-sm text-rose">{formError}</p>}
              <div className="flex justify-end gap-2">
                <button type="button" onClick={() => setModal(false)} className="rounded-full px-4 py-2 text-sm">
                  Cancel
                </button>
                <button type="submit" disabled={saving || form.title.trim().length < 2} className="rounded-full bg-deep px-4 py-2 text-sm text-white disabled:opacity-50">
                  {saving ? "Saving…" : "Save to the file"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between gap-4 border-b border-line/80 pb-2">
      <dt className="text-mute">{label}</dt>
      <dd className="text-right">{value}</dd>
    </div>
  )
}

function InsightList({ title, items, empty }: { title: string; items: string[]; empty: string }) {
  return (
    <div className="mt-4">
      <h3 className="text-sm font-medium">{title}</h3>
      {items.length === 0 ? (
        <p className="mt-1 text-sm text-mute">{empty}</p>
      ) : (
        <ul className="mt-2 space-y-1.5 text-sm leading-6">
          {items.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      )}
    </div>
  )
}

function CaseRow({
  item,
  pending,
  saving,
  onAsk,
  onCancel,
  onResolve,
}: {
  item: ServiceCase
  pending: boolean
  saving: boolean
  onAsk: () => void
  onCancel: () => void
  onResolve: () => void
}) {
  const open = item.status === "Open" || item.status === "In Progress"
  return (
    <div className="rounded-2xl bg-paper p-4 text-sm">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="font-medium">
          {item.id} · {item.title}
        </div>
        <Pill tone={item.status === "Resolved" ? "moss" : item.status === "Denied" ? "rose" : "amber"}>{item.status}</Pill>
      </div>
      <p className="mt-2 text-mute">{item.description}</p>
      <div className="mt-2 text-xs text-mute">
        {item.kind}
        {item.product_name ? ` · ${item.product_name}` : ""} · opened {prettyDate(item.opened_on)}
        {item.amount ? ` · ${money(item.amount)}` : ""}
        {item.closed_on ? ` · closed ${prettyDate(item.closed_on)}` : ` · ${item.age_days} days open`}
      </div>
      {open && !pending && (
        <button type="button" onClick={onAsk} className="mt-3 text-sm text-teal">
          Mark resolved
        </button>
      )}
      {pending && (
        <div className="mt-3 flex gap-3 text-sm">
          <span>Mark {item.id} resolved?</span>
          <button type="button" disabled={saving} onClick={onResolve} className="text-teal disabled:opacity-50">
            Yes, resolve
          </button>
          <button type="button" onClick={onCancel}>
            Cancel
          </button>
        </div>
      )}
    </div>
  )
}

function TimelineRow({ item, open, highlighted, onToggle }: { item: TimelineItem; open: boolean; highlighted: boolean; onToggle: () => void }) {
  return (
    <li id={`timeline-${item.id}`} className={highlighted ? "scroll-mt-24 rounded-2xl bg-paper ring-2 ring-teal" : "scroll-mt-24 rounded-2xl bg-paper"}>
      <button type="button" onClick={onToggle} className="flex w-full items-start justify-between gap-3 px-4 py-3 text-left" aria-expanded={open}>
        <span>
          <span className="block text-xs text-mute">
            {relativeDay(item.occurred_on)} · {item.kind}
            {item.duration_min ? ` · ${item.duration_min} min` : ""} · {item.actor}
          </span>
          <span className="mt-1 block font-medium">{item.title}</span>
        </span>
        <span className="flex items-center gap-2">
          {item.sentiment && <Pill tone={sentimentTone(item.sentiment)}>{item.sentiment}</Pill>}
          <ChevronDown size={16} className={open ? "rotate-180" : ""} />
        </span>
      </button>
      {open && (
        <div className="border-t border-line px-4 py-4 text-sm leading-7">
          {item.detail && <p className="whitespace-pre-wrap">{item.detail}</p>}
          {item.ai && (
            <div className="mt-4 grid gap-3 md:grid-cols-2">
              <Mini label="Intent" value={item.intent || "—"} />
              <Mini label="Urgency" value={item.urgency || "—"} />
              <Mini label="Topics" value={item.topics.join(", ") || "—"} />
              <Mini label="Concerns" value={item.concerns.join("; ") || "—"} />
              <Mini label="Entities" value={item.entities.join(", ") || "—"} />
              <Mini label="Churn signals" value={item.churn_signals.join("; ") || "—"} />
            </div>
          )}
          {item.summary && <p className="mt-3 text-mute">{item.summary}</p>}
          {item.source && <p className="mt-2 text-xs text-mute">Reading source: {item.source === "llm" ? "language model" : "rules engine"}</p>}
        </div>
      )}
    </li>
  )
}

function Mini({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-[11px] uppercase tracking-[0.14em] text-mute">{label}</div>
      <div>{value}</div>
    </div>
  )
}
