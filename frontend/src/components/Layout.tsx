import { useMutation, useQueryClient } from '@tanstack/react-query'
import { NavLink, Outlet, useNavigate } from 'react-router-dom'

import { logout } from '../api/auth'
import { ME_QUERY_KEY, useMe } from '../shared/useMe'

const NAV = [
  { to: '/invoices', label: 'Invoices' },
  { to: '/clients', label: 'Clients' },
  { to: '/products', label: 'Products' },
  { to: '/settings', label: 'Settings' },
]

export function Layout() {
  const { data: user } = useMe()
  const queryClient = useQueryClient()
  const navigate = useNavigate()

  const signOut = useMutation({
    mutationFn: logout,
    // Whether or not the request succeeds, end the local session: clear the
    // cached user and route to login.
    onSettled: () => {
      queryClient.setQueryData(ME_QUERY_KEY, null)
      navigate('/login', { replace: true })
    },
  })

  return (
    <div className="min-h-screen bg-gray-50 text-gray-900">
      <div className="mx-auto flex max-w-7xl">
        <aside className="flex min-h-screen w-56 shrink-0 flex-col border-r border-gray-200 bg-white px-4 py-6">
          <h1 className="px-3 pb-6 text-sm font-semibold tracking-tight text-gray-900">
            UK Invoice Generator
          </h1>
          <nav className="flex flex-col gap-1">
            {NAV.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) =>
                  `rounded-md px-3 py-2 text-sm ${
                    isActive
                      ? 'bg-gray-900 font-medium text-white'
                      : 'text-gray-700 hover:bg-gray-100'
                  }`
                }
              >
                {item.label}
              </NavLink>
            ))}
          </nav>

          <div className="mt-auto border-t border-gray-100 pt-4">
            {user ? (
              <p className="mb-2 truncate px-3 text-xs text-gray-500" title={user.email}>
                {user.email}
              </p>
            ) : null}
            <button
              type="button"
              onClick={() => signOut.mutate()}
              disabled={signOut.isPending}
              className="w-full rounded-md px-3 py-2 text-left text-sm text-gray-700 hover:bg-gray-100 disabled:opacity-50"
            >
              {signOut.isPending ? 'Signing out…' : 'Log out'}
            </button>
          </div>
        </aside>

        <main className="flex-1 px-8 py-6">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
