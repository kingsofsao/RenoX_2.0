import { defineConfig, loadEnv, type Plugin } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// Public pages that search engines may index. Everything else needs a signed-in account.
const PUBLIC_PATHS = ['/', '/signup', '/signin', '/privacy', '/terms']
// App routes (signed-in only) and the API: nothing for a crawler there.
const PRIVATE_PREFIXES = ['/api/', '/investigate', '/library', '/upload', '/papers/', '/graph', '/projects', '/settings', '/admin']

/**
 * Fills the absolute site URL into index.html (canonical and social-preview tags must be absolute,
 * and scrapers do not run JavaScript) and emits robots.txt and sitemap.xml for VITE_SITE_URL.
 */
function siteFiles(siteUrl: string): Plugin {
  return {
    name: 'researchmind-site-files',
    transformIndexHtml(html) {
      return html.replaceAll('%SITE_URL%', siteUrl)
    },
    generateBundle() {
      if (!siteUrl) {
        this.warn('VITE_SITE_URL is not set: canonical, social preview and sitemap URLs will be relative. Set it to your https:// domain for production builds.')
      }
      const today = new Date().toISOString().slice(0, 10)
      const robots = [
        'User-agent: *',
        ...PRIVATE_PREFIXES.map((p) => `Disallow: ${p}`),
        'Allow: /',
        '',
        ...(siteUrl ? [`Sitemap: ${siteUrl}/sitemap.xml`, ''] : []),
      ].join('\n')
      const urls = PUBLIC_PATHS.map((p) => `  <url><loc>${siteUrl}${p}</loc><lastmod>${today}</lastmod></url>`).join('\n')
      const sitemap = `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n${urls}\n</urlset>\n`
      this.emitFile({ type: 'asset', fileName: 'robots.txt', source: robots })
      this.emitFile({ type: 'asset', fileName: 'sitemap.xml', source: sitemap })
    },
  }
}

// In development the React app calls relative /api URLs and Vite proxies them to FastAPI,
// so the browser never needs CORS. Set VITE_API_BASE_URL to call the API directly instead.
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const target = env.VITE_API_PROXY_TARGET || 'http://127.0.0.1:8000'
  const siteUrl = (env.VITE_SITE_URL || '').replace(/\/$/, '')
  return {
    plugins: [react(), tailwindcss(), siteFiles(siteUrl)],
    server: {
      port: 5173,
      proxy: { '/api': { target, changeOrigin: true } },
    },
    preview: {
      port: 4173,
      proxy: { '/api': { target, changeOrigin: true } },
    },
    test: {
      environment: 'node',
    },
  }
})
