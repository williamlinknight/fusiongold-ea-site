import { defineConfig } from 'astro/config';
import sitemap from '@astrojs/sitemap';

export default defineConfig({
  site: 'https://williamlinknight.github.io/fusiongold-ea-site',
  base: '/fusiongold-ea-site/',
  integrations: [
    sitemap({
      i18n: {
        defaultLocale: 'ja',
        locales: {
          ja: 'ja-JP',
          en: 'en-US',
        },
      },
    }),
  ],
  server: { host: '127.0.0.1', port: 3000 },
  trailingSlash: 'never',
  build: {
    format: 'directory',
  },
  legacy: {
    collectionsBackwardsCompat: true,
  },
});
