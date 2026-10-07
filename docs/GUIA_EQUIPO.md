# Guía del equipo: AI Software Engineering Kit

> Para quién es: cualquier persona del equipo, sea o no desarrolladora.
> Para qué sirve: entender qué es esta herramienta, qué te aporta y cómo usarla paso a paso.
> Tiempo de lectura: unos 15 minutos.

---

## Índice

1. [¿Qué es, en una frase?](#1-qué-es-en-una-frase)
2. [¿Qué problema resuelve?](#2-qué-problema-resuelve)
3. [Cómo funciona (explicado sin tecnicismos)](#3-cómo-funciona-explicado-sin-tecnicismos)
4. [Beneficios para el equipo](#4-beneficios-para-el-equipo)
5. [Métricas medidas](#5-métricas-medidas)
6. [Antes de empezar: lo que necesitas](#6-antes-de-empezar-lo-que-necesitas)
7. [Paso a paso: crear un proyecto nuevo](#7-paso-a-paso-crear-un-proyecto-nuevo)
8. [Paso a paso: usarlo en un proyecto que ya existe](#8-paso-a-paso-usarlo-en-un-proyecto-que-ya-existe)
9. [Paso a paso: trabajar con la IA cada día](#9-paso-a-paso-trabajar-con-la-ia-cada-día)
10. [Cómo leer los resultados](#10-cómo-leer-los-resultados)
11. [Buenas prácticas y advertencias](#11-buenas-prácticas-y-advertencias)
12. [Preguntas frecuentes](#12-preguntas-frecuentes)
13. [Glosario](#13-glosario)
14. [Chuleta de comandos](#14-chuleta-de-comandos)

---

## 1. ¿Qué es, en una frase?

Es un **"manual de trabajo" que se instala dentro de cada proyecto**. Hace que los asistentes de
inteligencia artificial (como Claude, Copilot, Cursor o Codex) trabajen **como lo haría un equipo
profesional**: con orden, con seguridad, probando lo que hacen y documentándolo.

Y desde la versión 1.2, además, **les da a esos asistentes solo la información que necesitan para
cada tarea**, ni más ni menos.

---

## 2. ¿Qué problema resuelve?

### Problema 1: la IA trabaja "a su manera"

Si le pides algo a una IA sin indicaciones, suele:

- escribir código rápido pero sin pruebas;
- olvidar la seguridad (por ejemplo, contraseñas escritas dentro del código);
- no documentar lo que hizo;
- tomar decisiones distintas cada vez.

**El kit le da a la IA las reglas del equipo**, igual que le darías un manual a una persona nueva.

### Problema 2: la IA lee demasiado

Imagina que pides a alguien que arregle un enchufe y, antes de empezar, le haces leer **todos los
manuales de la casa**: fontanería, jardín, tejado, coche… Tardaría más, se cansaría y podría
confundirse.

Con la IA pasa lo mismo. Un proyecto tiene unos **44.000 "tokens"** de documentación (piensa en
los tokens como "trocitos de texto"; 44.000 tokens equivalen aproximadamente a un libro de 100 a
150 páginas). Si la IA lo lee todo para cada tarea:

- **cuesta más**, porque los servicios de IA cobran por la cantidad de texto que procesan;
- **va más lenta**;
- **responde peor**, porque se distrae con información que no viene al caso.

**El kit selecciona automáticamente solo los "manuales" que la tarea necesita.**

---

## 3. Cómo funciona (explicado sin tecnicismos)

Piensa en el kit como en **un buen bibliotecario**:

```
Tú le pides una tarea
        ↓
1. El bibliotecario entiende de qué trata  ............ (clasificador)
        ↓
2. Consulta su mapa de la biblioteca  .................. (grafo de conocimiento)
        ↓
3. Elige los libros relevantes  ........................ (selección y puntuación)
        ↓
4. Comprueba que caben en la mesa  ..................... (presupuesto)
        ↓
5. Marca solo los capítulos útiles  .................... (troceado)
        ↓
6. Le entrega a la IA un paquete preparado  ............ (paquete de contexto)
        ↓
La IA trabaja con lo justo y necesario
```

### Las piezas, una a una

**1. Entiende la tarea.** Lee tu petición y detecta de qué tipo es. Hay 14 tipos posibles:
crear algo nuevo, arreglar un error, mejorar la seguridad, desplegar, documentar, etc.

> Ejemplo: *"Fix ClickHouse query"* se reconoce como **base de datos** + **arreglo de error** +
> tecnología **ClickHouse**.

**2. Consulta el mapa.** El kit tiene un **mapa de conocimiento** (técnicamente, un "grafo") que
sabe qué cosas van juntas. Por ejemplo:

- "Kubernetes necesita Docker";
- "Una tarea de seguridad necesita al especialista en seguridad".

Este mapa se crea solo y se puede regenerar en cualquier momento.

**3. Elige y puntúa.** Cada documento recibe una puntuación de 0 a 1 según lo útil que sea para
tu tarea. Después se clasifica así:

| Etiqueta | Qué significa | ¿Se carga? |
|---|---|---|
| **Obligatorio** (REQUIRED) | Imprescindible para hacer bien la tarea | Siempre |
| **Recomendado** (RECOMMENDED) | Útil, pero no imprescindible | Si es suficientemente relevante y cabe |
| **Opcional** (OPTIONAL) | Poco relacionado | No; solo se menciona |

> 🔒 **Regla de oro:** la **seguridad** y las **pruebas** nunca se eliminan para ahorrar.

**4. Comprueba el presupuesto.** Cada tipo de tarea tiene un límite de texto:

| Tipo de tarea | Límite aproximado |
|---|---|
| Sencilla (un solo tema) | 12.000 tokens |
| Normal (dos o más temas) | 16.000 tokens |
| Compleja (proyecto nuevo, muchos temas) | 24.000 tokens |
| Seguridad | 24.000 tokens |

Si lo imprescindible no cabe, **el kit avisa** ("OVER_BUDGET") en lugar de quitar cosas
importantes.

**5. Trocea.** De los documentos de reglas, solo se toman los capítulos útiles. Por ejemplo, para
una tarea de autenticación se toma el capítulo "Autenticación" de las reglas de seguridad, no el
documento entero.

**6. Explica cada decisión.** Por cada documento, el kit dice **por qué lo incluyó o por qué no**.
Nada es una caja negra.

---

## 4. Beneficios para el equipo

| Beneficio | Qué significa en la práctica |
|---|---|
| 💰 **Menos coste** | La IA procesa entre un 67% y un 76% menos de texto que si lo leyera todo |
| ⚡ **Más rapidez** | Menos texto que leer significa respuestas más ágiles |
| 🎯 **Mejores respuestas** | La IA se concentra en lo relevante y no se distrae |
| 🔒 **Más seguridad** | Las reglas de seguridad se aplican siempre y la herramienta avisa si encuentra contraseñas mal guardadas |
| 📏 **Trabajo homogéneo** | Todos los proyectos siguen las mismas reglas, trabaje quien trabaje |
| 🔍 **Transparencia** | Siempre puedes ver qué información recibió la IA y por qué |
| 🔄 **Fácil de mantener** | Cuando el kit mejora, los proyectos se actualizan con un comando sin perder sus ajustes propios |
| 🏠 **Sin servicios externos** | Todo funciona en tu ordenador; no envía datos a ningún sitio |

---

## 5. Métricas medidas

Estos datos se **midieron realmente** el 6 de octubre de 2026 con la versión 1.2.0, sobre
proyectos de ejemplo.

> ⚠️ Los "tokens" son una **estimación** (número de caracteres dividido entre 4). No es la cifra
> exacta que factura cada proveedor de IA, pero sirve para comparar.

### Cuánto texto recibe la IA en cada tarea

Sin el kit, la IA leería **unos 44.000 tokens** en todas las tareas.

| Tarea de ejemplo | Con el kit 1.1 | Con el kit 1.2 | Ahorro frente a leerlo todo |
|---|---|---|---|
| Crear un nuevo servicio web (endpoint FastAPI) | 13.109 | 13.109 | **70%** |
| Arreglar una consulta de base de datos ClickHouse | 14.679 | 14.679 | **67%** |
| Auditar la seguridad del inicio de sesión | 10.286 | 10.652 * | **76%** |
| Reorganizar un servicio Python | 13.639 | 13.639 | **69%** |
| Desplegar en Kubernetes | 19.943 | **11.033** | **74%** (antes 52%) |

\* En la auditoría de seguridad, la versión 1.2 añade a propósito un poco más de información
(366 tokens) sobre arquitectura, porque es relevante para la seguridad. **La calidad va antes que
el ahorro.**

### Qué significa esto

- En el caso de **Kubernetes**, la versión 1.2 **casi reduce a la mitad** la información enviada
  (de 19.943 a 11.033 tokens) y pasa de **18 documentos a 10**.
- En el resto de tareas mantiene la selección, que ya era buena, y **elige mejor la prioridad**.
  Por ejemplo, ya no considera obligatorio un documento solo porque el proyecto use esa
  tecnología.

### Fiabilidad

- **361 pruebas automáticas** superadas en Windows, con Python 3.9 y 3.12.
- **0 secretos** detectados en el código de la herramienta.
- Pendiente: probarlo en Linux y macOS.

---

## 6. Antes de empezar: lo que necesitas

> 💡 **Si no eres desarrollador:** los pasos de instalación (este apartado) los puede hacer una
> sola vez una persona técnica del equipo en tu ordenador. Después, el uso diario es sencillo.

### Requisitos

1. **Python 3.9 o superior**. Para comprobar si lo tienes, abre una terminal y escribe
   `python --version`.
2. **Git**, para guardar los proyectos en el servidor del equipo (git.netsf.fr).
3. **Un asistente de IA**: Claude Code, GitHub Copilot, Cursor o Codex.

> **¿Qué es una "terminal"?** Es una ventana donde se escriben órdenes de texto. En Windows: pulsa
> la tecla Windows, escribe *PowerShell* y ábrelo. En Visual Studio Code: menú *Terminal* →
> *Nueva terminal*.

### Instalación (una sola vez)

Copia y pega en la terminal:

```bash
pipx install "git+https://git.netsf.fr/<grupo>/ai-software-engineering-kit.git@v1.2.0"
```

> Sustituye `<grupo>` por el grupo donde está publicado el kit en git.netsf.fr (pregúntaselo al
> responsable de la herramienta).

Para comprobar que funciona:

```bash
ai-project version
```

Si ves algo como `ai-project 1.2.0`, ya está instalado. ✅

---

## 7. Paso a paso: crear un proyecto nuevo

### Paso 1: abre la terminal en la carpeta donde guardas tus proyectos

Por ejemplo:

```bash
cd Documentos/proyectos
```

### Paso 2: lanza el asistente de creación

```bash
ai-project init
```

### Paso 3: responde a las preguntas

La herramienta te pregunta, una a una, cosas como:

| Pregunta | Ejemplo de respuesta |
|---|---|
| Nombre del proyecto | `portal-clientes` |
| Tipo de proyecto | Backend API, Frontend, Full Stack, Automatización… |
| Tecnología | Python + FastAPI, React… |
| Base de datos | PostgreSQL, ClickHouse, ninguna… |
| Despliegue | Kubernetes (estándar del equipo) |
| Asistentes de IA | Claude, Copilot, Cursor… |
| Objetivo del proyecto | "Que los clientes consulten sus pedidos en línea" |

> 💡 Si no sabes qué responder, **pulsa Enter**: se usa la opción recomendada.

Al final verás un **resumen**. Confirma con Enter y se crea el proyecto.

### Paso 4: describe tu proyecto (el paso más importante)

Abre el archivo `.ai/context/project.md` del nuevo proyecto y **rellena los apartados que dicen
`TODO`**:

- ¿Qué problema resuelve?
- ¿Quién lo va a usar?
- ¿Qué tiene que hacer?
- ¿Qué limitaciones hay (plazos, tecnologías obligatorias…)?

> ⏱️ Son unos 15 minutos y es **lo que más mejora el trabajo de la IA**: es lo primero que lee en
> cada tarea.

### Paso 5: comprueba que todo está bien

```bash
cd portal-clientes
ai-project doctor
```

Verás una lista de comprobaciones:

- ✓ (verde): correcto;
- ! (amarillo): aviso, conviene revisarlo;
- ✗ (rojo): problema, hay que corregirlo.

Al principio es normal ver avisos (por ejemplo, "aún no hay pruebas" o "faltan TODO por
completar").

### Paso 6: guarda el proyecto en el servidor del equipo

```bash
git init
git add .
git commit -m "Proyecto inicial"
git remote add origin https://git.netsf.fr/<grupo>/portal-clientes.git
git push -u origin main
```

🎉 **Listo. Ya puedes trabajar con la IA (apartado 9).**

---

## 8. Paso a paso: usarlo en un proyecto que ya existe

### Caso A: el proyecto nunca ha usado el kit

**Paso 1:** abre la terminal **dentro** de la carpeta del proyecto:

```bash
cd ruta/a/mi-proyecto
```

**Paso 2:** añade el kit al proyecto (fíjate en el punto final):

```bash
ai-project init .
```

> 🛡️ **Tranquilidad:** el kit **no borra ni sobrescribe** tus archivos. Si ya existía un archivo
> con el mismo nombre (por ejemplo `AGENTS.md`), deja su propia versión al lado, con el nombre
> `AGENTS.md.kit-new`, para que decidas qué conservar.

**Paso 3:** rellena `.ai/context/project.md` (igual que en el paso 4 del apartado 7).

**Paso 4:** comprueba con `ai-project doctor`.

### Caso B: el proyecto ya usa una versión anterior del kit

**Paso 1:** actualiza la herramienta en tu ordenador:

```bash
pipx upgrade ai-software-engineering-kit
```

**Paso 2:** entra en el proyecto y **mira primero qué va a cambiar**, sin tocar nada:

```bash
cd ruta/a/mi-proyecto
ai-project update --dry-run
```

**Paso 3:** si estás de acuerdo, aplica la actualización:

```bash
ai-project update
```

> 🛡️ Tus personalizaciones se conservan. Si has modificado un archivo que el kit también quiere
> cambiar, verás la palabra **CONFLICT** y aparecerá un archivo `.kit-new` para que compares las
> dos versiones con calma.

**Paso 4 (opcional, recomendado):** activa los nuevos límites por tipo de tarea. Los proyectos
antiguos mantienen un único límite para todas las tareas. Para activar los límites sencilla,
normal, compleja y seguridad, pide a una persona técnica que copie el bloque `budgets` de la
plantilla del kit en el archivo `.ai/context/budget.json` del proyecto.

---

## 9. Paso a paso: trabajar con la IA cada día

### Paso 1: abre el proyecto con tu asistente de IA

Abre la carpeta del proyecto en Claude Code, Visual Studio Code con Copilot, o Cursor. **No
tienes que configurar nada:** el asistente encuentra solo el archivo `AGENTS.md` y sabe cómo
trabajar.

### Paso 2: pide la tarea indicando que use el kit

Puedes copiar y adaptar estas frases:

**Para una funcionalidad nueva:**

> Ejecuta `ai-project context --task "Add order export to CSV" --json`, carga solo ese contexto y
> sigue `.ai/workflows/new-feature.md` para añadir la exportación de pedidos a CSV.

**Para arreglar un error:**

> Ejecuta `ai-project context --task "Fix login error when password has spaces" --json` y sigue
> `.ai/workflows/bug-fix.md`.

**Para una revisión de seguridad:**

> Ejecuta `ai-project context --task "Security audit of the authentication module" --json` y sigue
> `.ai/workflows/security-audit.md`.

> 💡 **Consejo importante:** escribe la descripción de la tarea (lo que va entre comillas tras
> `--task`) **en inglés**. El clasificador reconoce palabras clave en inglés; en español solo
> reconoce los términos técnicos (API, SQL, React…).

### Paso 3: revisa lo que hace la IA

Trata su trabajo como el de un compañero nuevo:

- ¿Hizo lo que pediste?
- ¿Muestra resultados **reales** de las pruebas? (El kit le obliga a decir **"NOT VALIDATED"**
  si no ha podido comprobar algo.)
- ¿Actualizó la documentación?

### Paso 4: ¿quieres ver qué información recibe la IA?

Puedes consultarlo tú mismo, sin la IA:

```bash
ai-project context --task "Deploy service to Kubernetes"
```

Verás la lista de documentos elegidos, los descartados y el motivo de cada uno (apartado 10).

---

## 10. Cómo leer los resultados

Este es un resultado real del comando anterior, simplificado:

```text
Routing: knowledge graph: loaded, 157 nodes, 483 edges     ← el mapa está cargado y en orden
Classification: deployment, kubernetes                    ← tipo de tarea detectado
Budget: simple - 12,000 tokens                            ← límite aplicado

Selected agents:                                          ← especialistas elegidos
✓ 12-devops  [REQUIRED, score 0.68] task matched: kubernetes, deploy
✓ 10-testing [REQUIRED, score 0.33] protected: security and tests are never dropped

Skipped:                                                  ← especialistas descartados
○ 02-backend - RECOMMENDED but low relevance: score 0.23 < threshold 0.30

Stack guides:                                             ← guías de tecnología
✓ kubernetes [REQUIRED] named in the task
✓ docker     [REQUIRED] dependency of a stack named in the task
○ linux      RECOMMENDED but low relevance
```

| Lo que ves | Qué significa |
|---|---|
| ✓ | Se incluye en el paquete para la IA |
| ○ | No se incluye; al lado aparece el motivo |
| `score 0.68` | Puntuación de relevancia (de 0 a 1; cuanto más alta, más relevante) |
| `REQUIRED` | Obligatorio |
| `RECOMMENDED` | Recomendado; entra solo si es suficientemente relevante |
| `Status: OK` | Cabe en el presupuesto |
| `Status: OVER_BUDGET` | Lo imprescindible supera el límite: la tarea quizá es demasiado grande; conviene dividirla |
| `Estimated reduction: 74%` | Cuánto texto se ahorra frente a leerlo todo |

---

## 11. Buenas prácticas y advertencias

### ✅ Haz esto

- **Rellena bien `.ai/context/project.md`**: es lo que más mejora los resultados.
- **Describe las tareas con claridad** y en inglés: *"Add CSV export for orders"* funciona mejor
  que *"hazme lo del CSV"*.
- **Divide las tareas grandes** en varias pequeñas, sobre todo si ves `OVER_BUDGET`.
- **Ejecuta `ai-project doctor`** de vez en cuando y antes de entregar un trabajo.
- **Actualiza el kit** cuando el equipo publique una versión nueva (apartado 8, caso B).

### ❌ Evita esto

- **No edites a mano** los archivos `graph.json` ni `index.json` de `.ai/context/`: se regeneran
  solos y tus cambios se perderían.
- **No modifiques** los archivos de `.ai/agents/` ni `.ai/rules/`. Si tu proyecto necesita reglas
  propias, escríbelas en la carpeta `.ai/custom/`.
- **Nunca guardes contraseñas ni claves** en archivos `.env` ni en el código.

### 🔒 Aviso de seguridad sobre los archivos `.env`

Si `ai-project doctor` encuentra contraseñas reales en un archivo `.env`, mostrará un **aviso
grande en amarillo**. No bloquea tu trabajo, pero **tómalo en serio**:

1. Considera esas contraseñas **comprometidas** y cámbialas.
2. Pide que se guarden de forma segura: en los secretos de Kubernetes, en un gestor de contraseñas
   (vault) o en las variables protegidas del CI.
3. Avisa al responsable de seguridad (vincent.goutagny@netsf.fr).

---

## 12. Preguntas frecuentes

**¿Tengo que saber programar para usarlo?**
No para el uso diario: pedir tareas a la IA y revisar resultados. La instalación conviene que la
haga una persona técnica la primera vez.

**¿Envía mis datos a algún sitio?**
No. El kit funciona por completo en tu ordenador, sin conexión ni servicios externos. Solo tu
asistente de IA se comunica con su proveedor, como siempre.

**¿Reduce la factura real de la IA?**
Reduce la cantidad de texto que se prepara para la IA, que es lo que más pesa en el coste. Las
cifras de tokens son **estimaciones**; la factura exacta depende de cada proveedor y de cómo use el
asistente esa información.

**¿Puede la IA dejar de lado algo importante por ahorrar?**
No en lo esencial. La seguridad y las pruebas están **protegidas**: nunca se eliminan. Si lo
imprescindible no cabe, el kit avisa en lugar de recortar.

**¿Y si el kit elige mal los documentos?**
Siempre explica sus motivos, así que es fácil detectarlo. Puedes nombrar la tecnología en la tarea
(por ejemplo, *"... in React"*) o comentarlo al responsable del kit para ajustar la configuración.

**¿Qué pasa si el "mapa de conocimiento" se estropea o se borra?**
Nada grave: el kit lo reconstruye automáticamente. También puedes regenerarlo con
`ai-project context --rebuild-graph`.

**¿Funciona con cualquier asistente de IA?**
Sí: Claude Code, GitHub Copilot, Cursor, Codex y cualquier otro que lea el archivo `AGENTS.md`.

**¿Qué hago si veo "CONFLICT" al actualizar?**
Significa que modificaste un archivo que el kit también actualizó. Compara tu archivo con el
`.kit-new`, quédate con lo que necesites y borra el `.kit-new`. Si dudas, pide ayuda a una persona
técnica.

---

## 13. Glosario

| Término | Explicación sencilla |
|---|---|
| **Agente** | Un "rol" o especialista que la IA adopta: experto en seguridad, en bases de datos, en pruebas… |
| **AGENTS.md** | El archivo de bienvenida que cualquier IA lee primero en el proyecto |
| **Contexto** | La información que se le da a la IA para hacer una tarea |
| **Token** | Un trocito de texto (aproximadamente 4 letras). Los servicios de IA miden y cobran por tokens |
| **Grafo de conocimiento** | Un mapa que indica qué documentos están relacionados entre sí |
| **Presupuesto** | El límite de información que se prepara para cada tarea |
| **Workflow** | Un procedimiento paso a paso (por ejemplo, "cómo arreglar un error") |
| **Stack** | Una tecnología concreta (Python, React, Kubernetes…) y su guía |
| **Terminal** | La ventana donde se escriben órdenes de texto |
| **Commit / push** | Guardar los cambios en el historial y enviarlos al servidor del equipo (git.netsf.fr) |
| **doctor** | El comando que revisa que el proyecto esté bien configurado |

---

## 14. Chuleta de comandos

| Quiero… | Comando |
|---|---|
| Ver si el kit está instalado | `ai-project version` |
| Crear un proyecto nuevo | `ai-project init` |
| Añadir el kit a un proyecto existente | `ai-project init .` |
| Revisar que todo está bien | `ai-project doctor` |
| Ver qué cambiaría al actualizar | `ai-project update --dry-run` |
| Actualizar el proyecto | `ai-project update` |
| Ver qué información recibiría la IA | `ai-project context --task "descripción en inglés"` |
| Regenerar el mapa de conocimiento | `ai-project context --rebuild-graph` |
| Ver los tipos de proyecto disponibles | `ai-project list` |
| Ver la ayuda | `ai-project help` |

---

**¿Dudas o sugerencias?** Contacta con el responsable del kit en el equipo. La documentación
técnica completa está en la carpeta `docs/` del repositorio (en inglés).
