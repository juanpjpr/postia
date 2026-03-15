import os
import sqlite3
from datetime import datetime, timedelta

# En Railway DATABASE_URL viene automático al agregar el plugin Postgres
DATABASE_URL = os.getenv("DATABASE_URL")

USOS_GRATIS = 3
DIAS_SUSCRIPCION = 30


# ── conexión ──────────────────────────────────────────────────────────────────

def _get_conn():
    if DATABASE_URL:
        import psycopg2
        return psycopg2.connect(DATABASE_URL)
    return sqlite3.connect(os.path.join(os.path.dirname(__file__), "postia.db"))


def _placeholder():
    """Postgres usa %s, SQLite usa ?"""
    return "%s" if DATABASE_URL else "?"


def _row_to_dict(cursor, row):
    cols = [d[0] for d in cursor.description]
    return dict(zip(cols, row))


# ── init ──────────────────────────────────────────────────────────────────────

def init_db():
    ph = _placeholder()
    with _get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
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
        # Migracion suave: agregar columna si no existe
        try:
            cur.execute("ALTER TABLE suscripciones ADD COLUMN fotos_restantes INTEGER DEFAULT -1")
        except Exception:
            pass
        conn.commit()


# ── queries ───────────────────────────────────────────────────────────────────

def _get(phone: str) -> dict | None:
    ph = _placeholder()
    with _get_conn() as conn:
        cur = conn.cursor()
        cur.execute(f"SELECT * FROM suscripciones WHERE phone = {ph}", (phone,))
        row = cur.fetchone()
        return _row_to_dict(cur, row) if row else None


def verificar_acceso(phone: str) -> dict:
    ph = _placeholder()
    row = _get(phone)

    # Usuario nuevo → trial
    if row is None:
        with _get_conn() as conn:
            cur = conn.cursor()
            cur.execute(f"INSERT INTO suscripciones (phone) VALUES ({ph})", (phone,))
            conn.commit()
        return {"permitido": True, "estado": "trial", "usos_restantes": USOS_GRATIS - 1}

    # Suscripcion activa
    if row["estado"] == "activo":
        if row["fecha_expiracion"] and datetime.now().isoformat() > row["fecha_expiracion"]:
            with _get_conn() as conn:
                cur = conn.cursor()
                cur.execute(f"UPDATE suscripciones SET estado='vencido' WHERE phone={ph}", (phone,))
                conn.commit()
            return {"permitido": False, "estado": "vencido",
                    "mensaje": "Tu suscripcion vencio. Renova para seguir generando contenido."}

        fotos = row["fotos_restantes"]
        if fotos == 0:
            return {"permitido": False, "estado": "sin_fotos",
                    "mensaje": f"Agotaste las fotos de tu plan *{row['plan']}*. Upgrade para seguir publicando."}
        if fotos > 0:
            with _get_conn() as conn:
                cur = conn.cursor()
                cur.execute(f"UPDATE suscripciones SET fotos_restantes=fotos_restantes-1 WHERE phone={ph}", (phone,))
                conn.commit()
            return {"permitido": True, "estado": "activo", "fotos_restantes": fotos - 1}
        return {"permitido": True, "estado": "activo", "fotos_restantes": -1}

    # Trial con usos disponibles
    if row["estado"] == "trial" and row["usos_gratis"] > 0:
        with _get_conn() as conn:
            cur = conn.cursor()
            cur.execute(f"UPDATE suscripciones SET usos_gratis=usos_gratis-1 WHERE phone={ph}", (phone,))
            conn.commit()
        return {"permitido": True, "estado": "trial", "usos_restantes": row["usos_gratis"] - 1}

    return {"permitido": False, "estado": "sin_usos",
            "mensaje": f"Usaste tus {USOS_GRATIS} publicaciones gratis.\n\nSuscribite para publicaciones ilimitadas."}


def reembolsar_uso(phone: str):
    """Devuelve el uso descontado si la generacion fallo o tardo demasiado."""
    row = _get(phone)
    if not row:
        return
    ph = _placeholder()
    with _get_conn() as conn:
        cur = conn.cursor()
        if row["estado"] == "trial":
            cur.execute(f"UPDATE suscripciones SET usos_gratis=usos_gratis+1 WHERE phone={ph}", (phone,))
        elif row["estado"] == "activo" and (row["fotos_restantes"] or 0) >= 0:
            cur.execute(f"UPDATE suscripciones SET fotos_restantes=fotos_restantes+1 WHERE phone={ph}", (phone,))
        conn.commit()


def activar_suscripcion(phone: str, payment_id: str, plan: str = "basico"):
    from pagos import PLANES
    fotos = PLANES.get(plan, {}).get("fotos", 30)
    expiracion = (datetime.now() + timedelta(days=DIAS_SUSCRIPCION)).isoformat()
    ph = _placeholder()

    if DATABASE_URL:
        sql = f"""
            INSERT INTO suscripciones (phone, estado, usos_gratis, fotos_restantes, fecha_inicio, fecha_expiracion, mp_payment_id, plan)
            VALUES ({ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph})
            ON CONFLICT(phone) DO UPDATE SET
                estado=EXCLUDED.estado,
                fotos_restantes=EXCLUDED.fotos_restantes,
                fecha_inicio=EXCLUDED.fecha_inicio,
                fecha_expiracion=EXCLUDED.fecha_expiracion,
                mp_payment_id=EXCLUDED.mp_payment_id,
                plan=EXCLUDED.plan
        """
    else:
        sql = f"""
            INSERT INTO suscripciones (phone, estado, usos_gratis, fotos_restantes, fecha_inicio, fecha_expiracion, mp_payment_id, plan)
            VALUES ({ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph})
            ON CONFLICT(phone) DO UPDATE SET
                estado=excluded.estado,
                fotos_restantes=excluded.fotos_restantes,
                fecha_inicio=excluded.fecha_inicio,
                fecha_expiracion=excluded.fecha_expiracion,
                mp_payment_id=excluded.mp_payment_id,
                plan=excluded.plan
        """
    with _get_conn() as conn:
        cur = conn.cursor()
        cur.execute(sql, (phone, "activo", 0, fotos, datetime.now().isoformat(), expiracion, payment_id, plan))
        conn.commit()
