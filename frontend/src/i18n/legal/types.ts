// Legal page content. Paragraphs starting with "- " render as list items.
// Placeholders: {operator} (who runs the service) and {contact} (how to reach them).
export interface LegalSection {
  id: string
  heading: string
  body: string[]
}

export interface LegalDoc {
  title: string
  description: string
  intro: string
  sections: LegalSection[]
}

export interface LegalTexts {
  privacy: LegalDoc
  terms: LegalDoc
  updated: string          // "Last updated {date}"
  contactEmail: string     // "by email at {email} or through the Contact form on this site"
  contactForm: string      // "through the Contact form on this site"
  contents: string         // "Contents"
  translationNote: string  // shown on non-English versions: the English version prevails
}
