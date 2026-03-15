from fastapi import FastAPI, Form, BackgroundTasks, Request
from fastapi.responses import PlainTextResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from typing import Optional
from openai import OpenAI
from twilio.rest import Client as TwilioClient
from dotenv import load_dotenv
import os
import base64
import uuid
import io
import httpx
import fal_client
import db
import pagos

load_dotenv()

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
db.init_db()

openai = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
twilio = TwilioClient(os.getenv("TWILIO_ACCOUNT_SID"), os.getenv("TWILIO_AUTH_TOKEN"))
os.environ["FAL_KEY"] = os.getenv("FAL_KEY", "")
TWILIO_NUMBER = os.getenv("TWILIO_WHATSAPP_NUMBER")
_railway_domain = os.getenv("RAILWAY_PUBLIC_DOMAIN")
BASE_URL = os.getenv("BASE_URL") or (f"https://{_railway_domain}" if _railway_domain else "http://localhost:8001")

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


# Pregunta especifica por categoria en modo detallado
# El detalle enriquece tanto el prompt de imagen como el de descripcion
PREGUNTAS_DETALLE = {
    "comida":      "Algun ingrediente o detalle especial del plato?\nEj: *con chimichurri casero, coccion a las brasas, sin TACC*\n(o escribi *0* para omitir)",
    "ropa":        "Talle disponible y colores? Ej: *S/M/L, negro y blanco*\n(o escribi *0* para omitir)",
    "electronica": "Marca y modelo exacto?\nEj: *Samsung Galaxy A54 128GB negro*\n(Mejora el SEO en ML y la precision de la imagen)\n(o escribi *0* para omitir)",
    "hogar":       "Medidas y materiales? Ej: *Mesa 1.20x0.80m madera maciza*\n(o escribi *0* para omitir)",
    "belleza":     "Ingrediente principal o beneficio clave?\nEj: *con vitamina C, apto piel sensible, sin parabenos*\n(o escribi *0* para omitir)",
    "otro":        "De que rubro es tu producto?\nEj: *juguetes, herramientas, mascotas, deportes, libreria...*",
}

PLATAFORMAS = {
    "1": ["Instagram"],
    "2": ["Mercado Libre"],
    "3": ["Facebook"],
    "4": ["WhatsApp"],
    "5": ["Instagram", "Mercado Libre", "Facebook", "WhatsApp"],
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

    ("Instagram", "fondo_limpio"):  "Escribi una descripcion limpia y profesional para Instagram de: {desc}. Resalta el producto sobre fondo blanco. Maximo 3 lineas, 2 emojis y 5 hashtags argentinos.",
    ("Mercado Libre", "fondo_limpio"): "Escribi titulo SEO (max 60 chars) y 4 bullet points destacando caracteristicas del producto de: {desc}. Menciona que es foto con fondo blanco profesional. Formato:\nTITULO: ...\n- punto 1\n- punto 2\n- punto 3\n- punto 4",
    ("Facebook", "fondo_limpio"):  "Escribi una descripcion para Facebook de: {desc}. Tono claro y directo, 3 lineas, precio si aplica, 1-2 emojis.",
    ("WhatsApp", "fondo_limpio"):  "Escribi un mensaje corto para estado de WhatsApp de: {desc}. Menciona que es foto profesional. Maximo 2 lineas, precio si aplica, 1-2 emojis.",
}


def twiml(mensaje: str) -> PlainTextResponse:
    body = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Message>{mensaje}</Message>
</Response>"""
    return PlainTextResponse(content=body, media_type="text/xml")


def enviar_mensaje(to: str, texto: str, media_url: str = None):
    if media_url:
        msg1 = twilio.messages.create(from_=TWILIO_NUMBER, to=to, body=" ", media_url=[media_url])
        print(f"[twilio send] imagen sid={msg1.sid} status={msg1.status}")
        msg2 = twilio.messages.create(from_=TWILIO_NUMBER, to=to, body=texto)
        print(f"[twilio send] texto sid={msg2.sid} status={msg2.status}")
    else:
        msg = twilio.messages.create(from_=TWILIO_NUMBER, to=to, body=texto)
        print(f"[twilio send] sid={msg.sid} status={msg.status}")


def generar_prompt_imagen(descripcion: str, categoria: str, estilo: str, plataforma: str, negocio_desc: str = None) -> str:
    estilos_desc = {
        "realista": "fotografía realista y profesional, sin textos ni overlays",
        "llamativo": "imagen llamativa, colores vibrantes, energía y dinamismo, puede incluir texto con el nombre del producto",
        "elegante": "fotografía premium y elegante, minimalista, sin textos",
    }
    formato_desc = {
        "Instagram": "formato cuadrado 1:1, optimizado para feed de Instagram",
        "Mercado Libre": "fondo blanco, producto centrado, formato e-commerce",
        "Facebook": "formato horizontal 16:9 para Facebook",
        "WhatsApp": "formato cuadrado, alto contraste, para estado de WhatsApp",
    }
    contexto = f" El negocio es: {negocio_desc}." if negocio_desc else ""
    extra_ropa = (
        " The garment must be displayed on a ghost mannequin (invisible body effect) or worn by a model. "
        "If the original is flat on the floor, generate it with natural 3D shape and volume. "
        "Remove all wrinkles. Professional fashion photography."
    ) if categoria == "ropa" else ""
    meta_prompt = (
        f"Eres un experto en fotografía de productos y marketing visual para redes sociales.{contexto} "
        f"Dame SOLO el prompt en inglés para generar con IA la mejor imagen posible para vender '{descripcion}' "
        f"(categoria: {categoria}) en {plataforma}. "
        f"Estilo deseado: {estilos_desc.get(estilo, estilo)}. "
        f"Formato: {formato_desc.get(plataforma, '')}. "
        f"{extra_ropa}"
        f"El prompt debe especificar iluminación, fondo, composición, ángulo, ambiente y detalles visuales del producto. "
        f"Maximo 120 palabras. Responde SOLO con el prompt, sin explicaciones ni comillas."
    )
    print(f"[prompt:meta_imagen] {meta_prompt}")
    response = openai.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": meta_prompt}],
        max_tokens=200,
    )
    resultado = response.choices[0].message.content.strip()
    print(f"[prompt:imagen_generado] {resultado}")
    return resultado


def _descargar_media_twilio(foto_url: str) -> bytes | None:
    """Descarga imagen de Twilio. Intenta 3 metodos. Retorna bytes o None si falla."""
    account_sid = os.getenv("TWILIO_ACCOUNT_SID")
    auth_token = os.getenv("TWILIO_AUTH_TOKEN")

    # Intento 1: auth sin seguir redirect — captura la Location del CDN
    try:
        r = httpx.get(foto_url, auth=(account_sid, auth_token), follow_redirects=False, timeout=15)
        print(f"[twilio] intento 1: status={r.status_code} ct={r.headers.get('content-type','')}")
        if r.status_code in (301, 302, 303, 307, 308):
            cdn_url = r.headers.get("location", "")
            print(f"[twilio] CDN redirect: {cdn_url}")
            if cdn_url:
                r2 = httpx.get(cdn_url, follow_redirects=True, timeout=30)
                ct = r2.headers.get("content-type", "").split(";")[0].strip()
                if ct.startswith("image/"):
                    print(f"[twilio] OK {len(r2.content)} bytes")
                    return r2.content
        if r.status_code == 200:
            ct = r.headers.get("content-type", "").split(";")[0].strip()
            if ct.startswith("image/"):
                return r.content
    except Exception as e:
        print(f"[twilio] intento 1 error: {e}")

    # Intento 2: auth + follow_redirects (httpx sigue el redirect completo)
    try:
        r = httpx.get(foto_url, auth=(account_sid, auth_token), follow_redirects=True, timeout=30)
        ct = r.headers.get("content-type", "").split(";")[0].strip()
        print(f"[twilio] intento 2: status={r.status_code} ct={ct} size={len(r.content)}")
        if ct.startswith("image/"):
            return r.content
    except Exception as e:
        print(f"[twilio] intento 2 error: {e}")

    # Intento 3: usar requests (ya instalado como dep de twilio, manejo distinto de redirects)
    try:
        import requests as _req
        r = _req.get(foto_url, auth=(account_sid, auth_token), allow_redirects=True, timeout=30)
        ct = r.headers.get("content-type", "").split(";")[0].strip()
        print(f"[twilio] intento 3 (requests): status={r.status_code} ct={ct} size={len(r.content)}")
        if ct.startswith("image/"):
            return r.content
    except Exception as e:
        print(f"[twilio] intento 3 error: {e}")

    print("[twilio] todos los intentos fallaron — sandbox limitation, usando generacion GPT")
    return None


def generar_imagen(descripcion: str, categoria: str, fondo_desc: str, plataforma: str, foto_url: str = None, negocio_desc: str = None) -> str:
    size = "1536x1024" if plataforma == "Facebook" else "1024x1024"

    if foto_url:
        img_bytes = _descargar_media_twilio(foto_url)
        if img_bytes:
            fal_image_url = fal_client.upload(img_bytes, "image/jpeg")
            print(f"[fal] imagen subida: {fal_image_url}")
            extra_ropa = "Remove wrinkles and creases from the fabric, restore natural smooth texture. The garment must remain 100% identical. " if categoria == "ropa" else ""
            flux_prompt = (
                f"Professional product photo. {extra_ropa}"
                f"Remove the current background and replace it with: {fondo_desc}. "
                f"The product must remain 100% identical: same color, material, texture, shape and all details. "
                f"Do not add, replace or remove any part of the product itself. "
                f"Optimized for {plataforma}. Photorealistic. "
                f"No text, no watermarks, no overlays, no logos, no writing of any kind."
            )
            print(f"[prompt:flux] {flux_prompt}")
            try:
                result = fal_client.run(
                    "fal-ai/flux-pro/kontext",
                    arguments={
                        "prompt": flux_prompt,
                        "image_url": fal_image_url,
                        "guidance_scale": 2.5,
                        "num_inference_steps": 28,
                    },
                )
                print(f"[fal] resultado keys: {list(result.keys()) if result else 'None'}")
            except Exception as fal_err:
                print(f"[fal] ERROR en run: {fal_err}")
                raise
            fal_img_url = result["images"][0]["url"]
            img_data = httpx.get(fal_img_url, timeout=60).content
            ext = fal_img_url.split(".")[-1].split("?")[0].lower()
            if ext not in ("jpg", "jpeg", "png", "webp"):
                ext = "jpg"
            print(f"[fal] imagen descargada: {fal_img_url} ext={ext}")
            filename = f"{uuid.uuid4().hex}.{ext}"
            with open(os.path.join("static", filename), "wb") as f:
                f.write(img_data)
            return f"{BASE_URL}/static/{filename}"
        # Si no se pudo descargar, cae al modo generativo

    prompt = generar_prompt_imagen(descripcion, categoria, fondo_desc, plataforma, negocio_desc=negocio_desc)
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


def investigar_producto_ml(descripcion: str) -> str:
    """Usa GPT para buscar especificaciones tecnicas reales del producto."""
    prompt = (
        f"Sos un experto en e-commerce de Mercado Libre Argentina. "
        f"Te describen un producto: '{descripcion}'.\n\n"
        f"Tu tarea: investigar y listar las especificaciones tecnicas mas relevantes de este producto "
        f"para una publicacion en Mercado Libre. Incluí:\n"
        f"- Marca y modelo exacto (si se puede inferir o es conocido)\n"
        f"- Especificaciones tecnicas clave (materiales, medidas, capacidad, potencia, etc.)\n"
        f"- Caracteristicas diferenciales que busca un comprador en ML\n"
        f"- Palabras clave SEO que usa la gente para buscar este producto\n\n"
        f"Si el vendedor no dio modelo exacto, aclaralo y sugerí que conviene especificarlo.\n"
        f"Formato: bullet points cortos, sin introduccion. Maximo 120 palabras."
    )
    print(f"[prompt:ml_investigar] {prompt}")
    response = openai.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=250,
    )
    return response.choices[0].message.content.strip()


def generar_descripcion(descripcion: str, estilo: str, plataforma: str, negocio_desc: str = None) -> str:
    # Para Mercado Libre: primero investigamos el producto, luego generamos el copy
    if plataforma == "Mercado Libre":
        specs = investigar_producto_ml(descripcion)
        prompt = (
            f"Sos un vendedor experto en Mercado Libre Argentina. "
            f"Producto: '{descripcion}'.\n\n"
            f"Especificaciones investigadas:\n{specs}\n\n"
            f"Crea una publicacion profesional de ML con estilo '{estilo}':\n"
            f"1. TITULO: maximo 60 caracteres, con las palabras clave mas buscadas, "
            f"incluí marca y modelo si estan disponibles\n"
            f"2. Cuatro bullet points que destaquen especificaciones tecnicas reales y beneficios concretos\n"
            f"3. NOTA_MODELO: una linea corta que le avise al vendedor si conviene aclarar "
            f"el modelo exacto o no (por ejemplo: 'Aclarar el modelo exacto mejora el SEO y genera mas confianza')\n\n"
            f"Formato exacto:\n"
            f"TITULO: ...\n"
            f"- punto 1\n"
            f"- punto 2\n"
            f"- punto 3\n"
            f"- punto 4\n"
            f"NOTA_MODELO: ..."
        )
        print(f"[prompt:ml_descripcion] {prompt}")
        response = openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=400,
        )
        return response.choices[0].message.content.strip()

    key = (plataforma, estilo)
    prompt_template = PROMPTS_TEXTO.get(key, PROMPTS_TEXTO[("Instagram", "realista")])
    prompt = prompt_template.format(desc=descripcion)
    if negocio_desc:
        prompt += f" Contexto del negocio: {negocio_desc}."
    print(f"[prompt:descripcion:{plataforma}:{estilo}] {prompt}")
    response = openai.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=300,
    )
    return response.choices[0].message.content.strip()


def procesar_en_background(to: str, descripcion: str, categoria: str, fondo_desc: str, plataformas: list, foto_url: str = None):
    import traceback
    try:
        negocio_desc = db.get_negocio_desc(to)
        print(f"[proceso] iniciando para {to} | fondo={fondo_desc} | plataformas={plataformas}")
        primera = plataformas[0]
        imagen_url = generar_imagen(descripcion, categoria, fondo_desc, primera, foto_url, negocio_desc=negocio_desc)
        print(f"[proceso] imagen generada: {imagen_url}")
        texto = generar_descripcion(descripcion, fondo_desc, primera, negocio_desc=negocio_desc)
        respuesta = f"*{primera}*\n\n{texto}"
        for plat in plataformas[1:]:
            texto_extra = generar_descripcion(descripcion, fondo_desc, plat, negocio_desc=negocio_desc)
            respuesta += f"\n\n---\n*{plat}*\n\n{texto_extra}"
        enviar_mensaje(to, respuesta, media_url=imagen_url)
        print(f"[proceso] mensaje enviado a {to}")

        # Feedback cada 5 usos
        total = db.incrementar_total_usos(to)
        if total > 0 and total % 5 == 0:
            enviar_mensaje(to,
                "Una pregunta rapida sobre tu experiencia con PostIA:\n\n"
                "1 - Mala\n"
                "2 - Buena\n"
                "3 - Muy buena\n\n"
                "_(Podes ignorar este mensaje si no queres responder)_"
            )
            sessions[to] = {**sessions.get(to, {}), "state": "waiting_feedback"}
    except Exception as e:
        tb = traceback.format_exc()
        print(f"[error] {e}\n{tb}")
        db.reembolsar_uso(to)
        enviar_mensaje(to, "Algo fallo al generar el contenido. No te descontamos el uso, podes intentar de nuevo.")


@app.get("/")
def root():
    return FileResponse("static/index.html")


@app.get("/terminos")
def terminos():
    return FileResponse("static/terminos.html")


@app.get("/admin")
def admin_panel():
    return FileResponse("static/admin.html")


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

    # Paso 3: eligio plataforma → genera
    if state == "waiting_platform" and body in PLATAFORMAS:
        plataformas = PLATAFORMAS[body]
        sessions[From] = {**session, "state": "done"}
        background_tasks.add_task(
            procesar_en_background,
            From,
            session["descripcion"],
            session["categoria"],
            session["fondo_desc"],
            plataformas,
            session.get("foto_url"),
        )
        return twiml("Generando tu contenido... En unos segundos te llega la imagen y descripcion lista.")

    # Paso 2: eligio fondo (blanco, negro, o descripcion libre para pro)
    if state == "waiting_fondo_basico":
        plan = session.get("plan", "trial")
        if body == "1":
            fondo = "pure white background, professional studio"
        elif body == "2":
            fondo = "pure black background, dramatic studio lighting"
        elif plan in ("pro", "ilimitado") and body:
            fondo = body
        else:
            return twiml("Respondé 1 para fondo blanco o 2 para fondo negro.")
        sessions[From] = {**session, "state": "waiting_platform", "fondo_desc": fondo}
        return twiml(
            "Donde vas a publicar?\n"
            "1 - Instagram\n"
            "2 - Mercado Libre\n"
            "3 - Facebook\n"
            "4 - WhatsApp\n"
            "5 - Todos"
        )

    # Paso 1: eligio categoria → pregunta fondo segun plan
    if state == "waiting_categoria" and body in CATEGORIAS:
        row = db._get(From)
        plan = row.get("plan", "trial") if row else "trial"
        sessions[From] = {**session, "categoria": CATEGORIAS[body], "plan": plan, "state": "waiting_fondo_basico"}
        if plan in ("pro", "ilimitado"):
            return twiml(
                "Que fondo queres?\n"
                "1 - Fondo blanco (ideal para Mercado Libre)\n"
                "2 - Fondo negro (premium)\n\n"
                "O escribi el fondo que quieras. Ej:\n"
                "• _horno de barro_\n"
                "• _noche de verano_\n"
                "• _cocina moderna_"
            )
        else:
            return twiml(
                "Que fondo queres?\n"
                "1 - Fondo blanco (ideal para Mercado Libre)\n"
                "2 - Fondo negro (premium)"
            )

    # Feedback - eligio calificacion
    if state == "waiting_feedback" and body in ("1", "2", "3"):
        calificaciones = {"1": "mala", "2": "buena", "3": "muy buena"}
        cal = calificaciones[body]
        if body in ("1", "2"):
            sessions[From] = {**session, "state": "waiting_feedback_detalle", "feedback_cal": cal}
            return twiml("Gracias por responder. Que mejorarias?")
        else:
            db.guardar_consulta(From, "feedback", f"Calificacion: {cal}")
            sessions[From] = {**session, "state": None}
            return twiml("Gracias! Nos alegra que te este yendo bien. Cuando quieras, manda una foto.")

    # Feedback - escribio que mejoraria
    if state == "waiting_feedback_detalle" and body:
        cal = session.get("feedback_cal", "")
        db.guardar_consulta(From, "feedback", f"Calificacion: {cal} | Mejora: {body}")
        sessions[From] = {**session, "state": None}
        return twiml("Gracias por tu opinion, lo tomamos en cuenta. Cuando quieras, manda una foto.")

    # Comando: ayuda / consulta
    if body.lower() in ("ayuda", "consulta", "contacto", "soporte"):
        sessions[From] = {**session, "state": "waiting_consulta"}
        return twiml(
            "Claro, con gusto te ayudo.\n\n"
            "Contame tu consulta, reclamo o sugerencia y te respondo a la brevedad."
        )

    if state == "waiting_consulta" and body:
        db.guardar_consulta(From, "consulta", body)
        sessions[From] = {**session, "state": None}
        return twiml(
            "Gracias, recibimos tu mensaje. Te respondemos pronto por aca.\n\n"
            "Cuando quieras, manda una foto para generar una publicacion."
        )

    # Comando: guardar descripcion del negocio
    if body.lower().startswith("mi negocio:"):
        desc = body[len("mi negocio:"):].strip()
        if desc:
            db.set_negocio_desc(From, desc)
            return twiml(f"Perfil guardado! Voy a usar esta info cuando elijas modo Personalizado:\n\n_{desc}_\n\nPodes actualizarlo cuando quieras mandando *mi negocio: [descripcion]*")
        return twiml("Manda la descripcion despues de 'mi negocio:'. Ej: *mi negocio: soy una parrilla en Palermo, vendo asados y empanadas*")

    # Primer contacto: cualquier mensaje de un usuario nuevo sin sesion
    if not session and int(NumMedia or 0) == 0:
        sessions[From] = {"state": "welcomed"}
        return twiml(
            "Hola! Soy *PostIA*.\n\n"
            "Transformo fotos de tus productos en publicaciones profesionales listas para Instagram, Mercado Libre, Facebook y WhatsApp.\n\n"
            "Para arrancar, manda una foto de tu producto con el nombre como texto.\n"
            "Ejemplo: *zapatillas Nike negras*\n\n"
            "Si tenes alguna consulta, escribi *ayuda*."
        )

    # Inicio: foto + descripcion
    if int(NumMedia or 0) > 0 and MediaUrl0 and body:
        acceso = db.verificar_acceso(From)
        if not acceso["permitido"]:
            links = pagos.crear_links_todos_los_planes(From)
            msg = acceso["mensaje"] + "\n\nEleги tu plan:"
            if "basico" in links:
                msg += f"\n\n🔹 *Plan Basico* — 30 fotos/mes — $2.999\n{links['basico']}"
            if "pro" in links:
                msg += f"\n\n🔸 *Plan Pro* — 100 fotos/mes — $5.999\n{links['pro']}"
            if "ilimitado" in links:
                msg += f"\n\n⭐ *Plan Ilimitado* — sin limite — $9.999\n{links['ilimitado']}"
            return twiml(msg)

        sessions[From] = {
            "state": "waiting_categoria",
            "descripcion": body,
            "foto_url": MediaUrl0,
        }
        aviso = ""
        if acceso["estado"] == "trial":
            restantes = acceso["usos_restantes"]
            if restantes == 0:
                aviso = "\n\n_(Es tu ultima publicacion gratis. Despues necesitas suscripcion.)_"
            else:
                aviso = f"\n\n_(Te quedan {restantes} publicaciones gratis)_"

        return twiml(
            f"Perfecto! Recibi tu foto de *{body}*.{aviso}\n\n"
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


@app.post("/pagos/mp")
async def webhook_mp(request: Request):
    """Webhook que llama MercadoPago cuando se confirma un pago."""
    try:
        data = await request.json()
    except Exception:
        data = {}

    print(f"[mp webhook] {data}")

    # MP manda notificaciones de tipo 'payment'
    if data.get("type") != "payment":
        return JSONResponse({"ok": True})

    payment_id = str(data.get("data", {}).get("id", ""))
    if not payment_id:
        return JSONResponse({"ok": True})

    pago = pagos.verificar_pago(payment_id)
    if not pago:
        return JSONResponse({"ok": False, "error": "payment not found"}, status_code=400)

    print(f"[mp] pago {payment_id} status={pago.get('status')} ref={pago.get('external_reference')}")

    if pago.get("status") == "approved":
        ref = pago.get("external_reference", "")
        # external_reference tiene formato "phone|plan"
        if "|" in ref:
            phone, plan = ref.split("|", 1)
        else:
            phone, plan = ref, "basico"
        if phone:
            from pagos import PLANES
            db.activar_suscripcion(phone, payment_id, plan)
            info = PLANES.get(plan, {})
            fotos_txt = "ilimitadas" if info.get("fotos") == -1 else f"{info.get('fotos', 30)} fotos"
            enviar_mensaje(
                phone,
                f"Suscripcion *{plan.capitalize()}* activada! Tenes {fotos_txt} por 30 dias. Manda una foto para empezar.",
            )
            print(f"[mp] suscripcion {plan} activada para {phone}")

    return JSONResponse({"ok": True})


@app.get("/admin/init-db")
def admin_init_db(secret: str = ""):
    if secret != "postia2026":
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    try:
        db.init_db()
        return {"ok": True}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/admin/env")
def admin_env(secret: str = ""):
    if secret != "postia2026":
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    db_url = os.getenv("DATABASE_URL", "NOT SET")
    return {"DATABASE_URL": db_url[:30] + "..." if len(db_url) > 30 else db_url}


@app.get("/admin/info")
def admin_info(secret: str = ""):
    if secret != "postia2026":
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    with db._get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT phone, plan, estado FROM suscripciones")
        rows = cur.fetchall()
    return {"database_url": bool(db.DATABASE_URL), "users": [{"phone": r[0], "plan": r[1], "estado": r[2]} for r in rows]}


@app.get("/admin/set-pro")
def admin_set_pro(phone: str, secret: str = ""):
    if secret != "postia2026":
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    ph = db._placeholder()
    conn = db._get_conn()
    try:
        cur = conn.cursor()
        cur.execute(f"""
            INSERT INTO suscripciones (phone, estado, plan, usos_gratis, fotos_restantes)
            VALUES ({ph},{ph},{ph},{ph},{ph})
            ON CONFLICT(phone) DO UPDATE SET estado=EXCLUDED.estado, plan=EXCLUDED.plan, fotos_restantes=EXCLUDED.fotos_restantes
        """, (phone, "activo", "pro", 0, 999))
        conn.commit()
    finally:
        conn.close()
    return {"ok": True, "phone": phone}


@app.get("/admin/usuarios")
def admin_usuarios(secret: str = ""):
    if secret != "postia2026":
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    usuarios = db.get_usuarios()
    return {"total": len(usuarios), "usuarios": usuarios}


@app.post("/admin/cambiar-plan")
async def admin_cambiar_plan(request: Request, secret: str = ""):
    if secret != "postia2026":
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    data = await request.json()
    phone = data.get("phone")
    plan = data.get("plan")
    planes_fotos = {"trial": 3, "basico": 30, "pro": 100, "ilimitado": -1}
    if not phone or plan not in planes_fotos:
        return JSONResponse({"error": "datos invalidos"}, status_code=400)
    db.cambiar_plan(phone, plan, planes_fotos[plan])
    return {"ok": True, "phone": phone, "plan": plan}


@app.get("/admin/consultas")
def admin_consultas(secret: str = "", tipo: str = ""):
    if secret != "postia2026":
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    rows = db.get_consultas()
    if tipo:
        rows = [r for r in rows if r["tipo"] == tipo]
    return {"total": len(rows), "consultas": rows}


@app.get("/admin/set-pro-all")
def admin_set_pro_all(secret: str = ""):
    if secret != "postia2026":
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    ph = db._placeholder()
    with db._get_conn() as conn:
        cur = conn.cursor()
        cur.execute("UPDATE suscripciones SET plan='pro', estado='activo', fotos_restantes=999")
        conn.commit()
        cur.execute("SELECT phone, plan, estado FROM suscripciones")
        rows = cur.fetchall()
    return {"updated": [r[0] for r in rows]}


@app.get("/pago-exitoso")
def pago_exitoso():
    return {"mensaje": "Pago recibido! Volve a WhatsApp, tu suscripcion ya esta activa."}


@app.get("/pago-fallido")
def pago_fallido():
    return {"mensaje": "El pago no se proceso. Intenta de nuevo."}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8001))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
