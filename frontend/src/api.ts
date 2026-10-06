import type { Answer, CustomerDetail, CustomerRow, DashboardData, Health } from "./types"

const BASE = (import.meta.env.VITE_API_URL ?? "").replace(/\/$/, "")

export class ApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${BASE}${path}`, {
      ...init,
      headers: {
        ...(init?.body ? { "Content-Type": "application/json" } : {}),
        ...init?.headers,
      },
    })
  } catch {
    throw new ApiError(0, "Cannot reach the Customer-360 API. Start it on port 8000 and refresh.")
  }
  if (!response.ok) {
    throw new ApiError(response.status, response.status === 404 ? "That record is not on this book." : "The request failed.")
  }
  return response.json() as Promise<T>
}

export function getHealth() {
  return request<Health>("/api/health")
}

export function getDashboard() {
  return request<DashboardData>("/api/dashboard")
}

export function getCustomers(params: Record<string, string | boolean | undefined> = {}) {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === "" || value === false) continue
    search.set(key, String(value))
  }
  const query = search.toString()
  return request<{ customers: CustomerRow[] }>(`/api/customers${query ? `?${query}` : ""}`)
}

export function getCustomer(id: string) {
  return request<CustomerDetail>(`/api/customers/${id}`)
}

export function getActions() {
  return request<{ actions: CustomerRow[] }>("/api/actions")
}

export function askCustomer(id: string, question: string) {
  return request<Answer>(`/api/customers/${id}/ask`, {
    method: "POST",
    body: JSON.stringify({ question }),
  })
}

export function recordAction(
  id: string,
  body: {
    action_type: string
    title: string
    outcome: string
    note: string
    owner: string
    due_on: string | null
    priority: string
    result: string
  },
) {
  return request<CustomerDetail>(`/api/customers/${id}/actions`, {
    method: "POST",
    body: JSON.stringify(body),
  })
}

export function recordOutcome(actionId: number, result: string) {
  return request<CustomerDetail>(`/api/actions/${actionId}/result`, {
    method: "POST",
    body: JSON.stringify({ result }),
  })
}

export function updateCase(caseId: string, status: string) {
  return request<CustomerDetail>(`/api/cases/${caseId}`, {
    method: "PATCH",
    body: JSON.stringify({ status }),
  })
}

export function rereadCustomer(id: string) {
  return request<CustomerDetail>(`/api/customers/${id}/analyze`, { method: "POST" })
}

export function resetDemo() {
  return request<{ ok: boolean; customers: number }>("/api/demo/reset", { method: "POST" })
}
