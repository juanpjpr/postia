# PostIA — Plan de Negocio

> Bot de WhatsApp con IA que transforma fotos de productos en imágenes profesionales con fondo personalizado + descripciones listas para publicar.

---

## Roadmap

- [x] Bot de WhatsApp funcional con flujo completo
- [x] Generación de imagen con FLUX Kontext (fal.ai) — reemplaza fondo con foto real del usuario
- [x] Fallback a GPT-image-1 si no hay foto
- [x] Sistema de suscripciones con MercadoPago (3 planes)
- [x] Landing page deployada en Railway con carousel antes/después
- [x] DB PostgreSQL en Railway
- [x] Perfil de negocio por usuario (`mi negocio: ...`)
- [x] Flujo de fondo por plan: básico = blanco/negro, pro = descripción libre
- [x] Sessions persistidas en DB (sobreviven redeploys)
- [x] Rate limiting por número (20 mensajes/60s)
- [x] Validación de firma Twilio en webhook
- [x] Admin auth server-side con token
- [x] Número WhatsApp real (+13186484804) — migrado de sandbox
- [x] USOS_GRATIS = 3
- [x] MercadoPago en producción (MP_SANDBOX=false)
- [ ] **Testear flujo de pago completo** con cuenta de tercero
- [ ] **Dominio propio** para la landing (ej: postia.app)
- [ ] **Grabar video demo** antes/después para ads

---

## La Idea

Bot de WhatsApp que recibe una foto + descripción de un producto y devuelve automáticamente una **imagen con fondo reemplazado por IA + descripción lista para publicar**, optimizada según la plataforma elegida. El cliente paga suscripción mensual vía MercadoPago.

---

## La promesa del producto

> *"Che, qué fácil y rápido es esto. Me sirve, me saca tiempo y trabajo."*

> *"Che, estoy usando una app que está muy buena, me crea las publicaciones y me las mejora."*

Cada decisión de producto — cantidad de pasos, tono del bot, velocidad, calidad de la imagen — se evalúa contra estas dos reacciones.

---

## A quién apunta PostIA

**El usuario ideal es un emprendedor que no tiene tiempo, ni ganas, ni conocimientos técnicos para crear contenido todos los días.**

Pensado para:
- El dueño de una hamburguesería que saca la foto del plato y la manda sin pensar
- La chica que vende ropa por Instagram y no sabe escribir hashtags
- El que vende en Mercado Libre y no tiene idea de SEO
- El almacén del barrio que quiere tener estado de WhatsApp todos los días

---

## Experiencia del Usuario

1. Abre WhatsApp y manda foto del producto con el nombre como texto
2. Bot pregunta categoría (comida, ropa, electrónica, etc.)
3. Bot pregunta fondo:
   - Plan básico/trial: `1 - Fondo blanco` / `2 - Fondo negro`
   - Plan pro/ilimitado: blanco, negro, o texto libre (ej: _"horno de barro"_, _"noche con luces"_)
4. Bot pregunta plataforma (Instagram, Facebook, WhatsApp, Mercado Libre)
5. En ~30 segundos recibe imagen con fondo reemplazado + descripción lista para copiar y pegar

**Sin apps, sin logins, sin complicaciones.**

---

## Planes y Precios

| Plan      | Publicaciones/mes | Fondo               | Precio (ARS)   |
|-----------|-------------------|---------------------|----------------|
| Trial     | 3 gratis          | Blanco o negro      | Gratis         |
| Básico    | 30                | Blanco o negro      | $15.000/mes    |
| Pro       | 100               | Libre (descripción) | $30.000/mes    |
| Ilimitado | Sin límite        | Libre (descripción) | $50.000/mes    |

---

## Stack Técnico

| Componente    | Tecnología                          | Costo                     |
|---------------|-------------------------------------|---------------------------|
| Backend       | FastAPI (Python) en Railway         | ~$5 USD/mes               |
| WhatsApp      | Twilio WhatsApp API (+13186484804)  | ~$1.15 USD/mes + uso      |
| IA Imágenes   | fal.ai FLUX Kontext (img2img)       | ~$0.05 por imagen         |
| IA Imágenes   | OpenAI GPT-image-1 (fallback)       | ~$0.04 por imagen         |
| IA Texto      | OpenAI gpt-4o-mini                  | ~$0.001 por descripción   |
| Pagos         | MercadoPago (webhook automático)    | % por transacción         |
| DB            | PostgreSQL en Railway               | incluido en plan          |
| Deploy        | Railway (auto-deploy desde GitHub)  | ~$5 USD/mes               |

---

## Costos Mensuales Operativos

| Herramienta              | Costo           |
|--------------------------|-----------------|
| Twilio WhatsApp API      | ~$2 USD         |
| OpenAI API (100 imgs)    | $5 USD          |
| Railway deploy           | ~$5 USD         |
| Meta Ads (publicidad)    | $30-50 USD      |
| **Total**                | **~$42-62 USD/mes** |

---

## Rentabilidad (en ARS)

```
10 clientes Plan Básico   → $150.000 ARS/mes
10 clientes Plan Pro      → $300.000 ARS/mes
20 clientes Plan Pro      → $600.000 ARS/mes
```

---

## Checklist Próximos Pasos

### Producción
- [ ] Testear flujo de pago completo con cuenta de tercero
- [ ] Dominio propio (postia.app)

### Go-to-market
- [ ] Grabar video demo antes/después para ads
- [ ] Conseguir primeros 5 clientes piloto
- [ ] Lanzar ads en Instagram apuntando a emprendedores

---

## Endpoints Admin

Base URL: `https://web-production-e9401.up.railway.app`
Panel visual: `/admin` (user: `postia`, pass en env var `ADMIN_PASSWORD`)

Auth: todos los endpoints requieren header `X-Admin-Token: <token>` obtenido via login.

```
POST   /admin/login               { user, password } → { token }
GET    /admin/usuarios            Lista usuarios con stats
POST   /admin/cambiar-plan        { phone, plan } → cambia plan
DELETE /admin/usuarios/{phone}    Elimina usuario
GET    /admin/consultas           Lista consultas y feedback
GET    /admin/info                Info DB y usuarios (debug)
GET    /admin/init-db             Fuerza creación de tablas
GET    /admin/set-pro?phone=      Pone número en plan pro
GET    /admin/set-pro-all         Pone todos en plan pro
```
