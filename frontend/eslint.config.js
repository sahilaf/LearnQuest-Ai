// ESLint 9 flat config. Replaces .eslintrc.json, which ESLint 9 no longer
// reads - `npm run lint` had been failing before checking a single file.
import js from '@eslint/js';
import react from 'eslint-plugin-react';
import reactHooks from 'eslint-plugin-react-hooks';
import globals from 'globals';

export default [
  { ignores: ['dist/**'] },
  js.configs.recommended,
  {
    files: ['src/**/*.{js,jsx}'],
    languageOptions: {
      ecmaVersion: 'latest',
      sourceType: 'module',
      globals: { ...globals.browser },
      parserOptions: { ecmaFeatures: { jsx: true } },
    },
    plugins: { react, 'react-hooks': reactHooks },
    settings: { react: { version: 'detect' } },
    rules: {
      ...react.configs.recommended.rules,
      ...reactHooks.configs.recommended.rules,
      'react/react-in-jsx-scope': 'off',
      'react/prop-types': 'off',
      // `catch (err) {}` and `{ node, ...props }` (dropping a key from a
      // spread) are deliberate; anything else unused is a real finding.
      'no-unused-vars': ['error', { caughtErrors: 'none', ignoreRestSiblings: true }],
      // A bare apostrophe in JSX text renders correctly; escaping every
      // "you're" as &apos; makes copy harder to edit for no gain.
      'react/no-unescaped-entities': 'off',
    },
  },
  {
    // Vitest runs these in Node with its own globals.
    files: ['src/**/*.test.{js,jsx}'],
    languageOptions: { globals: { ...globals.node } },
  },
];
