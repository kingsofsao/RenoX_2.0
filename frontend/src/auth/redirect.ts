// Where to go once the user is signed in. PublicOnly performs the redirect (it re-renders the moment the
// session exists), so pages only say where they want to go, before signing in, instead of navigating themselves.
let pending: string | null = null

/** Only same-site paths are accepted, so a crafted ?next= can never send the user to another site. */
export function safeNext(search: string): string {
  const next = new URLSearchParams(search).get('next') ?? '/'
  return isSafePath(next) ? next : '/'
}

function isSafePath(path: string): boolean {
  return path.startsWith('/') && !path.startsWith('//') && !path.startsWith('/\\')
}

export function setPostAuthRedirect(path: string): void {
  pending = isSafePath(path) ? path : null
}

/** Read without clearing: render functions may run twice (React StrictMode), so reading must be pure. */
export function peekPostAuthRedirect(): string | null {
  return pending
}

/** Called once the app has mounted after signing in. */
export function clearPostAuthRedirect(): void {
  pending = null
}
