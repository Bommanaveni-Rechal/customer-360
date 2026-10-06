export function cn(...parts: Array<string | false | null | undefined>) {
  return parts.filter(Boolean).join(" ")
}

export function money(value: number) {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  }).format(value)
}

export function percent(value: number) {
  return `${Math.round(value * 100)}%`
}

export function prettyDate(iso: string | null) {
  if (!iso) return "—"
  const date = new Date(iso.includes("T") ? iso : `${iso}T12:00:00`)
  return date.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })
}

export function relativeDay(iso: string) {
  const date = new Date(iso.includes("T") ? iso : `${iso}T12:00:00`)
  const now = new Date()
  const start = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const target = new Date(date.getFullYear(), date.getMonth(), date.getDate())
  const days = Math.round((start.getTime() - target.getTime()) / 86400000)
  if (days <= 0) return "Today"
  if (days === 1) return "Yesterday"
  if (days < 45) return `${days} days ago`
  return prettyDate(iso)
}

export function bookLabel(book: string) {
  if (book === "Both") return "Insurance + lending"
  return book
}

export function greeting() {
  const hour = new Date().getHours()
  if (hour < 12) return "Good morning"
  if (hour < 17) return "Good afternoon"
  return "Good evening"
}

export const ACTION_LABEL: Record<string, string> = {
  retention_call: "Retention call",
  resolve_complaint: "Resolve complaint",
  follow_up_claim: "Claim follow-up",
  offer_renewal: "Renewal offer",
  offer_product: "Product offer",
  personalized_discount: "Personal discount",
  escalate_service: "Escalate service",
  schedule_follow_up: "Follow-up",
  payment_follow_up: "Payment follow-up",
  no_action: "No action",
}

export const SCENARIOS = [
  { id: "retention", label: "High-risk retention", customerId: "CUS-1042" },
  { id: "escalation", label: "Claim escalation", customerId: "CUS-1066" },
  { id: "renewal", label: "Renewal opportunity", customerId: "CUS-1088" },
  { id: "cross", label: "Cross-sell opportunity", customerId: "CUS-1214" },
  { id: "hardship", label: "Lending hardship", customerId: "CUS-1267" },
  { id: "quiet", label: "No action required", customerId: "CUS-1175" },
] as const

export const RESULT_OPTIONS = [
  "Customer retained",
  "Complaint resolved",
  "Renewal completed",
  "Customer declined",
  "No response",
] as const

export const ACTION_OPTIONS = [
  ["retention_call", "Retention call"],
  ["resolve_complaint", "Resolve complaint"],
  ["follow_up_claim", "Follow up on claim"],
  ["offer_renewal", "Offer renewal"],
  ["offer_product", "Offer a relevant product"],
  ["personalized_discount", "Personalized discount"],
  ["escalate_service", "Escalate service issue"],
  ["schedule_follow_up", "Schedule follow-up"],
  ["payment_follow_up", "Payment follow-up"],
  ["no_action", "No action required"],
] as const

export function riskTone(level: string): "rose" | "amber" | "moss" | "slate" {
  if (level === "High") return "rose"
  if (level === "Medium") return "amber"
  return "moss"
}

export function sentimentTone(sentiment: string): "rose" | "amber" | "moss" | "slate" {
  if (sentiment === "Negative") return "rose"
  if (sentiment === "Positive") return "moss"
  return "slate"
}

export function priorityTone(priority: string): "rose" | "amber" | "teal" | "slate" {
  if (priority === "High") return "rose"
  if (priority === "Medium") return "amber"
  if (priority === "Low") return "teal"
  return "slate"
}

export function avatarColor(name: string) {
  const palette = ["#0e6b64", "#1d4e59", "#8a5a12", "#7a3e49", "#245c45", "#3e4d63"]
  let hash = 0
  for (const char of name) hash = (hash * 31 + char.charCodeAt(0)) >>> 0
  return palette[hash % palette.length]
}

export const QUESTIONS = [
  "Why is this customer at risk?",
  "What should we do next?",
  "Why is the customer unhappy?",
  "Should we contact this customer?",
  "Summarize this customer's recent interactions.",
  "What product would be relevant for this customer?",
]
