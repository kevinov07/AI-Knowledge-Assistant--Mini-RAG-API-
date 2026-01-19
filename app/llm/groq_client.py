from groq import Groq
import os

DEFAULT_MODEL = "llama-3.3-70b-versatile"

def get_groq_client():
    return Groq(
        api_key=os.getenv("GROQ_API_KEY")
    )

def generate_answer(
    question: str,
    context: str,
    model: str = DEFAULT_MODEL
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
        temperature=0.2
    )

    return completion.choices[0].message.content.strip()
