const { defineConfig } = require('eslint/config');
const expo = require('eslint-config-expo/flat');
module.exports = defineConfig([
  expo,
  { ignores: ['dist/**', 'dist-ios/**', 'src/shared/**', 'src/content/**', 'src/components/imageAssets.ts', 'App.js', 'index.js'] },
  { files: ['**/*.js', '**/*.cjs'], rules: { '@typescript-eslint/no-require-imports': 'off' } },
  { files: ['src/services/rules.ts'], rules: { '@typescript-eslint/no-require-imports': 'off' } },
]);
