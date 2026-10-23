import { test as base, expect } from '@playwright/test'
import { CoverageReport } from 'monocart-coverage-reports'
import { coverage_enabled, coverage_options } from './e2e_coverage.js'

// Same test as Playwright's, plus V8 coverage of every page in the context when E2E_COVERAGE is set.
export const test = base.extend({
  context: async ({ context }, use) => {
    if (!coverage_enabled) {
      await use(context)
      return
    }
    const started = []
    context.on('page', (page) => {
      started.push(page.coverage.startJSCoverage({ resetOnNavigation: false }).then(() => page))
    })
    await use(context)
    const pages = await Promise.all(started)
    for (const page of pages.filter((page) => !page.isClosed())) {
      await new CoverageReport(coverage_options).add(await page.coverage.stopJSCoverage())
    }
  },
})

export { expect }
