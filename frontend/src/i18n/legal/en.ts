import type { LegalTexts } from './types'

const legal: LegalTexts = {
  updated: 'Last updated {date}',
  contactEmail: 'by email at {email} or through the Contact form on this site',
  contactForm: 'through the Contact form on this site',
  contents: 'Contents',
  translationNote: '',
  privacy: {
    title: 'Privacy Policy',
    description: 'What ResearchMind AI collects, why, how long it is kept, and the choices you have.',
    intro: 'This policy explains what information ResearchMind AI collects when you use it, how the information is used and protected, and the choices you have. ResearchMind AI is operated by {operator}.',
    sections: [
      {
        id: 'collect',
        heading: 'Information we collect',
        body: [
          '- Account details: your name, email address, and your language and theme preferences. Your password is never stored; only a one-way Argon2id hash of it is kept.',
          '- Content you add: the PDF files you upload, the text extracted from them, the knowledge graph built from them, your questions, any project requirements you enter, and the reports generated for you.',
          '- Sign-in sessions: when you sign in we record when the session started, when it was last used and your browser\'s user-agent string, so you can review and end sessions in Settings.',
          '- Messages you send us through the Contact form: your name, email address, topic and message.',
          '- Usage statistics, only if you allow them: daily counts of page views and of a few actions (sign-ups, uploads, investigations), grouped by page and by campaign tag. These counts contain no IP address, no account identifier and no cookie, so they cannot be linked to you.',
          '- Server logs: technical records of requests and errors, used to keep the service secure and working. They do not contain your password or the content of your papers.',
        ],
      },
      {
        id: 'use',
        heading: 'How we use information',
        body: [
          'We use your information to provide the service (storing your papers, building their knowledge graphs and answering your questions), to keep accounts secure, to reply to your messages, and to understand in aggregate which parts of the service are used. We do not sell your information, we do not show advertising, and we do not use your papers or questions to train AI models.',
        ],
      },
      {
        id: 'ai',
        heading: 'How AI processing works',
        body: [
          'When you run an investigation, your question and the relevant passages of the paper you chose are sent to the AI model configured by the operator, which writes the report. Only that one paper is used.',
          'If the model runs on the operator\'s own servers, this data does not leave them. If the operator uses a third-party AI provider, the question and passages are sent to that provider only to generate the answer, under the provider\'s data-processing terms. The model used is shown next to each report.',
        ],
      },
      {
        id: 'cookies',
        heading: 'Cookies and local storage',
        body: [
          '- rm_session: keeps you signed in. It is essential, cannot be read by page scripts, and expires after at most 7 days or when you sign out.',
          '- rm_csrf: a security token that protects your account against cross-site request forgery. It is essential.',
          '- Local storage in your browser keeps your theme, language, cookie choice and last opened project. It is not sent to us except when you change your settings while signed in.',
          '- Usage statistics use no cookies and are off unless you allow them. You can change your choice at any time with "Cookie settings" at the bottom of the public pages.',
        ],
      },
      {
        id: 'sharing',
        heading: 'Who we share information with',
        body: [
          'Your papers and reports are visible only to your account. We share information only with the infrastructure providers that host the service, with the AI provider described above if one is used, and with authorities when the law requires it. Every provider is allowed to use the information only to provide its service to us.',
        ],
      },
      {
        id: 'retention',
        heading: 'How long we keep information',
        body: [
          'Your papers, knowledge graphs and investigations are kept until you delete them or delete your account. Sessions are removed when they expire or when you sign out. Contact messages are kept as long as needed to answer them. Usage statistics are aggregate counts and contain no personal information.',
        ],
      },
      {
        id: 'security',
        heading: 'Security',
        body: [
          'Connections use HTTPS. Passwords are hashed with Argon2id, sign-in sessions are stored only as hashes, every request is checked against the account that owns the data, each project is stored in its own database graph, and repeated failed sign-ins are blocked. No system is perfectly secure, but we work to protect your information and will inform you of a breach that affects you as required by law.',
        ],
      },
      {
        id: 'rights',
        heading: 'Your rights and choices',
        body: [
          'You can see and correct your name and preferences in Settings, delete individual papers, projects and investigations, download reports, and permanently delete your account and everything in it. Depending on where you live, you may also have the right to request a copy of your data, to object to or restrict processing, and to complain to a data protection authority. To make a request, contact us {contact}.',
        ],
      },
      {
        id: 'children',
        heading: 'Children',
        body: ['ResearchMind AI is not intended for children under 16, and we do not knowingly collect their information.'],
      },
      {
        id: 'changes',
        heading: 'Changes to this policy',
        body: ['If we change this policy, we will update it on this page and change the date at the top. For significant changes we will let account holders know in the app.'],
      },
      {
        id: 'contact',
        heading: 'Contact',
        body: ['For questions about this policy or your information, contact {operator} {contact}.'],
      },
    ],
  },
  terms: {
    title: 'Terms and Conditions',
    description: 'The rules for using ResearchMind AI, your content, AI-generated reports and our responsibilities.',
    intro: 'These terms govern your use of ResearchMind AI, operated by {operator}. By creating an account or using the service, you agree to them. If you do not agree, do not use the service.',
    sections: [
      {
        id: 'accounts',
        heading: 'Your account',
        body: [
          'You must give accurate information, keep your password confidential and tell us if you believe your account has been compromised. You are responsible for activity under your account. An account is for one person.',
        ],
      },
      {
        id: 'content',
        heading: 'Your content',
        body: [
          'You keep all rights to the papers you upload and to your questions. You give us permission to store and process your content only as needed to provide the service to you. You must have the right to upload each file, and you must not upload content that is unlawful or that infringes someone else\'s rights.',
        ],
      },
      {
        id: 'use',
        heading: 'Acceptable use',
        body: [
          '- Do not try to access other users\' accounts or data, or to test, probe or break the service\'s security.',
          '- Do not overload the service, get around its limits, or use automated means to create accounts or send requests.',
          '- Do not use the service to break the law or to process other people\'s personal data without a legal basis.',
        ],
      },
      {
        id: 'ai',
        heading: 'AI-generated reports',
        body: [
          'Reports are written by an AI model from the paper you chose. Although every citation is checked against the paper, AI can misread, omit or overstate information. Reports are research aids, not professional, medical, legal or financial advice. Check important statements against the cited pages before relying on them. Candidate research gaps are hypotheses, not confirmed findings.',
        ],
      },
      {
        id: 'service',
        heading: 'Availability and changes',
        body: [
          'We work to keep the service available and secure, but it is provided "as is" and "as available", without guarantees of uninterrupted operation. We may change, limit or discontinue features. Usage limits apply to keep the service fair and stable.',
        ],
      },
      {
        id: 'termination',
        heading: 'Ending your use',
        body: [
          'You can delete your account at any time in Settings, which permanently deletes your data. We may suspend or close accounts that break these terms or put the service or other users at risk.',
        ],
      },
      {
        id: 'liability',
        heading: 'Liability',
        body: [
          'To the extent permitted by law, {operator} is not liable for indirect or consequential losses, or for decisions made on the basis of AI-generated reports. Nothing in these terms limits liability that cannot be limited by law.',
        ],
      },
      {
        id: 'changes',
        heading: 'Changes to these terms',
        body: ['We may update these terms. We will change the date at the top and, for significant changes, notify account holders in the app. Continuing to use the service after a change means you accept the updated terms.'],
      },
      {
        id: 'contact',
        heading: 'Contact',
        body: ['Questions about these terms can be sent to {operator} {contact}.'],
      },
    ],
  },
}

export default legal
