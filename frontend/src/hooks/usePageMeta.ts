import { useEffect } from 'react'
import { useLocation } from 'react-router-dom'
import { SITE } from '../config/site'

function setMeta(selector: string, attr: 'name' | 'property', key: string, content: string) {
  let el = document.head.querySelector<HTMLMetaElement>(selector)
  if (!el) {
    el = document.createElement('meta')
    el.setAttribute(attr, key)
    document.head.appendChild(el)
  }
  el.content = content
}

/** Page title and description for the browser tab, search engines and social previews. */
export function usePageMeta(title: string, description?: string, opts: { noindex?: boolean } = {}) {
  const { pathname } = useLocation()
  useEffect(() => {
    const full = title ? `${title} · ${SITE.name}` : SITE.name
    document.title = full
    setMeta('meta[property="og:title"]', 'property', 'og:title', full)
    setMeta('meta[name="twitter:title"]', 'name', 'twitter:title', full)
    if (description) {
      setMeta('meta[name="description"]', 'name', 'description', description)
      setMeta('meta[property="og:description"]', 'property', 'og:description', description)
      setMeta('meta[name="twitter:description"]', 'name', 'twitter:description', description)
    }
    setMeta('meta[name="robots"]', 'name', 'robots', opts.noindex ? 'noindex, nofollow' : 'index, follow')
    if (SITE.url) {
      setMeta('meta[property="og:url"]', 'property', 'og:url', SITE.url + pathname)
      let link = document.head.querySelector<HTMLLinkElement>('link[rel="canonical"]')
      if (!link) {
        link = document.createElement('link')
        link.rel = 'canonical'
        document.head.appendChild(link)
      }
      link.href = SITE.url + pathname
    }
  }, [title, description, pathname, opts.noindex])
}
