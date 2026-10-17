// Applies the saved theme and language direction before React renders (no flash of the wrong theme).
// A separate file rather than an inline script, so the Content-Security-Policy can forbid inline scripts.
;(function () {
  try {
    var t = localStorage.getItem('researchmind.theme')
    var dark = t === 'dark' || ((!t || t === 'system') && window.matchMedia('(prefers-color-scheme: dark)').matches)
    if (dark) document.documentElement.classList.add('dark')
    var l = localStorage.getItem('researchmind.language')
    if (l) {
      document.documentElement.lang = l
      if (l === 'ar') document.documentElement.dir = 'rtl'
    }
  } catch (e) { /* storage unavailable: defaults apply */ }
})()
