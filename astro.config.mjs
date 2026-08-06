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
      serialize: (item) => {
        // GitHub Pages serves directory routes with a trailing slash and 301-redirects
        // the slash-less form; keep sitemap URLs canonical to avoid redirect chains.
        if (!item.url.endsWith('/')) item.url += '/';
        return item;
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
