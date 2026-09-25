import { useQuery } from '@tanstack/react-query'

import { getMe } from '../api/auth'
import { ApiError } from '../api/client'
import type { User } from '../api/types'

export const ME_QUERY_KEY = ['me'] as const

/**
 * The authenticated user, or `null` when not logged in.
 *
 * A 401 is a normal answer here (anonymous visitor), not an error to retry — so
 * it is folded into `data: null` rather than surfaced as an error. Any other
 * failure still rejects. The route guard reads `data`/`isPending` from this.
 */
export function useMe() {
  return useQuery<User | null>({
    queryKey: ME_QUERY_KEY,
    queryFn: async () => {
      try {
        return await getMe()
      } catch (error) {
        if (error instanceof ApiError && error.status === 401) {
          return null
        }
        throw error
      }
    },
    // Auth state is not something to retry or refetch behind the user's back.
    retry: false,
    refetchOnWindowFocus: false,
    staleTime: Infinity,
  })
}
