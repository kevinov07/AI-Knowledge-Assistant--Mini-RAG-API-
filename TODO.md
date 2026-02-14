# AI Knowledge Assistant - TODO

## Posibles bugs (por verificar)

### Carga de archivos (posible bug en frontend)

- **Síntoma:** Al subir archivos una primera vez y luego volver a subir (otra tanda o los mismos), parece que se reenvían también los que ya se habían subido antes.
- **Hipótesis:** Comportamiento del frontend (p. ej. el input de archivos no se limpia o se reutiliza la misma selección). Aún no verificado del lado backend.
- **Qué comprobar:** Si el backend recibe en cada petición solo los archivos que el usuario eligió en esa acción, o si por algún motivo llegan duplicados/repetidos.

## Features pendientes

### 🔔 Notificaciones

- [ ] **Sistema de notificaciones toast/alert**
  - Notificación de éxito al cargar documentos correctamente
  - Notificación de error cuando falla la carga
  - Mostrar detalles específicos de los errores (qué documentos fallaron y por qué)
  - Indicador visual durante el proceso de carga
  - Lista de documentos procesados con su estado (exitoso/fallido)

### 📝 Gestión de documentos

- [ ] **Crear documentos en la app**
  - Agregar funcionalidad para crear documentos directamente escribiendo texto en un input dentro de la aplicación
  - Permitir editar y guardar documentos creados

- [ ] **Visualización de documentos en el frontend (preview por texto)**
  - Usar el texto plano que devuelve `GET /api/documents/{id}/text` para mostrar una vista previa del documento (solo visualización, no descarga del archivo original).
  - Variar la presentación según la extensión del archivo (`filename`): `.md` → renderizar como Markdown; `.txt` → texto con saltos de línea; `.pdf`/`.docx` → mismo texto en vista tipo documento (legible); `.csv` → opcionalmente parsear y mostrar como tabla.
  - Objetivo: que el usuario vea qué contenido está indexado sin guardar ni servir el binario original.

- [x] **Soporte para múltiples formatos**
  - ✅ Formatos soportados en el backend (según `DocumentProcessor`):
    - `.txt` — texto plano
    - `.pdf` — PDF
    - `.docx` — Word
    - `.md` — Markdown
    - `.csv` — CSV (convertido a texto estructurado)
    - `.xlsx` — Excel (nuevo)
    - `.xls` — Excel (legacy)

### 📚 Sistema de colecciones

- [ ] **Colecciones de documentos**
  - Permitir a los usuarios crear colecciones personalizadas de documentos
  - Características:
    - **Colecciones públicas**: accesibles para todos
    - **Colecciones privadas**: protegidas con clave/código de acceso
    - Selector de colección para elegir el contexto en las consultas

- [ ] **Backend para colecciones**
  - Implementar base de datos para gestionar colecciones
  - API endpoints para CRUD de colecciones
  - Validación de contraseña simple para colecciones privadas (sin sistema de usuarios)
  - Lógica para seleccionar contexto de colecciones específicas

### 📄 Filtro por documento / nombre en contexto (RAG)

- [ ] **Incluir nombre del documento en el contexto enviado al LLM**
  - Prefijar cada fragmento con el `filename` al armar el contexto (ej. `"[kevin-cv-español.pdf]\n" + texto`), para que el modelo sepa de qué documento viene cada parte y pueda priorizar o citar mejor.
- [ ] **Filtro por documento cuando el usuario menciona uno**
  - Detectar en la pregunta mención a un documento (nombre de archivo, "el CV", "en el documento X", coincidencia con `documents.filename`).
  - Restringir la búsqueda semántica a ese documento: en `similarity_search_chunks_pgvector` añadir filtro `WHERE document_id = :doc_id` (o lista de candidatos) para que los k chunks salgan solo de ese doc.

### 🔄 Reintentar respuesta (mejor contexto)

- [ ] **Botón "Reintentar" en el frontend**
  - Si el usuario no está satisfecho con la respuesta, poder pulsar "Reintentar" sin cambiar la pregunta.
  - **Comportamiento:** Al reintentar, el frontend vuelve a llamar a `POST /api/ask` con la misma pregunta pero con más contexto (p. ej. `k` mayor o un parámetro opcional para ampliar el `window`), para que el modelo reciba más chunks y pueda dar una respuesta más completa.
  - Backend: opcionalmente aceptar un parámetro tipo `retry_with_more_context=true` que aumente `k` o el window interno; o que el frontend envíe directamente un `k` mayor en el body.

### 💬 Historial de chat (contexto de conversación)

- [ ] **Guardar y usar historial de chat para que el LLM tenga contexto**
  - Hoy cada `POST /api/ask` es una petición aislada: no se envía al LLM la pregunta ni la respuesta anteriores, por eso preguntas de seguimiento ("amplía detalles", "¿y las tecnologías?") no tienen contexto.
  - Objetivo: que el modelo reciba las últimas N vueltas (pregunta + respuesta) además de la pregunta actual y el contexto RAG, para poder responder como en una conversación.
  - Backend: aceptar en el body un historial opcional (lista de `{ role: "user"|"assistant", content: string }`) o un `session_id` y recuperar historial desde BD; incluir ese historial en el prompt que se envía a Groq (respetando límite de contexto del modelo).
  - Frontend: mantener en estado (o en BD/localStorage) el historial del chat y enviarlo en cada nueva pregunta; opción de "nueva conversación" para limpiar historial.

## Configuración Completada

- [x] Variables de entorno para API URL
- [x] Build con SSR funcionando
- [x] Configuración de despliegue en Vercel