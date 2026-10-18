import type { LegalTexts } from './types'

const legal: LegalTexts = {
  updated: 'Zuletzt aktualisiert am {date}',
  contactEmail: 'per E-Mail an {email} oder über das Kontaktformular dieser Website',
  contactForm: 'über das Kontaktformular dieser Website',
  contents: 'Inhalt',
  translationNote: 'Dies ist eine Übersetzung. Bei Abweichungen gilt die englische Fassung.',
  privacy: {
    title: 'Datenschutzerklärung',
    description: 'Welche Daten ResearchMind AI erhebt, wozu, wie lange sie gespeichert werden und welche Wahlmöglichkeiten Sie haben.',
    intro: 'Diese Erklärung beschreibt, welche Informationen ResearchMind AI bei der Nutzung erhebt, wie sie verwendet und geschützt werden und welche Wahlmöglichkeiten Sie haben. ResearchMind AI wird betrieben von {operator}.',
    sections: [
      {
        id: 'collect',
        heading: 'Welche Informationen wir erheben',
        body: [
          '- Kontodaten: Ihr Name, Ihre E-Mail-Adresse sowie Ihre Sprach- und Design-Einstellungen. Ihr Passwort wird nie gespeichert, nur ein nicht umkehrbarer Argon2id-Hash davon.',
          '- Von Ihnen hinzugefügte Inhalte: hochgeladene PDF-Dateien, der daraus extrahierte Text, der daraus erstellte Wissensgraph, Ihre Fragen, eingegebene Projektanforderungen und die für Sie erstellten Berichte.',
          '- Anmeldesitzungen: Bei der Anmeldung speichern wir, wann die Sitzung begann, wann sie zuletzt genutzt wurde und die Kennung (User-Agent) Ihres Browsers, damit Sie Sitzungen in den Einstellungen prüfen und beenden können.',
          '- Nachrichten über das Kontaktformular: Ihr Name, Ihre E-Mail-Adresse, das Thema und die Nachricht.',
          '- Nutzungsstatistiken, nur wenn Sie zustimmen: tägliche Zahlen zu Seitenaufrufen und einigen Aktionen (Registrierungen, Uploads, Untersuchungen), gruppiert nach Seite und Kampagnenkennzeichen. Sie enthalten keine IP-Adresse, keine Kontokennung und kein Cookie und können daher nicht mit Ihnen verknüpft werden.',
          '- Serverprotokolle: technische Aufzeichnungen von Anfragen und Fehlern, um den Dienst sicher und funktionsfähig zu halten. Sie enthalten weder Ihr Passwort noch den Inhalt Ihrer Paper.',
        ],
      },
      { id: 'use', heading: 'Wie wir Informationen verwenden', body: ['Wir verwenden Ihre Informationen, um den Dienst bereitzustellen (Ihre Paper speichern, ihre Wissensgraphen erstellen und Ihre Fragen beantworten), Konten zu schützen, Ihre Nachrichten zu beantworten und in zusammengefasster Form zu verstehen, welche Teile des Dienstes genutzt werden. Wir verkaufen Ihre Informationen nicht, zeigen keine Werbung und verwenden Ihre Paper und Fragen nicht zum Training von KI-Modellen.'] },
      {
        id: 'ai',
        heading: 'Wie die KI-Verarbeitung funktioniert',
        body: [
          'Wenn Sie eine Untersuchung starten, werden Ihre Frage und die relevanten Textstellen des gewählten Papers an das vom Betreiber konfigurierte KI-Modell gesendet, das den Bericht verfasst. Es wird nur dieses eine Paper verwendet.',
          'Läuft das Modell auf den eigenen Servern des Betreibers, verlassen diese Daten diese Server nicht. Nutzt der Betreiber einen externen KI-Anbieter, werden Frage und Textstellen nur zur Erstellung der Antwort an diesen Anbieter übermittelt, gemäß dessen Bedingungen zur Datenverarbeitung. Das verwendete Modell wird neben jedem Bericht angezeigt.',
        ],
      },
      {
        id: 'cookies',
        heading: 'Cookies und lokaler Speicher',
        body: [
          '- rm_session: hält Sie angemeldet. Es ist notwendig, kann von Skripten der Seite nicht gelesen werden und läuft spätestens nach 7 Tagen oder bei der Abmeldung ab.',
          '- rm_csrf: ein Sicherheitstoken, das Ihr Konto vor seitenübergreifender Anfragenfälschung schützt. Es ist notwendig.',
          '- Im lokalen Speicher Ihres Browsers werden Design, Sprache, Cookie-Auswahl und das zuletzt geöffnete Projekt gespeichert. Diese Daten werden nur an uns gesendet, wenn Sie angemeldet Ihre Einstellungen ändern.',
          '- Nutzungsstatistiken verwenden keine Cookies und bleiben ausgeschaltet, solange Sie sie nicht erlauben. Ihre Auswahl können Sie jederzeit über „Cookie-Einstellungen“ unten auf den öffentlichen Seiten ändern.',
        ],
      },
      { id: 'sharing', heading: 'An wen wir Informationen weitergeben', body: ['Ihre Paper und Berichte sind nur für Ihr Konto sichtbar. Wir geben Informationen nur an die Infrastrukturanbieter weiter, die den Dienst hosten, an den oben beschriebenen KI-Anbieter, falls einer genutzt wird, und an Behörden, wenn das Gesetz es verlangt. Jeder Anbieter darf die Informationen nur zur Erbringung seiner Leistung für uns verwenden.'] },
      { id: 'retention', heading: 'Wie lange wir Informationen speichern', body: ['Ihre Paper, Wissensgraphen und Untersuchungen werden gespeichert, bis Sie sie oder Ihr Konto löschen. Sitzungen werden entfernt, wenn sie ablaufen oder Sie sich abmelden. Kontaktnachrichten werden so lange aufbewahrt, wie es für die Antwort nötig ist. Nutzungsstatistiken sind zusammengefasste Zahlen ohne personenbezogene Daten.'] },
      { id: 'security', heading: 'Sicherheit', body: ['Verbindungen nutzen HTTPS. Passwörter werden mit Argon2id gehasht, Anmeldesitzungen nur als Hash gespeichert, jede Anfrage wird gegen das Konto geprüft, dem die Daten gehören, jedes Projekt liegt in einem eigenen Datenbankgraphen, und wiederholte Fehlanmeldungen werden gesperrt. Kein System ist vollkommen sicher, aber wir schützen Ihre Informationen und informieren Sie über eine Sie betreffende Datenpanne, wie gesetzlich vorgeschrieben.'] },
      { id: 'rights', heading: 'Ihre Rechte und Wahlmöglichkeiten', body: ['Sie können Ihren Namen und Ihre Einstellungen in den Einstellungen einsehen und ändern, einzelne Paper, Projekte und Untersuchungen löschen, Berichte herunterladen und Ihr Konto mit allen Inhalten dauerhaft löschen. Je nach Wohnort haben Sie möglicherweise auch das Recht auf eine Kopie Ihrer Daten, auf Widerspruch gegen oder Einschränkung der Verarbeitung sowie auf Beschwerde bei einer Datenschutzbehörde. Für eine Anfrage kontaktieren Sie uns {contact}.'] },
      { id: 'children', heading: 'Kinder', body: ['ResearchMind AI richtet sich nicht an Kinder unter 16 Jahren, und wir erheben wissentlich keine Daten von ihnen.'] },
      { id: 'changes', heading: 'Änderungen dieser Erklärung', body: ['Wenn wir diese Erklärung ändern, aktualisieren wir sie auf dieser Seite und ändern das Datum oben. Über wesentliche Änderungen informieren wir Kontoinhaber in der App.'] },
      { id: 'contact', heading: 'Kontakt', body: ['Bei Fragen zu dieser Erklärung oder zu Ihren Daten wenden Sie sich an {operator} {contact}.'] },
    ],
  },
  terms: {
    title: 'Nutzungsbedingungen',
    description: 'Die Regeln für die Nutzung von ResearchMind AI, Ihre Inhalte, KI-generierte Berichte und unsere Verantwortung.',
    intro: 'Diese Bedingungen regeln Ihre Nutzung von ResearchMind AI, betrieben von {operator}. Mit dem Erstellen eines Kontos oder der Nutzung des Dienstes stimmen Sie ihnen zu. Wenn Sie nicht zustimmen, nutzen Sie den Dienst nicht.',
    sections: [
      { id: 'accounts', heading: 'Ihr Konto', body: ['Sie müssen zutreffende Angaben machen, Ihr Passwort geheim halten und uns informieren, wenn Sie glauben, dass Ihr Konto kompromittiert wurde. Sie sind für die Aktivitäten Ihres Kontos verantwortlich. Ein Konto ist für eine Person bestimmt.'] },
      { id: 'content', heading: 'Ihre Inhalte', body: ['Sie behalten alle Rechte an den hochgeladenen Papern und an Ihren Fragen. Sie erlauben uns, Ihre Inhalte nur so weit zu speichern und zu verarbeiten, wie es zur Bereitstellung des Dienstes nötig ist. Sie müssen zum Hochladen jeder Datei berechtigt sein und dürfen keine rechtswidrigen oder fremde Rechte verletzenden Inhalte hochladen.'] },
      {
        id: 'use',
        heading: 'Zulässige Nutzung',
        body: [
          '- Versuchen Sie nicht, auf Konten oder Daten anderer Nutzer zuzugreifen oder die Sicherheit des Dienstes zu testen, auszuspähen oder zu umgehen.',
          '- Überlasten Sie den Dienst nicht, umgehen Sie keine Grenzen und verwenden Sie keine automatisierten Mittel, um Konten zu erstellen oder Anfragen zu senden.',
          '- Nutzen Sie den Dienst nicht für Rechtsverstöße oder zur Verarbeitung personenbezogener Daten anderer ohne Rechtsgrundlage.',
        ],
      },
      { id: 'ai', heading: 'KI-generierte Berichte', body: ['Berichte werden von einem KI-Modell aus dem gewählten Paper verfasst. Obwohl jedes Zitat am Paper geprüft wird, kann die KI Informationen falsch lesen, auslassen oder überzeichnen. Berichte sind Hilfsmittel für die Forschung, keine fachliche, medizinische, rechtliche oder finanzielle Beratung. Prüfen Sie wichtige Aussagen auf den zitierten Seiten, bevor Sie sich darauf verlassen. Mögliche Forschungslücken sind Hypothesen, keine bestätigten Ergebnisse.'] },
      { id: 'service', heading: 'Verfügbarkeit und Änderungen', body: ['Wir bemühen uns, den Dienst verfügbar und sicher zu halten, er wird jedoch „wie besehen“ und „wie verfügbar“ bereitgestellt, ohne Garantie eines unterbrechungsfreien Betriebs. Wir können Funktionen ändern, einschränken oder einstellen. Nutzungsgrenzen sorgen für einen fairen und stabilen Betrieb.'] },
      { id: 'termination', heading: 'Beendigung der Nutzung', body: ['Sie können Ihr Konto jederzeit in den Einstellungen löschen; Ihre Daten werden dabei dauerhaft gelöscht. Wir können Konten sperren oder schließen, die gegen diese Bedingungen verstoßen oder den Dienst oder andere Nutzer gefährden.'] },
      { id: 'liability', heading: 'Haftung', body: ['Soweit gesetzlich zulässig, haftet {operator} nicht für mittelbare Schäden oder Folgeschäden und nicht für Entscheidungen, die auf Grundlage KI-generierter Berichte getroffen werden. Eine Haftung, die gesetzlich nicht beschränkt werden kann, bleibt unberührt.'] },
      { id: 'changes', heading: 'Änderungen dieser Bedingungen', body: ['Wir können diese Bedingungen aktualisieren. Wir ändern dann das Datum oben und informieren Kontoinhaber bei wesentlichen Änderungen in der App. Wenn Sie den Dienst nach einer Änderung weiter nutzen, gelten die aktualisierten Bedingungen als akzeptiert.'] },
      { id: 'contact', heading: 'Kontakt', body: ['Fragen zu diesen Bedingungen richten Sie an {operator} {contact}.'] },
    ],
  },
}

export default legal
