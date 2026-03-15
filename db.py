import sqlite3
import os
from datetime import datetime, timedelta

DB_PATH = os.path.join(os.path.dirname(__file__), "postia.db")

USOS_GRATIS = 3  # publicaciones gratis antes de pedir suscripción
DIAS_SUSCRIPCION = 30


def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS suscripciones (
                phone            TEXT PRIMARY KEY,
                estado           TEXT DEFAULT 'trial',
                usos_gratis      INTEGER DEFAULT 3,
                fotos_restantes  INTEGER DEFAULT -1,
                fecha_inicio     TEXT,
                fecha_expiracion TEXT,
                mp_payment_id    TEXT,
                plan             TEXT DEFAULT 'trial'
            )
        """)
        # Migracion: agregar columna si no existe (por si la DB ya existia)
        try:
            conn.execute("ALTER TABLE suscripciones ADD COLUMN fotos_restantes INTEGER DEFAULT -1")
        except Exception:
            pass
        conn.commit()


def _get(phone: str) -> dict | None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM suscripciones WHERE phone = ?", (phone,)).fetchone()
        return dict(row) if row else None


def verificar_acceso(phone: str) -> dict:
    """
    Retorna dict con:
      - permitido: bool
      - estado: 'trial' | 'activo' | 'vencido' | 'sin_usos'
      - usos_restantes: int (solo en trial)
      - mensaje: str para enviar al usuario si no tiene acceso
    """
    row = _get(phone)

    # Usuario nuevo → crear trial
    if row is None:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                "INSERT INTO suscripciones (phone) VALUES (?)", (phone,)
            )
            conn.commit()
        return {"permitido": True, "estado": "trial", "usos_restantes": USOS_GRATIS - 1}

    # Suscripción activa — verificar que no venció ni agotó fotos
    if row["estado"] == "activo":
        if row["fecha_expiracion"] and datetime.now().isoformat() > row["fecha_expiracion"]:
            with sqlite3.connect(DB_PATH) as conn:
                conn.execute("UPDATE suscripciones SET estado='vencido' WHERE phone=?", (phone,))
                conn.commit()
            return {
                "permitido": False,
                "estado": "vencido",
                "mensaje": "Tu suscripcion vencio. Renova para seguir generando contenido.",
            }
        # Plan con limite de fotos
        fotos = row["fotos_restantes"]
        if fotos == 0:
            return {
                "permitido": False,
                "estado": "sin_fotos",
                "mensaje": f"Agotaste las fotos de tu plan *{row['plan']}*. Upgrade para seguir publicando.",
            }
        if fotos > 0:
            nuevas = fotos - 1
            with sqlite3.connect(DB_PATH) as conn:
                conn.execute("UPDATE suscripciones SET fotos_restantes=? WHERE phone=?", (nuevas, phone))
                conn.commit()
            return {"permitido": True, "estado": "activo", "fotos_restantes": nuevas}
        # fotos == -1 → ilimitado
        return {"permitido": True, "estado": "activo", "fotos_restantes": -1}

    # Trial con usos disponibles
    if row["estado"] == "trial" and row["usos_gratis"] > 0:
        nuevos = row["usos_gratis"] - 1
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                "UPDATE suscripciones SET usos_gratis=? WHERE phone=?", (nuevos, phone)
            )
            conn.commit()
        return {"permitido": True, "estado": "trial", "usos_restantes": nuevos}

    # Sin usos ni suscripcion
    return {
        "permitido": False,
        "estado": "sin_usos",
        "mensaje": (
            "Usaste tus {} publicaciones gratis.\n\n"
            "Suscribite para publicaciones ilimitadas."
        ).format(USOS_GRATIS),
    }


def activar_suscripcion(phone: str, payment_id: str, plan: str = "basico"):
    from pagos import PLANES
    fotos = PLANES.get(plan, {}).get("fotos", 30)
    expiracion = (datetime.now() + timedelta(days=DIAS_SUSCRIPCION)).isoformat()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            INSERT INTO suscripciones (phone, estado, usos_gratis, fotos_restantes, fecha_inicio, fecha_expiracion, mp_payment_id, plan)
            VALUES (?, 'activo', 0, ?, ?, ?, ?, ?)
            ON CONFLICT(phone) DO UPDATE SET
                estado='activo',
                fotos_restantes=excluded.fotos_restantes,
                fecha_inicio=excluded.fecha_inicio,
                fecha_expiracion=excluded.fecha_expiracion,
                mp_payment_id=excluded.mp_payment_id,
                plan=excluded.plan
            """,
            (phone, fotos, datetime.now().isoformat(), expiracion, payment_id, plan),
        )
        conn.commit()


def get_phone_by_payment(payment_id: str) -> str | None:
    """Busca el phone asociado a un pago (para webhook de MP)."""
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT phone FROM suscripciones WHERE mp_payment_id=?", (payment_id,)
        ).fetchone()
        return row[0] if row else None
