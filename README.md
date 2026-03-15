# PostIA — Plan de Negocio

> Bot de WhatsApp con IA que transforma fotos de platos y productos en contenido profesional listo para publicar.

---

## Roadmap

- [x] Bot de WhatsApp funcional con flujo completo
- [x] Generación de imagen con GPT-image-1 y FLUX Kontext
- [x] Sistema de suscripciones con MercadoPago (3 planes)
- [x] Landing page deployada en Railway
- [x] Árbol de decisiones: modo rápido vs detallado por categoría
- [ ] **Migrar DB a PostgreSQL** — SQLite en Railway se resetea en cada deploy
- [ ] **Testear flujo de pago completo** con tarjetas de prueba de MercadoPago
- [ ] **Dominio propio** para la landing (ej: postia.app)
- [ ] **Resolver descarga de imágenes Twilio** para que FLUX Kontext funcione en producción

---

## La Idea

Bot de WhatsApp que recibe una foto + descripción de un plato o producto y devuelve automáticamente una **imagen mejorada con IA + descripción lista para publicar**, optimizada según la plataforma elegida. El cliente paga suscripción mensual vía MercadoPago.

---

## La promesa del producto

Hay dos cosas que PostIA tiene que lograr en quien lo usa:

> *"Che, qué fácil y rápido es esto. Me sirve, me saca tiempo y trabajo."*

> *"Che, estoy usando una app que está muy buena, me crea las publicaciones y me las mejora."*

La primera es sobre **utilidad real**: el usuario siente que no hizo nada y ya tiene todo listo.
La segunda es sobre **orgullo y recomendación**: el usuario lo cuenta porque siente que tiene algo que otros no tienen.

Cada decisión de producto — cantidad de pasos, tono del bot, velocidad, calidad de la imagen — se evalúa contra estas dos reacciones.

---

## A quién apunta PostIA

**El usuario ideal es un emprendedor que no tiene tiempo, ni ganas, ni conocimientos técnicos para crear contenido todos los días.**

Pensado para:
- El dueño de una hamburguesería que saca la foto del plato y la manda sin pensar
- La chica que vende ropa por Instagram y no sabe escribir hashtags
- El que vende en Mercado Libre y no tiene idea de SEO
- El almacén del barrio que quiere tener estado de WhatsApp todos los días

**Lo que NO es PostIA:**
No es una herramienta para marketers ni diseñadores. No requiere saber nada de IA, ni de redes sociales, ni de tecnología. El único requisito es saber mandar un mensaje de WhatsApp.

**Principio de diseño del bot:**
Cada interacción tiene que ser tan simple que una persona de 60 años con emprendimiento pueda usarla sin ayuda. Mensajes cortos, opciones numeradas, cero jerga técnica. El flujo rápido (foto → resultado en 3 toques) es el default. El detallado existe pero nunca se impone.

---

## Experiencia del Usuario

1. Abre WhatsApp
2. Saca foto del plato/producto con el celu
3. Manda la foto con texto: `"asado de tira con chimichurri"`
4. Bot pregunta: _"¿Dónde vas a publicar?"_
   - 1️⃣ Instagram
   - 2️⃣ Mercado Libre
   - 3️⃣ Facebook
   - 4️⃣ Todos
5. Cliente responde `"4"`
6. En 30 segundos recibe todo listo para publicar

**Sin apps, sin logins, sin complicaciones.**

---

## Lo que Devuelve el Bot por Plataforma

| Plataforma    | Imagen                         | Descripción                               |
|---------------|--------------------------------|-------------------------------------------|
| Instagram     | 1080x1080 cuadrada             | Corta, emojis, hashtags                   |
| Mercado Libre | Fondo blanco profesional       | Título SEO + bullet points técnicos       |
| Facebook      | 1200x630 horizontal            | Más larga, tono familiar, precio incluido |

---

## Flujo Técnico Completo

```
Cliente manda foto + descripción por WhatsApp
        ↓
Webhook recibe (Twilio / Meta WhatsApp API)
        ↓
Bot pregunta plataforma destino
        ↓
Cliente elige (Instagram / ML / Facebook / Todos)
        ↓
Backend llama OpenAI API (DALL-E + GPT-4)
        ↓
Genera imagen optimizada por plataforma + descripción
        ↓
Bot devuelve todo al cliente automáticamente
        ↓
Cliente copia y pega directo
```

---

## Flujo de Cobro

```
Bot detecta suscripción vencida
        ↓
Manda mensaje automático:
"Tu plan venció 🔴 Renovalo acá para seguir:"
[Link MercadoPago]
        ↓
Cliente paga en 2 minutos
        ↓
MercadoPago notifica backend (webhook)
        ↓
Bot se reactiva automáticamente
```

---

## Planes y Precios

| Plan     | Plataformas    | Imágenes/mes | Precio        |
|----------|----------------|--------------|---------------|
| Starter  | 1 plataforma   | 20           | $8 USD/mes    |
| Standard | 2 plataformas  | 50           | $18 USD/mes   |
| Pro      | Todas          | Ilimitado    | $35 USD/mes   |

---

## Stack Técnico

| Componente    | Tecnología                   | Costo                     |
|---------------|------------------------------|---------------------------|
| Backend       | Spring Boot (Java)           | Gratis                    |
| WhatsApp      | Twilio o Meta WhatsApp API   | ~$10 USD/mes              |
| IA Imágenes   | OpenAI DALL-E API            | ~$0.05 por imagen         |
| IA Texto      | OpenAI GPT-4 API             | ~$0.01 por descripción    |
| Pagos         | MercadoPago Suscripciones    | % por transacción         |
| Deploy        | Railway o Render             | Gratis para empezar       |

---

## Datos por Usuario en Backend

```java
{
  whatsappNumber: "+5491112345678",
  plan: "STANDARD",
  plataformas: ["INSTAGRAM", "MERCADOLIBRE"],
  imagenesUsadas: 12,
  imagenesLimit: 50,
  suscripcionActiva: true,
  vencimiento: "2026-04-14"
}
```

---

## Tiempo de Desarrollo

| Componente                        | Tiempo   |
|-----------------------------------|----------|
| Webhook WhatsApp                  | 1 día    |
| Integración OpenAI                | 1 día    |
| Lógica del flujo + plataformas    | 2 días   |
| MercadoPago suscripción           | 1-2 días |
| **Total**                         | **~1 semana** |

---

## Costos Mensuales Operativos

| Herramienta              | Costo           |
|--------------------------|-----------------|
| Twilio WhatsApp API      | $10 USD         |
| OpenAI API (100 imgs)    | $5 USD          |
| Railway deploy           | Gratis          |
| Meta Ads (publicidad)    | $30-50 USD      |
| **Total**                | **~$45-65 USD/mes** |

---

## Rentabilidad

```
10 clientes plan Starter  → $80 USD  - $65 costos = $15 USD
10 clientes plan Standard → $180 USD - $65 costos = $115 USD
20 clientes plan Standard → $360 USD - $65 costos = $295 USD
```

---

## Estrategia de Publicidad

Antes de lanzar grabás un video:

1. Foto fea de un plato
2. La mandás al bot por WhatsApp
3. En 30 segundos llega foto pro + descripción
4. _"Probalo gratis 7 días"_

**Ad en Instagram apuntando a:**
- Dueños de restaurantes
- Vendedores de Mercado Libre
- Argentina, radio 50km de tu ciudad

---

## Identidad

| Elemento        | Detalle                                           |
|-----------------|---------------------------------------------------|
| Nombre          | PostIA                                            |
| Dominio         | postia.com.ar / postia.app                        |
| Instagram       | @postia o @postia.ar                              |
| WhatsApp        | PostIA Business                                   |
| Logo concepto   | Cámara simple + rayo de velocidad                 |
| Colores         | Naranja/blanco o verde/blanco (destacan en WA)    |

---

## Prompt Base del Bot

```
Tengo esta foto de [nombre del plato/producto].
Plataforma destino: [Instagram / Mercado Libre / Facebook]

1. Generá una imagen mejorada optimizada para [plataforma]:
   - Instagram: cuadrada 1080x1080, iluminación cálida, fondo rústico
   - Mercado Libre: fondo blanco profesional, producto centrado
   - Facebook: horizontal 1200x630, composición apetitosa

2. Escribí una descripción optimizada para [plataforma]:
   - Instagram: máximo 3 líneas, emojis, 5 hashtags relevantes
   - Mercado Libre: título SEO + bullet points con características
   - Facebook: tono familiar argentino, precio si corresponde
```

---

## Plan de Lanzamiento

| Hito         | Acción                                              |
|--------------|-----------------------------------------------------|
| Semana 1     | MVP manual con vecino parrilla (gratis)             |
| Semana 2     | Bot funcionando WhatsApp + OpenAI                   |
| Semana 3     | MercadoPago integrado                               |
| Semana 4     | Primeros 5 clientes pagando                         |
| Mes 2        | Video antes/después para ads                        |
| Mes 3        | 20+ clientes recurrentes                            |

---

## Checklist Próximos Pasos

### Validación
- [ ] Probar prompt con foto real de la parrilla del vecino
- [ ] Validar que le gusta el resultado al dueño
- [ ] Ofrecerle el servicio manual gratis 1 semana

### Identidad
- [ ] Registrar @postia en Instagram
- [ ] Registrar postia.com.ar

### Desarrollo
- [ ] Armar webhook WhatsApp con Spring Boot
- [ ] Integrar OpenAI API (imágenes + texto)
- [ ] Lógica de plataformas (Instagram / ML / Facebook)
- [ ] Integrar MercadoPago suscripciones

### Go-to-market
- [ ] Grabar video demo para ads
- [ ] Conseguir 5 clientes piloto

---

## Endpoints Admin (temporales, solo desarrollo)

Base URL: `https://web-production-e9401.up.railway.app`
Secret: `postia2026`

| Endpoint | Descripción |
|----------|-------------|
| `GET /admin/info?secret=` | Lista todos los usuarios y muestra si usa Postgres o SQLite |
| `GET /admin/env?secret=` | Muestra el valor parcial de `DATABASE_URL` para debug |
| `GET /admin/init-db?secret=` | Fuerza la creación de la tabla `suscripciones` |
| `GET /admin/set-pro?phone=whatsapp%3A%2B549XXXXXXXX&secret=` | Pone un número específico en plan pro con 999 fotos |
| `GET /admin/set-pro-all?secret=` | Pone todos los usuarios existentes en plan pro |
