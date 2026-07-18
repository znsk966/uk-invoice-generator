const REPO_URL = 'https://github.com/znsk966/uk-invoice-generator'

function App() {
  return (
    <main className="min-h-screen flex flex-col items-center justify-center gap-4 p-8 text-center">
      <h1 className="text-4xl font-semibold tracking-tight">
        UK Invoice Generator
      </h1>
      <p className="max-w-prose text-lg text-gray-600 dark:text-gray-400">
        An open-source proof-of-concept invoice generator for the UK market.
        Currently in <strong>Phase 0 — scaffold</strong>.
      </p>
      <a
        href={REPO_URL}
        className="text-indigo-600 underline underline-offset-4 hover:text-indigo-500 dark:text-indigo-400"
        target="_blank"
        rel="noreferrer"
      >
        View the project on GitHub
      </a>
    </main>
  )
}

export default App
