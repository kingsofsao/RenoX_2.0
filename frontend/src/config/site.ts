// Public site settings, set at build time (frontend/.env or the Docker build arguments). Nothing secret here.
export const SITE = {
  name: 'ResearchMind AI',
  /** Canonical origin of the deployed site, e.g. https://researchmind.example.com (used for canonical/OG URLs). */
  url: (import.meta.env.VITE_SITE_URL ?? '').replace(/\/$/, ''),
  /** Who runs the service (shown in the Privacy Policy and Terms). */
  operator: import.meta.env.VITE_OPERATOR_NAME || 'The ResearchMind AI team',
  /** Address for privacy requests and support (shown in the legal pages and the contact form). */
  contactEmail: import.meta.env.VITE_CONTACT_EMAIL || '',
  /** Date the Privacy Policy and Terms were last changed (ISO date). */
  legalUpdated: '2026-10-18',
}
