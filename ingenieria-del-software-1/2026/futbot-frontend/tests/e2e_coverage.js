import { CoverageReport } from 'monocart-coverage-reports'

export const coverage_enabled = Boolean(process.env.E2E_COVERAGE)

export const coverage_options = {
  name: 'Cobertura e2e (Playwright)',
  outputDir: './coverage-e2e',
  // Vite serves CSS as JS modules: skip them, they hold no logic to cover.
  entryFilter: (entry) => {
    const { pathname } = new URL(entry.url)
    return pathname.startsWith('/src/') && !pathname.endsWith('.css')
  },
  sourceFilter: (source_path) => /\.jsx?$/.test(source_path),
  // Vite's source maps name only the file ("Login.jsx"); the served module ("127.0.0.1-5173/src/pages/Login.jsx")
  // has the full path, so it is used and trimmed to "src/..." to match Vitest's paths.
  sourcePath: (source_path, { distFile }) => (distFile ?? source_path).replace(/^.*?(?=src\/)/, ''),
  // Istanbul reports (not 'v8') so lines are counted like Vitest; the table is printed by coverage_report.js.
  reports: ['html', ['json', { file: 'coverage-final.json' }]],
}

// Playwright globalSetup: drops data from previous runs and returns the teardown that builds the report.
export default async function setup() {
  if (!coverage_enabled) return
  new CoverageReport(coverage_options).cleanCache()
  return async () => {
    await new CoverageReport(coverage_options).generate()
  }
}
