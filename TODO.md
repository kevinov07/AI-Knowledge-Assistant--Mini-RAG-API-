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

### 🔄 Reintentar respuesta (mejor contexto)

- [ ] **Botón "Reintentar" en el frontend**
  - Si el usuario no está satisfecho con la respuesta, poder pulsar "Reintentar" sin cambiar la pregunta.
  - **Comportamiento:** Al reintentar, el frontend vuelve a llamar a `POST /api/ask` con la misma pregunta pero con más contexto (p. ej. `k` mayor o un parámetro opcional para ampliar el `window`), para que el modelo reciba más chunks y pueda dar una respuesta más completa.
  - Backend: opcionalmente aceptar un parámetro tipo `retry_with_more_context=true` que aumente `k` o el window interno; o que el frontend envíe directamente un `k` mayor en el body.


## Configuración Completada

- [x] Variables de entorno para API URL
- [x] Build con SSR funcionando
- [x] Configuración de despliegue en Vercel