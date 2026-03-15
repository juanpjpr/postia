import mercadopago
import os

# fotos=-1 significa ilimitadas
PLANES = {
    "basico":    {"titulo": "PostIA - Plan Basico",    "precio": 15000, "fotos": 30},
    "pro":       {"titulo": "PostIA - Plan Pro",       "precio": 30000, "fotos": 100},
    "ilimitado": {"titulo": "PostIA - Plan Ilimitado", "precio": 50000, "fotos": -1},
}


def crear_link_pago(phone: str, plan: str) -> str:
    """Crea una preferencia de pago en MercadoPago y retorna el link."""
    sdk = mercadopago.SDK(os.getenv("MP_ACCESS_TOKEN"))
    item = PLANES[plan]
    base_url = os.getenv("BASE_URL", "http://localhost:8001")

    preference_data = {
        "items": [
            {
                "title": item["titulo"],
                "quantity": 1,
                "unit_price": float(item["precio"]),
                "currency_id": "ARS",
            }
        ],
        "external_reference": f"{phone}|{plan}",   # phone + plan separados por |
        "notification_url": f"{base_url}/pagos/mp",
        "back_urls": {
            "success": f"{base_url}/pago-exitoso",
            "failure": f"{base_url}/pago-fallido",
            "pending": f"{base_url}/pago-pendiente",
        },
        "auto_return": "approved",
        "statement_descriptor": "PostIA",
    }

    response = sdk.preference().create(preference_data)
    if response["status"] != 201:
        raise RuntimeError(f"MercadoPago error: {response}")

    if os.getenv("MP_SANDBOX", "true").lower() == "true":
        return response["response"]["sandbox_init_point"]
    return response["response"]["init_point"]


def crear_links_todos_los_planes(phone: str) -> dict:
    """Retorna {plan: link} para los 3 planes. Si falla alguno, lo omite."""
    links = {}
    for plan in PLANES:
        try:
            links[plan] = crear_link_pago(phone, plan)
        except Exception as e:
            print(f"[pagos] error creando link {plan}: {e}")
    return links


def verificar_pago(payment_id: str) -> dict | None:
    """Verifica el estado de un pago en MercadoPago."""
    sdk = mercadopago.SDK(os.getenv("MP_ACCESS_TOKEN"))
    response = sdk.payment().get(payment_id)
    if response["status"] != 200:
        return None
    return response["response"]
