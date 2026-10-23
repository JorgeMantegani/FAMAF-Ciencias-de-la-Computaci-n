// Prints coverage tables from Istanbul JSON, so e2e and total count lines the same way Vitest does.
//   node tests/coverage_report.js e2e    -> summary of the Playwright run
//   node tests/coverage_report.js total  -> merges Vitest and Playwright line by line (union, not sum) into coverage-total/
import { existsSync, readFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join, relative } from 'node:path'
import { CoverageReport } from 'monocart-coverage-reports'

const UNIT_JSON = 'coverage/coverage-final.json'
const E2E_JSON = 'coverage-e2e/coverage-final.json'

const MODES = {
  e2e: {
    inputs: [E2E_JSON],
    // Only the console table is wanted; the HTML report already lives in coverage-e2e/.
    options: {
      name: 'Cobertura e2e (Playwright)',
      outputDir: join(tmpdir(), 'futbot-coverage-e2e-summary'),
      reports: ['console-summary'],
    },
  },
  total: {
    inputs: [UNIT_JSON, E2E_JSON],
    // Only lines: each tool splits statements, branches and functions differently, so merging double counts them.
    options: {
      name: 'Cobertura total (Vitest + Playwright)',
      outputDir: './coverage-total',
      reports: [
        ['html-spa', { metricsToShow: ['lines'] }],
        ['console-summary', { metrics: ['lines'] }],
      ],
    },
  },
}

// Vitest keys files by absolute path and Playwright by "src/...": both become "src/...".
function load(input) {
  if (!existsSync(input)) {
    console.error(`No existe ${input}. Corré antes "make coverage-unit" y/o "make coverage-e2e".`)
    process.exit(1)
  }
  const normalized = {}
  for (const file of Object.values(JSON.parse(readFileSync(input, 'utf8')))) {
    const path = relative(process.cwd(), file.path).replaceAll('\\', '/')
    normalized[path] = { ...file, path }
  }
  return normalized
}

const mode = MODES[process.argv[2]]
if (!mode) {
  console.error('Uso: node tests/coverage_report.js e2e|total')
  process.exit(1)
}
const report = new CoverageReport(mode.options)
for (const input of mode.inputs) {
  await report.add(load(input))
}
await report.generate()
