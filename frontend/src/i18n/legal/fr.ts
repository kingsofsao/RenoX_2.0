import type { LegalTexts } from './types'

const legal: LegalTexts = {
  updated: 'Dernière mise à jour : {date}',
  contactEmail: 'par e-mail à {email} ou via le formulaire de contact de ce site',
  contactForm: 'via le formulaire de contact de ce site',
  contents: 'Sommaire',
  translationNote: 'Ceci est une traduction. En cas de divergence avec la version anglaise, la version anglaise prévaut.',
  privacy: {
    title: 'Politique de confidentialité',
    description: 'Ce que ResearchMind AI collecte, pourquoi, pendant combien de temps, et vos choix.',
    intro: 'Cette politique explique quelles informations ResearchMind AI collecte lorsque vous l’utilisez, comment elles sont utilisées et protégées, et les choix dont vous disposez. ResearchMind AI est exploité par {operator}.',
    sections: [
      {
        id: 'collect',
        heading: 'Informations collectées',
        body: [
          '- Données du compte : votre nom, votre adresse e-mail et vos préférences de langue et de thème. Votre mot de passe n’est jamais conservé ; seule une empreinte Argon2id à sens unique est stockée.',
          '- Contenu que vous ajoutez : les PDF importés, le texte qui en est extrait, le graphe de connaissances construit à partir d’eux, vos questions, les exigences de projet saisies et les rapports générés pour vous.',
          '- Sessions : à la connexion, nous enregistrons le début de la session, sa dernière utilisation et l’identifiant (user agent) de votre navigateur, afin que vous puissiez consulter et fermer vos sessions dans les Paramètres.',
          '- Messages envoyés via le formulaire de contact : votre nom, votre e-mail, le sujet et le message.',
          '- Statistiques d’utilisation, uniquement si vous les autorisez : nombres quotidiens de pages vues et de quelques actions (inscriptions, imports, investigations), regroupés par page et par balise de campagne. Elles ne contiennent ni adresse IP, ni identifiant de compte, ni cookie, et ne peuvent donc pas être reliées à vous.',
          '- Journaux du serveur : enregistrements techniques des requêtes et des erreurs, utilisés pour assurer la sécurité et le bon fonctionnement du service. Ils ne contiennent ni votre mot de passe ni le contenu de vos articles.',
        ],
      },
      { id: 'use', heading: 'Utilisation des informations', body: ['Nous utilisons vos informations pour fournir le service (conserver vos articles, construire leurs graphes de connaissances et répondre à vos questions), sécuriser les comptes, répondre à vos messages et comprendre, de façon agrégée, quelles parties du service sont utilisées. Nous ne vendons pas vos informations, n’affichons pas de publicité et n’utilisons pas vos articles ni vos questions pour entraîner des modèles d’IA.'] },
      {
        id: 'ai',
        heading: 'Traitement par l’IA',
        body: [
          'Lorsque vous lancez une investigation, votre question et les passages pertinents de l’article choisi sont envoyés au modèle d’IA configuré par l’exploitant, qui rédige le rapport. Seul cet article est utilisé.',
          'Si le modèle fonctionne sur les serveurs de l’exploitant, ces données ne les quittent pas. Si l’exploitant utilise un fournisseur d’IA tiers, la question et les passages lui sont envoyés uniquement pour générer la réponse, selon ses conditions de traitement des données. Le modèle utilisé est indiqué à côté de chaque rapport.',
        ],
      },
      {
        id: 'cookies',
        heading: 'Cookies et stockage local',
        body: [
          '- rm_session : vous garde connecté. Il est essentiel, ne peut pas être lu par les scripts de la page et expire au plus tard après 7 jours ou à la déconnexion.',
          '- rm_csrf : un jeton de sécurité qui protège votre compte contre la falsification de requêtes intersites. Il est essentiel.',
          '- Le stockage local de votre navigateur conserve votre thème, votre langue, votre choix de cookies et le dernier projet ouvert. Il ne nous est pas transmis, sauf lorsque vous modifiez vos préférences en étant connecté.',
          '- Les statistiques d’utilisation n’utilisent pas de cookies et restent désactivées tant que vous ne les autorisez pas. Vous pouvez changer d’avis à tout moment via « Paramètres des cookies » en bas des pages publiques.',
        ],
      },
      { id: 'sharing', heading: 'Partage des informations', body: ['Vos articles et rapports ne sont visibles que par votre compte. Nous ne partageons des informations qu’avec les prestataires d’infrastructure qui hébergent le service, avec le fournisseur d’IA décrit ci-dessus s’il y en a un, et avec les autorités lorsque la loi l’exige. Chaque prestataire ne peut utiliser ces informations que pour nous fournir son service.'] },
      { id: 'retention', heading: 'Durée de conservation', body: ['Vos articles, graphes de connaissances et investigations sont conservés jusqu’à ce que vous les supprimiez ou supprimiez votre compte. Les sessions sont supprimées à leur expiration ou à la déconnexion. Les messages de contact sont conservés le temps nécessaire pour y répondre. Les statistiques d’utilisation sont des comptages agrégés sans information personnelle.'] },
      { id: 'security', heading: 'Sécurité', body: ['Les connexions utilisent HTTPS. Les mots de passe sont protégés par Argon2id, les sessions ne sont stockées que sous forme d’empreintes, chaque requête est vérifiée par rapport au compte propriétaire des données, chaque projet est stocké dans son propre graphe de base de données et les échecs de connexion répétés sont bloqués. Aucun système n’est parfaitement sûr, mais nous protégeons vos informations et vous informerons de toute violation vous concernant, comme la loi l’exige.'] },
      { id: 'rights', heading: 'Vos droits et choix', body: ['Vous pouvez consulter et corriger votre nom et vos préférences dans les Paramètres, supprimer des articles, projets et investigations, télécharger des rapports et supprimer définitivement votre compte et tout son contenu. Selon votre lieu de résidence, vous pouvez aussi avoir le droit d’obtenir une copie de vos données, de vous opposer au traitement ou de le limiter, et d’introduire une réclamation auprès d’une autorité de protection des données. Pour toute demande, contactez-nous {contact}.'] },
      { id: 'children', heading: 'Enfants', body: ['ResearchMind AI ne s’adresse pas aux enfants de moins de 16 ans, et nous ne collectons pas sciemment leurs informations.'] },
      { id: 'changes', heading: 'Modifications de cette politique', body: ['Si nous modifions cette politique, nous la mettrons à jour sur cette page et changerons la date en haut. Pour les changements importants, nous informerons les titulaires de compte dans l’application.'] },
      { id: 'contact', heading: 'Contact', body: ['Pour toute question sur cette politique ou vos informations, contactez {operator} {contact}.'] },
    ],
  },
  terms: {
    title: 'Conditions générales',
    description: 'Les règles d’utilisation de ResearchMind AI, votre contenu, les rapports générés par l’IA et nos responsabilités.',
    intro: 'Ces conditions régissent votre utilisation de ResearchMind AI, exploité par {operator}. En créant un compte ou en utilisant le service, vous les acceptez. Si vous ne les acceptez pas, n’utilisez pas le service.',
    sections: [
      { id: 'accounts', heading: 'Votre compte', body: ['Vous devez fournir des informations exactes, garder votre mot de passe confidentiel et nous prévenir si vous pensez que votre compte a été compromis. Vous êtes responsable de l’activité de votre compte. Un compte est destiné à une seule personne.'] },
      { id: 'content', heading: 'Votre contenu', body: ['Vous conservez tous les droits sur les articles importés et sur vos questions. Vous nous autorisez à stocker et traiter votre contenu uniquement dans la mesure nécessaire pour vous fournir le service. Vous devez avoir le droit d’importer chaque fichier et ne devez pas importer de contenu illicite ou portant atteinte aux droits d’autrui.'] },
      {
        id: 'use',
        heading: 'Utilisation acceptable',
        body: [
          '- N’essayez pas d’accéder aux comptes ou aux données d’autres utilisateurs, ni de tester, sonder ou contourner la sécurité du service.',
          '- Ne surchargez pas le service, ne contournez pas ses limites et n’utilisez pas de moyens automatisés pour créer des comptes ou envoyer des requêtes.',
          '- N’utilisez pas le service pour enfreindre la loi ou pour traiter les données personnelles d’autrui sans base légale.',
        ],
      },
      { id: 'ai', heading: 'Rapports générés par l’IA', body: ['Les rapports sont rédigés par un modèle d’IA à partir de l’article choisi. Même si chaque citation est vérifiée dans l’article, l’IA peut mal interpréter, omettre ou exagérer des informations. Les rapports sont une aide à la recherche, pas un conseil professionnel, médical, juridique ou financier. Vérifiez les affirmations importantes aux pages citées avant de vous y fier. Les pistes de recherche possibles sont des hypothèses, pas des résultats confirmés.'] },
      { id: 'service', heading: 'Disponibilité et évolutions', body: ['Nous nous efforçons de garder le service disponible et sûr, mais il est fourni « en l’état » et « selon disponibilité », sans garantie de fonctionnement ininterrompu. Nous pouvons modifier, limiter ou arrêter des fonctionnalités. Des limites d’utilisation s’appliquent pour que le service reste équitable et stable.'] },
      { id: 'termination', heading: 'Fin de l’utilisation', body: ['Vous pouvez supprimer votre compte à tout moment dans les Paramètres, ce qui supprime définitivement vos données. Nous pouvons suspendre ou fermer les comptes qui enfreignent ces conditions ou mettent en danger le service ou d’autres utilisateurs.'] },
      { id: 'liability', heading: 'Responsabilité', body: ['Dans la mesure permise par la loi, {operator} n’est pas responsable des pertes indirectes ou consécutives, ni des décisions prises sur la base de rapports générés par l’IA. Rien dans ces conditions ne limite une responsabilité que la loi ne permet pas de limiter.'] },
      { id: 'changes', heading: 'Modifications de ces conditions', body: ['Nous pouvons mettre à jour ces conditions. Nous changerons la date en haut et, pour les changements importants, informerons les titulaires de compte dans l’application. Continuer à utiliser le service après une modification vaut acceptation des conditions mises à jour.'] },
      { id: 'contact', heading: 'Contact', body: ['Les questions sur ces conditions peuvent être adressées à {operator} {contact}.'] },
    ],
  },
}

export default legal
