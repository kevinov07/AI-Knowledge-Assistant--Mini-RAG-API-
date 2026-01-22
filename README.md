# AI Knowledge Assistant - Mini RAG API

API de inteligencia artificial para consultas sobre documentos utilizando RAG (Retrieval-Augmented Generation).

## 🚀 Características

- Procesamiento y análisis de documentos
- Sistema de embeddings con Sentence Transformers
- Búsqueda semántica con FAISS
- Generación de respuestas con Groq LLM
- API RESTful con FastAPI
- Soporte para archivos de texto y PDF

## 📋 Requisitos

- Python 3.12+
- pip

## 🛠️ Instalación Local

1. Clona el repositorio:
```bash
git clone <repository-url>
cd "AI Knowledge Assistant (Mini-RAG API)"
```

2. Crea y activa el entorno virtual:
```bash
python -m venv venv
# Windows
venv\Scripts\activate
# Linux/Mac
source venv/bin/activate
```

3. Instala las dependencias:
```bash
pip install -r requirements.txt
```

4. Configura las variables de entorno:
```bash
cp .env.example .env
# Edita .env con tus valores
```

5. Inicia el servidor:
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

La API estará disponible en `http://localhost:8000`

## 🌐 Despliegue en Producción

### 🔵 Azure for Students (Recomendado)

**Despliegue con Docker + CI/CD automático**

Ver guía completa: [AZURE_DEPLOYMENT.md](./AZURE_DEPLOYMENT.md)

```bash
# 1. Crear recursos en Azure (Container Registry + Web App)
# 2. Configurar GitHub Secrets
# 3. Push a GitHub → Auto-deploy ✅
```

**Ventajas:**
- ✅ CI/CD automático con GitHub Actions
- ✅ Docker para builds consistentes
- ✅ $100 USD crédito gratis (12 meses)
- ✅ Escalable y profesional

### Despliegue en Render (Alternativa)

### Opción 1: Usando render.yaml (Recomendado)

1. Conecta tu repositorio a Render
2. Render detectará automáticamente el archivo `render.yaml`
3. Configura las variables de entorno en el dashboard de Render:
   - `GROQ_API_KEY`: Tu API key de Groq
   - `FRONTEND_URL`: URL de tu frontend en producción
   - `ALLOWED_ORIGINS`: Orígenes permitidos (opcional)

### Opción 2: Configuración Manual

1. Crea un nuevo Web Service en Render
2. Conecta tu repositorio
3. Configura los siguientes valores:
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   - **Environment**: Python 3
4. Agrega las variables de entorno necesarias

### Variables de Entorno Requeridas

| Variable | Descripción | Requerida |
|----------|-------------|-----------|
| `ENV` | Entorno de ejecución (`development` o `production`) | No (default: development) |
| `GROQ_API_KEY` | API Key de Groq para el LLM | Sí |
| `FRONTEND_URL` | URL del frontend en producción | Sí (producción) |
| `ALLOWED_ORIGINS` | Orígenes permitidos para CORS (separados por coma) | No |

## 📚 Endpoints Principales

### Health Check
```
GET /api/health
```

### Subir Documento
```
POST /api/upload
Content-Type: multipart/form-data
Body: file (documento a procesar)
```

### Agregar Texto
```
POST /api/text
Content-Type: application/json
Body: {
  "text": "texto a agregar",
  "metadata": {...}
}
```

### Hacer Pregunta
```
POST /api/ask
Content-Type: application/json
Body: {
  "query": "tu pregunta aquí"
}
```

## 📖 Documentación API

Una vez iniciado el servidor en modo desarrollo, accede a:
- Swagger UI: `http://localhost:8000/api/docs`
- ReDoc: `http://localhost:8000/api/redoc`

> **Nota**: En producción, la documentación está deshabilitada por seguridad.

## 🏗️ Estructura del Proyecto

```
.
├── app/
│   ├── llm/              # Cliente de Groq LLM
│   ├── rag/              # Sistema RAG (embeddings, FAISS, retriever)
│   ├── routes/           # Endpoints de la API
│   ├── main.py           # Configuración principal
│   └── schemas.py        # Modelos de datos
├── venv/                 # Entorno virtual
├── requirements.txt      # Dependencias
├── render.yaml          # Configuración de Render
└── .env.example         # Template de variables de entorno
```

## 🔒 Seguridad en Producción

- Documentación automática deshabilitada en producción
- CORS configurado con orígenes específicos
- Logging estructurado
- Manejo global de errores
- Variables de entorno para datos sensibles

## 🛠️ Desarrollo

Para ejecutar en modo desarrollo con recarga automática:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## 📝 Licencia

Ver archivo LICENSE

## 🤝 Contribuir

Las contribuciones son bienvenidas. Por favor:
1. Fork el proyecto
2. Crea tu rama de feature (`git checkout -b feature/AmazingFeature`)
3. Commit tus cambios (`git commit -m 'Add some AmazingFeature'`)
4. Push a la rama (`git push origin feature/AmazingFeature`)
5. Abre un Pull Request

## 📧 Contacto

Para preguntas o sugerencias, por favor abre un issue en el repositorio.
