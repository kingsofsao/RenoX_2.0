import type { LegalTexts } from './types'

const legal: LegalTexts = {
  updated: 'Última actualización: {date}',
  contactEmail: 'por correo electrónico en {email} o mediante el formulario de contacto de este sitio',
  contactForm: 'mediante el formulario de contacto de este sitio',
  contents: 'Contenido',
  translationNote: 'Esta es una traducción. Si difiere de la versión en inglés, prevalece la versión en inglés.',
  privacy: {
    title: 'Política de privacidad',
    description: 'Qué recopila ResearchMind AI, por qué, durante cuánto tiempo y qué opciones tienes.',
    intro: 'Esta política explica qué información recopila ResearchMind AI cuando lo usas, cómo se utiliza y protege, y qué opciones tienes. ResearchMind AI está operado por {operator}.',
    sections: [
      {
        id: 'collect',
        heading: 'Información que recopilamos',
        body: [
          '- Datos de la cuenta: tu nombre, tu correo electrónico y tus preferencias de idioma y tema. Tu contraseña nunca se guarda; solo se conserva un hash Argon2id de un solo sentido.',
          '- Contenido que añades: los PDF que subes, el texto extraído de ellos, el grafo de conocimiento construido a partir de ellos, tus preguntas, los requisitos de proyecto que introduzcas y los informes generados para ti.',
          '- Sesiones: al iniciar sesión registramos cuándo empezó la sesión, cuándo se usó por última vez y el identificador (user agent) de tu navegador, para que puedas revisar y cerrar sesiones en Configuración.',
          '- Mensajes que nos envías con el formulario de contacto: tu nombre, correo electrónico, tema y mensaje.',
          '- Estadísticas de uso, solo si las permites: recuentos diarios de visitas a páginas y de algunas acciones (registros, subidas, investigaciones), agrupados por página y por etiqueta de campaña. No contienen dirección IP, identificador de cuenta ni cookies, por lo que no pueden vincularse contigo.',
          '- Registros del servidor: registros técnicos de solicitudes y errores, usados para mantener el servicio seguro y operativo. No contienen tu contraseña ni el contenido de tus artículos.',
        ],
      },
      {
        id: 'use',
        heading: 'Cómo usamos la información',
        body: ['Usamos tu información para prestar el servicio (guardar tus artículos, construir sus grafos de conocimiento y responder a tus preguntas), mantener las cuentas seguras, responder a tus mensajes y entender, de forma agregada, qué partes del servicio se usan. No vendemos tu información, no mostramos publicidad y no usamos tus artículos ni tus preguntas para entrenar modelos de IA.'],
      },
      {
        id: 'ai',
        heading: 'Cómo funciona el procesamiento con IA',
        body: [
          'Cuando ejecutas una investigación, tu pregunta y los fragmentos relevantes del artículo elegido se envían al modelo de IA configurado por el operador, que redacta el informe. Solo se usa ese artículo.',
          'Si el modelo se ejecuta en los servidores del operador, estos datos no salen de ellos. Si el operador usa un proveedor de IA externo, la pregunta y los fragmentos se envían a ese proveedor solo para generar la respuesta, según sus condiciones de tratamiento de datos. El modelo usado se muestra junto a cada informe.',
        ],
      },
      {
        id: 'cookies',
        heading: 'Cookies y almacenamiento local',
        body: [
          '- rm_session: mantiene tu sesión iniciada. Es esencial, los scripts de la página no pueden leerla y caduca como máximo a los 7 días o al cerrar sesión.',
          '- rm_csrf: un token de seguridad que protege tu cuenta frente a la falsificación de peticiones entre sitios. Es esencial.',
          '- El almacenamiento local de tu navegador guarda tu tema, idioma, elección de cookies y el último proyecto abierto. No se nos envía, salvo cuando cambias tus preferencias con la sesión iniciada.',
          '- Las estadísticas de uso no usan cookies y están desactivadas salvo que las permitas. Puedes cambiar tu elección en cualquier momento con "Configuración de cookies" al pie de las páginas públicas.',
        ],
      },
      {
        id: 'sharing',
        heading: 'Con quién compartimos información',
        body: ['Tus artículos e informes solo son visibles para tu cuenta. Solo compartimos información con los proveedores de infraestructura que alojan el servicio, con el proveedor de IA descrito arriba si se usa uno, y con las autoridades cuando la ley lo exige. Cada proveedor solo puede usar la información para prestarnos su servicio.'],
      },
      {
        id: 'retention',
        heading: 'Cuánto tiempo conservamos la información',
        body: ['Tus artículos, grafos de conocimiento e investigaciones se conservan hasta que los eliminas o eliminas tu cuenta. Las sesiones se eliminan al caducar o al cerrar sesión. Los mensajes de contacto se conservan el tiempo necesario para responderlos. Las estadísticas de uso son recuentos agregados y no contienen información personal.'],
      },
      {
        id: 'security',
        heading: 'Seguridad',
        body: ['Las conexiones usan HTTPS. Las contraseñas se protegen con Argon2id, las sesiones se guardan solo como hashes, cada petición se comprueba con la cuenta propietaria de los datos, cada proyecto se guarda en su propio grafo de base de datos y se bloquean los inicios de sesión fallidos repetidos. Ningún sistema es perfectamente seguro, pero trabajamos para proteger tu información y te informaremos de cualquier brecha que te afecte según exija la ley.'],
      },
      {
        id: 'rights',
        heading: 'Tus derechos y opciones',
        body: ['Puedes ver y corregir tu nombre y tus preferencias en Configuración, eliminar artículos, proyectos e investigaciones, descargar informes y eliminar de forma permanente tu cuenta y todo su contenido. Según dónde vivas, también puedes tener derecho a solicitar una copia de tus datos, a oponerte al tratamiento o limitarlo, y a presentar una reclamación ante una autoridad de protección de datos. Para hacer una solicitud, contacta con nosotros {contact}.'],
      },
      {
        id: 'children',
        heading: 'Menores',
        body: ['ResearchMind AI no está dirigido a menores de 16 años y no recopilamos conscientemente su información.'],
      },
      {
        id: 'changes',
        heading: 'Cambios en esta política',
        body: ['Si cambiamos esta política, la actualizaremos en esta página y cambiaremos la fecha de arriba. Si los cambios son importantes, avisaremos a los titulares de cuentas en la aplicación.'],
      },
      {
        id: 'contact',
        heading: 'Contacto',
        body: ['Para preguntas sobre esta política o tu información, contacta con {operator} {contact}.'],
      },
    ],
  },
  terms: {
    title: 'Términos y condiciones',
    description: 'Las normas de uso de ResearchMind AI, tu contenido, los informes generados por IA y nuestras responsabilidades.',
    intro: 'Estos términos regulan tu uso de ResearchMind AI, operado por {operator}. Al crear una cuenta o usar el servicio, los aceptas. Si no estás de acuerdo, no uses el servicio.',
    sections: [
      { id: 'accounts', heading: 'Tu cuenta', body: ['Debes facilitar información veraz, mantener tu contraseña en secreto y avisarnos si crees que tu cuenta se ha visto comprometida. Eres responsable de la actividad de tu cuenta. Una cuenta es para una sola persona.'] },
      { id: 'content', heading: 'Tu contenido', body: ['Conservas todos los derechos sobre los artículos que subes y sobre tus preguntas. Nos das permiso para guardar y procesar tu contenido solo en la medida necesaria para prestarte el servicio. Debes tener derecho a subir cada archivo y no debes subir contenido ilícito o que infrinja derechos de terceros.'] },
      {
        id: 'use',
        heading: 'Uso aceptable',
        body: [
          '- No intentes acceder a cuentas o datos de otros usuarios, ni probar, sondear o vulnerar la seguridad del servicio.',
          '- No sobrecargues el servicio, no eludas sus límites ni uses medios automatizados para crear cuentas o enviar peticiones.',
          '- No uses el servicio para infringir la ley ni para tratar datos personales de otras personas sin base legal.',
        ],
      },
      { id: 'ai', heading: 'Informes generados por IA', body: ['Los informes los redacta un modelo de IA a partir del artículo que eliges. Aunque cada cita se comprueba con el artículo, la IA puede malinterpretar, omitir o exagerar información. Los informes son una ayuda para la investigación, no asesoramiento profesional, médico, jurídico ni financiero. Comprueba las afirmaciones importantes en las páginas citadas antes de basarte en ellas. Las posibles lagunas de investigación son hipótesis, no hallazgos confirmados.'] },
      { id: 'service', heading: 'Disponibilidad y cambios', body: ['Trabajamos para que el servicio esté disponible y sea seguro, pero se ofrece "tal cual" y "según disponibilidad", sin garantía de funcionamiento ininterrumpido. Podemos cambiar, limitar o suspender funciones. Se aplican límites de uso para que el servicio sea justo y estable.'] },
      { id: 'termination', heading: 'Fin del uso', body: ['Puedes eliminar tu cuenta en cualquier momento en Configuración, lo que borra tus datos de forma permanente. Podemos suspender o cerrar cuentas que incumplan estos términos o pongan en riesgo el servicio o a otros usuarios.'] },
      { id: 'liability', heading: 'Responsabilidad', body: ['En la medida en que lo permita la ley, {operator} no es responsable de pérdidas indirectas o consecuentes, ni de decisiones tomadas a partir de informes generados por IA. Nada en estos términos limita la responsabilidad que la ley no permite limitar.'] },
      { id: 'changes', heading: 'Cambios en estos términos', body: ['Podemos actualizar estos términos. Cambiaremos la fecha de arriba y, si los cambios son importantes, avisaremos a los titulares de cuentas en la aplicación. Seguir usando el servicio después de un cambio supone aceptar los términos actualizados.'] },
      { id: 'contact', heading: 'Contacto', body: ['Puedes enviar tus preguntas sobre estos términos a {operator} {contact}.'] },
    ],
  },
}

export default legal
