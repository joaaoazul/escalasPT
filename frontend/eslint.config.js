import js from '@eslint/js';
import globals from 'globals';
import reactHooks from 'eslint-plugin-react-hooks';
import reactRefresh from 'eslint-plugin-react-refresh';
import tseslint from 'typescript-eslint';

export default tseslint.config(
  { ignores: ['dist', 'dev-dist', 'node_modules', 'public/sw-push.js'] },
  {
    files: ['**/*.{ts,tsx}'],
    extends: [js.configs.recommended, ...tseslint.configs.recommended],
    languageOptions: {
      ecmaVersion: 2022,
      globals: globals.browser,
    },
    plugins: {
      'react-hooks': reactHooks,
      'react-refresh': reactRefresh,
    },
    rules: {
      ...reactHooks.configs.recommended.rules,
      'react-refresh/only-export-components': [
        'warn',
        { allowConstantExport: true },
      ],
      // A warning, not an error, and deliberately so: this rule is about
      // cascading renders, and satisfying it means restructuring the effects
      // in AssignmentPopover, ShiftEditorModal and usePushNotifications —
      // behaviour changes that want testing in a browser, not a lint pass.
      // It stays visible so the debt doesn't disappear, without blocking CI
      // on a refactor nobody has done yet.
      'react-hooks/set-state-in-effect': 'warn',
    },
  },
);
