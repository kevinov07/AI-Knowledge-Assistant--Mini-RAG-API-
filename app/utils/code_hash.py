"""Helpers para hashear y verificar el código de acceso de colecciones privadas."""
import bcrypt


def hash_code(plain: str) -> str:
    """Hashea el código en texto plano. Devuelve el hash como string para guardar en BD."""
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(plain.encode("utf-8"), salt)
    return hashed.decode("utf-8")


def verify_code(plain: str, stored_hash: str | None) -> bool:
    """Comprueba si el código en texto plano coincide con el hash guardado."""
    print(f"[verify_code] plain: '{plain}', hash: '{stored_hash}'")
    if not stored_hash:
        print("[verify_code] No hash stored, returning False")
        return False
    try:
        result = bcrypt.checkpw(
            plain.encode("utf-8"),
            stored_hash.encode("utf-8"),
        )
        print(f"[verify_code] bcrypt.checkpw result: {result}")
        return result
    except Exception as e:
        print(f"[verify_code] Exception: {e}")
        return False
