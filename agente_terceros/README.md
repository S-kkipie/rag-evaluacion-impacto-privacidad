# Agente de Terceros (DPAs) — PIMS multiagente ISO/IEC 27701:2025

Agente 7 de los 8 del PIMS multiagente. Gestiona a los **encargados del tratamiento**:
registra a los proveedores, revisa sus contratos de encargo (DPA) contra las cláusulas mínimas
exigibles, evalúa su riesgo, controla vencimientos y subencargados y somete cada decisión a una
**aprobación humana (HITL)**.

| | |
|---|---|
| Controles ISO/IEC 27701:2025 | A.1.2.7 (contratos con encargados), A.2.5.7 (divulgación de subcontratistas), A.2.5.8 (contratación de subencargados), A.2.5.9 (cambio de subencargado) |
| Herramientas MCP | `list_processors`, `check_dpa_status`, `evaluate_vendor` (+ `processors_in_breach`) |
| Entradas | Contratos (PDF/TXT), lista de proveedores, perfil de seguridad, cambios de subcontratistas |
| Salidas | Registro de DPAs vigentes, alertas de renovación, evaluación de riesgo, informe de brechas del contrato |
| Puerta HITL | Asesoría Legal aprueba o rechaza cada DPA nuevo y cada cambio de subencargado |

**Stack:** Python · Flask · HTML/CSS/JavaScript puro · FAISS · embeddings locales con Ollama
(`nomic-embed-text`) · LLM Gemini 2.5 Flash · SQLite (esquema portable a PostgreSQL) · MCP.

## Arquitectura

```
                      ┌────────────── Interfaz web (Flask + JS puro) ──────────────┐
                      │ Panel · Proveedores · Revisar DPA · Aprobaciones · Brecha  │
                      │ Consulta normativa · Bitácora                              │
                      └───────────────┬────────────────────────────────────────────┘
                                      │ API REST /api/...
Orquestador / otros agentes ──MCP──► Agente (agente.py)
  (stdio, JSON-RPC)                   │ list_processors · check_dpa_status · evaluate_vendor
                                      │ revisar_y_registrar · encargados_implicados · consultar
          ┌───────────────────────────┼───────────────────────────┐
          ▼                           ▼                           ▼
 Revisor de DPA (revisor.py)   Riesgo (riesgo.py)          Repositorio (db.py)
 13 cláusulas mínimas          probabilidad × impacto       proveedores, dpas,
 RAG FAISS por cláusula        determinista (4×4)           subencargados, aprobaciones,
 1 llamada Gemini → JSON                                    bitácora de auditoría
 verificación literal de citas
          │
          ▼
 Índice FAISS (IndexFlatIP, coseno) ◄── nomic-embed-text (Ollama, local)
 978 fragmentos con fuente, artículo/cláusula y página
```

### Revisión de un DPA

1. El contrato se extrae (pypdf) y se limpia.
2. Por cada una de las **13 cláusulas mínimas** (`checklist.py`) se recuperan del índice FAISS
   2 fragmentos de la norma peruana + 4 generales.
3. Una sola llamada a Gemini devuelve, por cláusula: `cumple | parcial | falta`, la cita literal del
   contrato, los fragmentos que la fundamentan y una recomendación.
4. **Control anti-alucinación**: cada frase citada como evidencia debe aparecer literal en el
   contrato; si no, un "cumple" baja a "parcial" y se marca para revisión manual.
5. Cumplimiento = promedio ponderado por criticidad (peso 3 = esencial).
6. El DPA queda `pendiente_aprobacion` hasta que Legal decide; la decisión queda en la bitácora.

### Riesgo del proveedor

Matriz 4×4 (AEPD / NTP-ISO 31000). Impacto: volumen de titulares (+1 si hay datos sensibles).
Probabilidad: +1 transferencia a país sin nivel adecuado, +1 subencargados, +1/+2 incidentes,
+1 DPA sin revisar o con cumplimiento < 70 %, +1 DPA vencido, −1 certificación ISO/IEC 27701.
Nivel: bajo ≤ 3, medio ≤ 6, alto ≤ 9, crítico > 9, con frecuencia de revisión de 24/12/6/3 meses.

## Corpus normativo (`data/raw`)

| Sigla | Documento | Jurisdicción |
|---|---|---|
| LPDP | Ley N.º 29733, Ley de Protección de Datos Personales (art. 30) | Perú |
| RLPDP | D.S. N.º 016-2024-JUS (arts. 28-33 y 36: tercerización, encargo, subcontratación, incidentes) | Perú |
| RGPD | Reglamento (UE) 2016/679 (art. 28) | Unión Europea |
| EDPB-07/2020 | Directrices 07/2020 del CEPD sobre responsable y encargado | Unión Europea |
| CCT-2021/915 | Decisión de Ejecución (UE) 2021/915, cláusulas contractuales tipo del art. 28 | Unión Europea |

**ISO/IEC 27701:2025** no es de libre acceso, así que no se indexa. `checklist.py` cataloga los títulos de
sus controles con una paráfrasis propia. La numeración de 2025 se infiere de la correspondencia con la
edición de 2019 (Anexo F) y hay que verificarla contra la norma antes de citarla formalmente.

## Uso

```bash
cd agente_terceros
uv sync
ollama pull nomic-embed-text          # embeddings locales
# GOOGLE_API_KEY en ../.env (compartido con el RAG del avance) o en agente_terceros/.env
uv run agente-terceros ingest         # (opcional) reconstruye data/index; ya viene construido
uv run agente-terceros demo           # 4 proveedores ficticios; revisa 2 DPAs con Gemini
uv run agente-terceros web            # http://localhost:5000
uv run agente-terceros mcp            # servidor MCP por stdio para el orquestador
uv run pytest                         # 57 pruebas, no necesitan red ni API
```

Para conectar el servidor MCP a un cliente (p. ej. el orquestador o Claude Desktop):

```json
{ "mcpServers": { "pims-terceros": {
    "command": "uv", "args": ["--directory", "agente_terceros", "run", "agente-terceros", "mcp"] } } }
```

### Escenario de demostración

| Proveedor | Situación | Lo que muestra el agente |
|---|---|---|
| NubeSegura S.A.C. | DPA completo, ISO 27701, subencargado AWS aprobado | Cumplimiento ≈ 98 %, riesgo bajo |
| MailRápido LLC | Contrato de mailing deficiente (EE. UU.), propone a Mixpanel | ≈ 21 %, riesgo crítico, 2 decisiones HITL pendientes |
| PagoFácil Perú S.A. | DPA heredado que vence en 25 días | Alerta de renovación |
| LabClínico Arequipa | Datos de salud sin DPA, 2 incidentes | Riesgo crítico; aparece en el flujo de brecha "salud" |

Los contratos de ejemplo están en `data/ejemplos/` y sirven para probar "Revisar DPA" desde la interfaz.

## API REST

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/api/panel` | KPIs, alertas, pendientes, actividad |
| GET/POST | `/api/proveedores` | Listar (con DPA y riesgo) / registrar |
| GET | `/api/proveedores/<id>` | Ficha: riesgo, DPA, historial, subencargados |
| POST | `/api/proveedores/<id>/dpa` | Subir contrato (multipart: `archivo`, `fecha_firma`, `fecha_vencimiento`) |
| POST | `/api/proveedores/<id>/subencargados` | Notificar un subencargado (queda pendiente) |
| GET | `/api/aprobaciones` · POST `/api/aprobaciones/<id>` | Cola HITL / decidir `{aprobado, revisor, comentario}` |
| GET | `/api/brecha?termino=salud` | Encargados implicados en una brecha |
| POST | `/api/consulta` | RAG normativo `{pregunta, jurisdiccion}` |
| GET | `/api/tools/{list_processors, check_dpa_status/<id>, evaluate_vendor/<id>}` | Herramientas MCP por HTTP |
| GET | `/api/historial` · `/api/checklist` | Bitácora y catálogo de cláusulas/controles |

## Limitaciones

- El LLM no es determinista: dos revisiones del mismo contrato pueden diferir en algún "parcial".
  La verificación literal de citas y la aprobación humana mitigan este riesgo.
- PDFs escaneados (solo imagen) no tienen texto extraíble; habría que añadir OCR.
- La numeración de los controles ISO/IEC 27701:2025 está inferida (ver arriba).
