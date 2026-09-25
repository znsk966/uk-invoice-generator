import { request } from './client'
import type { Product, ProductCreate, ProductPriceUpdate } from './types'

export function listProducts(includeArchived = false): Promise<Product[]> {
  return request<Product[]>(`/products?include_archived=${includeArchived}`)
}

export function getProduct(id: number): Promise<Product> {
  return request<Product>(`/products/${id}`)
}

export function createProduct(payload: ProductCreate): Promise<Product> {
  return request<Product>('/products', { method: 'POST', body: payload })
}

/** Price is the only thing that can change — identity is fixed at creation. */
export function updateProductPrice(id: number, payload: ProductPriceUpdate): Promise<Product> {
  return request<Product>(`/products/${id}`, { method: 'PATCH', body: payload })
}

/** Products are archived, never deleted — linked lines must keep valid references. */
export function archiveProduct(id: number): Promise<Product> {
  return request<Product>(`/products/${id}/archive`, { method: 'POST' })
}

export function unarchiveProduct(id: number): Promise<Product> {
  return request<Product>(`/products/${id}/unarchive`, { method: 'POST' })
}
