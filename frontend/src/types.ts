export type Story = {
  kicker: string
  title: string
  blurb: string
}

export type NbaSummary = {
  action_type: string
  title: string
  priority: string
  reason: string
  evidence_preview: string
}

export type CustomerRow = {
  id: string
  name: string
  initials: string
  city: string
  region: string
  occupation: string
  segment: string
  book: string
  tenure_months: number
  customer_value: number
  high_value: boolean
  risk_level: string
  risk_score: number
  churn_probability: number
  sentiment: string
  intent: string
  nba: NbaSummary
  open_issues: number
  next_renewal_days: number | null
  headline_product: string
  story: Story | null
}

export type Point = { label: string; value: number }

export type DashboardData = {
  ai_mode: string
  kpis: {
    customers: number
    high_risk: number
    needs_action: number
    negative_sentiment: number
    open_issues: number
    churn_cases: number
    recommended_actions: number
  }
  charts: {
    sentiment: Point[]
    risk: Point[]
    segments: Point[]
    actions: Point[]
  }
  stories: CustomerRow[]
  queue: CustomerRow[]
}

export type Product = {
  id: number
  kind: string
  name: string
  number: string
  status: string
  health: string
  installment: number
  frequency: string
  cover: number
  outstanding: number
  renewal_on: string | null
  renewal_in_days: number | null
  next_due_on: string | null
  started_on: string
}

export type Payment = {
  id: number
  product_name: string
  product_number: string
  paid_on: string
  amount: number
  status: string
}

export type ServiceCase = {
  id: string
  kind: string
  title: string
  description: string
  status: string
  opened_on: string
  closed_on: string | null
  amount: number | null
  product_name: string | null
  age_days: number
}

export type TimelineItem = {
  id: string
  kind: string
  occurred_on: string
  title: string
  detail: string
  actor: string
  direction: string
  duration_min: number | null
  sentiment: string | null
  intent: string | null
  topics: string[]
  concerns: string[]
  urgency: string | null
  entities: string[]
  churn_signals: string[]
  summary: string
  quote: string
  source: string | null
  ai: boolean
  expandable: boolean
}

export type ActionRecord = {
  id: number
  action_type: string
  title: string
  outcome: string
  note: string
  owner: string
  due_on: string | null
  priority: string
  result: string
  risk_before: string
  risk_after: string
  nba_before: string
  nba_after: string
  created_on: string
}

export type EvidenceLink = {
  text: string
  timeline_id: string | null
}

export type Alternative = {
  action_type: string
  title: string
  reason: string
}

export type Nba = {
  action_type: string
  title: string
  priority: string
  reason: string
  expected_impact: string
  talk_track: string
  evidence: string[]
  evidence_links: EvidenceLink[]
  reasoning: string[]
  alternatives: Alternative[]
  suggested_note: string
  confidence: number
  confidence_note: string
  selection: string
}

export type SourceItem = {
  name: string
  count: number
}

export type SourceTrace = {
  items: SourceItem[]
  last_updated: string
  analyzed_interactions: number
}

export type CustomerDetail = {
  customer: {
    id: string
    name: string
    initials: string
    age: number
    city: string
    region: string
    occupation: string
    email: string
    phone: string
    segment: string
    book: string
    tenure_months: number
    tenure_label: string
    customer_value: number
    joined_on: string
    high_value: boolean
  }
  risk: {
    level: string
    score: number
    churn_probability: number
    factors: string[]
  }
  insights: {
    sentiment: string
    previous_sentiment: string | null
    trend: string | null
    intent: string
    concerns: string[]
    topics: string[]
    urgency: string
    facts: string[]
    churn_indicators: string[]
    summary: string
    source: string
  }
  nba: Nba
  products: Product[]
  payments: Payment[]
  cases: ServiceCase[]
  timeline: TimelineItem[]
  actions: ActionRecord[]
  sources: SourceTrace
  story: Story | null
  open_issues: number
  next_renewal_days: number | null
  headline_product: string
}

export type Answer = {
  question: string
  answer: string
  recommended_action: string
  priority: string
  source: string
}

export type Health = {
  status: string
  ai_mode: string
  customers: number
  seed_version: string
}
