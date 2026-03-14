from fastapi import FastAPI, Form, BackgroundTasks
from fastapi.responses import PlainTextResponse
from fastapi.staticfiles import StaticFiles
from typing import Optional
from openai import OpenAI
from twilio.rest import Client as TwilioClient
from dotenv import load_dotenv
import os
import base64
import uuid

load_dotenv()

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

openai = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
twilio = TwilioClient(os.getenv("TWILIO_ACCOUNT_SID"), os.getenv("TWILIO_AUTH_TOKEN"))
TWILIO_NUMBER = os.getenv("TWILIO_WHATSAPP_NUMBER")
BASE_URL = os.getenv("BASE_URL", "http://localhost:8001")

sessions = {}

# --- Opciones del flujo ---

CATEGORIAS = {
    "1": "comida",
    "2": "ropa",
    "3": "electronica",
    "4": "hogar",
    "5": "belleza",
    "6": "otro",
}

ESTILOS = {
    "1": "realista",
    "2": "llamativo",
    "3": "elegante",
}

PLATAFORMAS = {
    "1": ["Instagram"],
    "2": ["Mercado Libre"],
    "3": ["Facebook"],
    "4": ["WhatsApp"],
    "5": ["Instagram", "Mercado Libre", "Facebook", "WhatsApp"],
}

# --- Prompts de imagen por categoria + estilo ---

PROMPTS_IMAGEN = {
    ("comida", "realista"):  "professional food photography, natural lighting, clean plating, restaurant quality, soft shadows, no text overlays",
    ("comida", "llamativo"):  "steaming hot food, golden crust, dramatic fire background, vibrant colors, street food energy, ultra appetizing, bold text overlay with product name",
    ("comida", "elegante"):   "fine dining plating, dark marble surface, candlelight bokeh, michelin star presentation, moody editorial, no text overlays",
    ("ropa", "realista"):    "fashion product photography, neutral background, flat lay or mannequin, clean studio light, no text overlays",
    ("ropa", "llamativo"):   "vibrant outfit, urban street background, dynamic lifestyle shot, bold colors, eye-catching, bold promotional text overlay",
    ("ropa", "elegante"):    "luxury fashion editorial, minimalist background, soft studio lighting, high-end look, no text overlays",
    ("electronica", "realista"):  "product photography, white background, sharp focus, tech gadget, studio light, no text overlays",
    ("electronica", "llamativo"): "futuristic neon background, glowing product, dynamic angles, cyberpunk vibe, bold price or promo text overlay",
    ("electronica", "elegante"):  "premium tech product, dark background, dramatic spotlight, sleek and minimal, no text overlays",
    ("hogar", "realista"):   "home decor photography, natural light, cozy interior setting, lifestyle staging, no text overlays",
    ("hogar", "llamativo"):  "bright colorful room, bold decor, eye-catching composition, vibrant interior, promotional text overlay",
    ("hogar", "elegante"):   "luxury interior design, muted tones, editorial styling, sophisticated atmosphere, no text overlays",
    ("belleza", "realista"): "beauty product photography, clean white background, soft light, cosmetics styling, no text overlays",
    ("belleza", "llamativo"): "bold beauty product shot, glitter and color splashes, vibrant makeup vibes, bold promo text overlay",
    ("belleza", "elegante"): "luxury beauty editorial, marble surface, gold accents, premium cosmetics aesthetic, no text overlays",
    ("otro", "realista"):    "clean product photography, neutral background, sharp focus, natural light, no text overlays",
    ("otro", "llamativo"):   "bold product shot, vibrant colors, dynamic composition, eye-catching background, bold text overlay",
    ("otro", "elegante"):    "premium product photography, dark moody background, dramatic spotlight, no text overlays",
}

# --- Prompts de texto por plataforma + estilo ---

PROMPTS_TEXTO = {
    ("Instagram", "realista"):  "Escribi una descripcion real y apetitosa para Instagram de: {desc}. Maximo 3 lineas, 2 emojis y 5 hashtags argentinos.",
    ("Instagram", "llamativo"): "Escribi una descripcion LLAMATIVA y exagerada para Instagram de: {desc}. Usa mayusculas en palabras clave, 3 emojis impactantes y 5 hashtags virales en espanol.",
    ("Instagram", "elegante"):  "Escribi una descripcion elegante y sofisticada para Instagram de: {desc}. Tono premium, maximo 2 lineas, 1 emoji y 5 hashtags de lujo en espanol.",

    ("Mercado Libre", "realista"):  "Escribi titulo SEO (max 60 chars) y 4 bullet points tecnicos y reales de: {desc}. Formato:\nTITULO: ...\n- punto 1\n- punto 2\n- punto 3\n- punto 4",
    ("Mercado Libre", "llamativo"): "Escribi titulo SEO llamativo con MAYUSCULAS en palabras clave (max 60 chars) y 4 bullet points que destaquen beneficios de: {desc}. Formato:\nTITULO: ...\n- punto 1\n- punto 2\n- punto 3\n- punto 4",
    ("Mercado Libre", "elegante"):  "Escribi titulo SEO premium (max 60 chars) y 4 bullet points que transmitan calidad y exclusividad de: {desc}. Formato:\nTITULO: ...\n- punto 1\n- punto 2\n- punto 3\n- punto 4",

    ("Facebook", "realista"):  "Escribi una descripcion para Facebook de: {desc}. Tono familiar argentino, 3 lineas, precio si aplica, 1-2 emojis.",
    ("Facebook", "llamativo"): "Escribi una descripcion MUY LLAMATIVA para Facebook de: {desc}. Usa frases como 'NO TE LO PIERDAS', 'OFERTA IMPERDIBLE', mayusculas en lo importante, 3 emojis y precio si aplica.",
    ("Facebook", "elegante"):  "Escribi una descripcion elegante para Facebook de: {desc}. Tono sofisticado, 3 lineas, 1 emoji discreto.",

    ("WhatsApp", "realista"):  "Escribi un mensaje corto y natural para estado/grupo de WhatsApp de: {desc}. Que no parezca generado por IA. Maximo 2 lineas, precio si aplica, 1-2 emojis. Como si lo escribiera el dueno del negocio.",
    ("WhatsApp", "llamativo"): "Escribi un mensaje MUY LLAMATIVO para estado de WhatsApp de: {desc}. Primera linea en MAYUSCULAS, precio visible, 3 emojis impactantes, maximo 3 lineas.",
    ("WhatsApp", "elegante"):  "Escribi un mensaje elegante y breve para estado de WhatsApp de: {desc}. Tono premium y natural, precio si aplica, 1 emoji, maximo 2 lineas. Que no parezca IA.",
}

PROMPTS_IMAGEN_PLATAFORMA = {
    "Instagram":     "square 1:1 format optimized for Instagram feed",
    "Mercado Libre": "white background, product centered, e-commerce listing format",
    "Facebook":      "horizontal 16:9 format optimized for Facebook feed",
    "WhatsApp":      "square format, bold text overlay space, high contrast, designed for WhatsApp status",
}


def twiml(mensaje: str) -> PlainTextResponse:
    body = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Message>{mensaje}</Message>
</Response>"""
    return PlainTextResponse(content=body, media_type="text/xml")


def enviar_mensaje(to: str, texto: str, media_url: str = None):
    kwargs = {"from_": TWILIO_NUMBER, "to": to, "body": texto}
    if media_url:
        kwargs["media_url"] = [media_url]
    twilio.messages.create(**kwargs)


def generar_imagen(descripcion: str, categoria: str, estilo: str, plataforma: str) -> str:
    estilo_base = PROMPTS_IMAGEN.get((categoria, estilo), PROMPTS_IMAGEN[("otro", "realista")])
    formato = PROMPTS_IMAGEN_PLATAFORMA.get(plataforma, "")
    size = "1536x1024" if plataforma == "Facebook" else "1024x1024"
    prompt = f"{descripcion}, {estilo_base}, {formato}"

    response = openai.images.generate(
        model="gpt-image-1",
        prompt=prompt,
        size=size,
        quality="low",
    )
    img_data = base64.b64decode(response.data[0].b64_json)
    filename = f"{uuid.uuid4().hex}.png"
    with open(os.path.join("static", filename), "wb") as f:
        f.write(img_data)
    return f"{BASE_URL}/static/{filename}"


def generar_descripcion(descripcion: str, estilo: str, plataforma: str) -> str:
    key = (plataforma, estilo)
    prompt_template = PROMPTS_TEXTO.get(key, PROMPTS_TEXTO[("Instagram", "realista")])
    prompt = prompt_template.format(desc=descripcion)
    response = openai.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=300,
    )
    return response.choices[0].message.content.strip()


def procesar_en_background(to: str, descripcion: str, categoria: str, estilo: str, plataformas: list):
    try:
        primera = plataformas[0]
        imagen_url = generar_imagen(descripcion, categoria, estilo, primera)
        texto = generar_descripcion(descripcion, estilo, primera)
        respuesta = f"*{primera}*\n\n{texto}"

        for plat in plataformas[1:]:
            texto_extra = generar_descripcion(descripcion, estilo, plat)
            respuesta += f"\n\n---\n*{plat}*\n\n{texto_extra}"

        enviar_mensaje(to, respuesta, media_url=imagen_url)

    except Exception as e:
        print(f"Error: {e}")
        enviar_mensaje(to, "Ocurrio un error. Intenta de nuevo.")


@app.get("/")
def root():
    return {"status": "PostIA corriendo"}


@app.post("/webhook")
async def webhook(
    background_tasks: BackgroundTasks,
    From: str = Form(...),
    Body: Optional[str] = Form(""),
    NumMedia: Optional[int] = Form(0),
    MediaUrl0: Optional[str] = Form(None),
):
    body = Body.strip() if Body else ""
    session = sessions.get(From, {})
    state = session.get("state")

    # Paso 3: eligio plataforma
    if state == "waiting_platform" and body in PLATAFORMAS:
        plataformas = PLATAFORMAS[body]
        session["plataformas"] = plataformas
        sessions[From] = {**session, "state": "done"}
        background_tasks.add_task(
            procesar_en_background,
            From,
            session["descripcion"],
            session["categoria"],
            session["estilo"],
            plataformas,
        )
        return twiml("Generando tu contenido... En unos segundos te llega la imagen y descripcion lista.")

    # Paso 2: eligio estilo
    if state == "waiting_estilo" and body in ESTILOS:
        sessions[From] = {**session, "state": "waiting_platform", "estilo": ESTILOS[body]}
        return twiml(
            "Donde vas a publicar?\n"
            "1 - Instagram\n"
            "2 - Mercado Libre\n"
            "3 - Facebook\n"
            "4 - WhatsApp\n"
            "5 - Todos"
        )

    # Paso 1: eligio categoria
    if state == "waiting_categoria" and body in CATEGORIAS:
        sessions[From] = {**session, "state": "waiting_estilo", "categoria": CATEGORIAS[body]}
        return twiml(
            "Que estilo queres?\n"
            "1 - Realista y profesional\n"
            "2 - Llamativo y exagerado\n"
            "3 - Elegante y premium"
        )

    # Primer contacto: cualquier mensaje de un usuario nuevo sin sesion
    if not session and int(NumMedia or 0) == 0:
        sessions[From] = {"state": "welcomed"}
        return twiml(
            "Hola! Soy *PostIA*.\n\n"
            "Transformo fotos de tus productos en imagenes profesionales y descripciones listas para publicar, en segundos.\n\n"
            "Funciona asi:\n"
            "1. Manda una foto de tu producto con el nombre\n"
            "2. Elegi categoria, estilo y plataforma\n"
            "3. En segundos recibi imagen mejorada + descripcion lista\n\n"
            "Funciona para Instagram, Mercado Libre, Facebook y WhatsApp.\n\n"
            "Cuando quieras arrancar, manda una foto de tu producto con el nombre como texto. "
            "Ejemplo: *asado de tira con chimichurri*"
        )

    # Inicio: foto + descripcion
    if int(NumMedia or 0) > 0 and MediaUrl0 and body:
        sessions[From] = {
            "state": "waiting_categoria",
            "descripcion": body,
            "foto_url": MediaUrl0,
        }
        return twiml(
            f"Perfecto! Recibi tu foto de *{body}*.\n\n"
            "Que tipo de producto es?\n"
            "1 - Comida / Restaurante\n"
            "2 - Ropa / Indumentaria\n"
            "3 - Electronica\n"
            "4 - Hogar / Deco\n"
            "5 - Belleza / Cuidado\n"
            "6 - Otro"
        )

    # Foto sin texto
    if int(NumMedia or 0) > 0 and not body:
        return twiml("Manda la foto con el nombre del producto como texto. Ejemplo: *asado de tira con chimichurri*")

    # Mensaje sin foto
    return twiml(
        "Manda una foto de tu plato o producto con el nombre como texto.\n"
        "Ejemplo: *asado de tira con chimichurri*"
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=False)
