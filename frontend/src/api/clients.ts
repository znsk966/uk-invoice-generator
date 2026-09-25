import { request } from './client'
import type { Client, ClientWrite } from './types'

export function listClients(includeArchived = false): Promise<Client[]> {
  return request<Client[]>(`/clients?include_archived=${includeArchived}`)
}

export function getClient(id: number): Promise<Client> {
  return request<Client>(`/clients/${id}`)
}

export function createClient(payload: ClientWrite): Promise<Client> {
  return request<Client>('/clients', { method: 'POST', body: payload })
}

export function updateClient(id: number, payload: ClientWrite): Promise<Client> {
  return request<Client>(`/clients/${id}`, { method: 'PUT', body: payload })
}

/** Clients are archived, never deleted — issued invoices must keep valid references. */
export function archiveClient(id: number): Promise<Client> {
  return request<Client>(`/clients/${id}/archive`, { method: 'POST' })
}

export function unarchiveClient(id: number): Promise<Client> {
  return request<Client>(`/clients/${id}/unarchive`, { method: 'POST' })
}
