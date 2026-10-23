import js from '@eslint/js'
import globals from 'globals'
import react_hooks from 'eslint-plugin-react-hooks'
import react_refresh from 'eslint-plugin-react-refresh'
import { defineConfig, globalIgnores } from 'eslint/config'

export default defineConfig([
  globalIgnores(['dist', 'coverage', 'coverage-e2e', 'coverage-total', 'playwright-report']),
  {
    files: ['**/*.{js,jsx}'],
    extends: [
      js.configs.recommended,
      react_hooks.configs.flat.recommended,
      react_refresh.configs.vite,
    ],
    languageOptions: {
      globals: globals.browser,
      parserOptions: { ecmaFeatures: { jsx: true } },
    },
  },
  {
    // Coverage helpers run in Node, and Playwright's fixture "use" is not a React hook.
    files: ['tests/fixtures.js', 'tests/e2e_coverage.js', 'tests/coverage_report.js'],
    languageOptions: { globals: globals.node },
    rules: { 'react-hooks/rules-of-hooks': 'off' },
  },
])
