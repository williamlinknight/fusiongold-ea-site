import { defineConfig } from 'astro/config';
import sitemap from '@astrojs/sitemap';

export default defineConfig({
  site: 'https://williamlinknight.github.io/fusiongold-ea-site',
  integrations: [sitemap()],
  server: { host: '127.0.0.1', port: 3000 },
  trailingSlash: 'always',
  legacy: {
    collectionsBackwardsCompat: true,
  },
});
