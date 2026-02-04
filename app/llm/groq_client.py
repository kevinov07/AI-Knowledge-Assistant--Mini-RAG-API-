"""
Cliente Groq LLM para respuestas RAG.

generate_answer(question, context) envía al modelo la pregunta y el contexto recuperado;
el prompt indica usar SOLO ese contexto y decir claramente si no sabe, para reducir
alucinaciones.
"""
from groq import Groq
import os

DEFAULT_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
DEFAULT_TEMPERATURE = float(os.getenv("GROQ_TEMPERATURE", "0.2"))


def get_groq_client():
    return Groq(
        api_key=os.getenv("GROQ_API_KEY")
    )


def generate_answer(
    question: str,
    context: str,
    model: str = DEFAULT_MODEL,
    temperature: float = DEFAULT_TEMPERATURE
) -> str:
    client = get_groq_client()
    prompt = f"""
Responde la pregunta usando SOLO la información del contexto.
Si la respuesta no está en el contexto, di claramente que no lo sabes.

Contexto:
{context}

Pregunta:
{question}

Respuesta:
"""

    completion = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "user", "content": prompt}
        ],
        temperature=temperature
    )

    return completion.choices[0].message.content.strip()
