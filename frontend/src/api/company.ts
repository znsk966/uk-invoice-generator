import { request } from './client'
import type { CompanyProfile, CompanyProfileWrite } from './types'

/** Throws `ApiError` with code `company_profile_missing` when never saved. */
export function getCompanyProfile(): Promise<CompanyProfile> {
  return request<CompanyProfile>('/company-profile')
}

export function saveCompanyProfile(payload: CompanyProfileWrite): Promise<CompanyProfile> {
  return request<CompanyProfile>('/company-profile', { method: 'PUT', body: payload })
}
