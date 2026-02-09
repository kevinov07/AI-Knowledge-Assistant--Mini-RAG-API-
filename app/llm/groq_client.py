"""
Cliente Groq LLM para respuestas RAG.

generate_answer(question, context, history) envía al modelo la pregunta, el contexto
recuperado y opcionalmente el historial de chat para que pueda responder con contexto
de conversación (p. ej. preguntas de seguimiento).
"""
from groq import Groq
import os

DEFAULT_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
DEFAULT_TEMPERATURE = float(os.getenv("GROQ_TEMPERATURE", "0.2"))
# Máximo de mensajes de historial a enviar al LLM (por límite de contexto)
MAX_HISTORY_MESSAGES = int(os.getenv("GROQ_MAX_HISTORY_MESSAGES", "10"))


def get_groq_client():
    return Groq(
        api_key=os.getenv("GROQ_API_KEY")
    )


def generate_answer(
    question: str,
    context: str,
    history: list[dict] | None = None,
    model: str = DEFAULT_MODEL,
    temperature: float = DEFAULT_TEMPERATURE,
) -> str:
    """
    Genera la respuesta usando contexto RAG y opcionalmente historial de chat.
    history: lista de {"role": "user"|"assistant", "content": str} (orden cronológico).
    """
    client = get_groq_client()
    prompt = f"""
Responde la pregunta usando SOLO la información del contexto.
Si la respuesta no está en el contexto, di claramente que no lo sabes.

Contexto:
{context}
"""

    messages = [{"role": "system", "content": prompt}]
    if history:
        # Enviar solo los últimos N mensajes para no exceder contexto
        for msg in history[-MAX_HISTORY_MESSAGES:]:
            messages.append({"role": msg["role"], "content": msg["content"]})
    messages.append({"role": "user", "content": question})

    completion = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
    )

    return completion.choices[0].message.content.strip()
