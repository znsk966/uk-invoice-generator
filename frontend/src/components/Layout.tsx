import { NavLink, Outlet } from 'react-router-dom'

const NAV = [
  { to: '/invoices', label: 'Invoices' },
  { to: '/clients', label: 'Clients' },
  { to: '/settings', label: 'Settings' },
]

export function Layout() {
  return (
    <div className="min-h-screen bg-gray-50 text-gray-900">
      <div className="mx-auto flex max-w-7xl">
        <aside className="min-h-screen w-56 shrink-0 border-r border-gray-200 bg-white px-4 py-6">
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
        </aside>

        <main className="flex-1 px-8 py-6">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
