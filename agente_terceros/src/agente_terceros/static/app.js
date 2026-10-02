"use strict";

// ---------------------------------------------------------------- utilidades
const $vista = document.getElementById("vista");

function esc(valor) {
  return String(valor ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[c]);
}

async function api(ruta, opciones = {}) {
  const r = await fetch(ruta, opciones);
  const datos = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(datos.error || `Error ${r.status}`);
  return datos;
}

const postJSON = (ruta, cuerpo) => api(ruta, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(cuerpo),
});

const ETIQUETAS = {
  sin_dpa: "Sin DPA", vigente: "Vigente", por_vencer: "Por vencer", vencido: "Vencido",
  pendiente_aprobacion: "Pendiente de aprobación", rechazado: "Rechazado", pendiente: "Pendiente",
  aprobado: "Aprobado", cumple: "Cumple", parcial: "Parcial", falta: "Falta",
  sin_revision: "Sin revisión", bajo: "Bajo", medio: "Medio", alto: "Alto", "crítico": "Crítico",
};
const chip = (estado) => `<span class="chip ${esc(estado)}">${esc(ETIQUETAS[estado] || estado)}</span>`;

function colorPct(p) {
  if (p >= 85) return "var(--ok)";
  if (p >= 70) return "var(--med)";
  if (p >= 40) return "var(--alto)";
  return "var(--crit)";
}

function medidor(p) {
  const v = Math.max(0, Math.min(100, p ?? 0));
  return `<div class="medidor" role="img" aria-label="${v.toFixed(0)}%"><span style="width:${v}%;background:${colorPct(v)}"></span></div>`;
}

function cargando(msg = "Cargando…") {
  const n = document.getElementById("tpl-cargando").content.cloneNode(true);
  n.querySelector(".msg").textContent = msg;
  return n;
}

function mostrarError(contenedor, e) {
  contenedor.insertAdjacentHTML("afterbegin", `<div class="error">${esc(e.message)}</div>`);
}

async function refrescarBadge() {
  try {
    const pend = await api("/api/aprobaciones");
    const b = document.getElementById("badge-pend");
    b.hidden = pend.length === 0;
    b.textContent = pend.length;
  } catch { /* el badge es accesorio */ }
}

// ---------------------------------------------------------------- vistas
async function vistaPanel() {
  const p = await api("/api/panel");
  const n = p.por_nivel;
  $vista.innerHTML = `
    <h2>Panel del DPO</h2>
    <div class="rejilla">
      <div class="kpi"><div class="num">${p.total_proveedores}</div><div class="eti">Encargados registrados</div></div>
      <div class="kpi"><div class="num" style="color:var(--crit)">${(n["crítico"] || 0) + (n.alto || 0)}</div><div class="eti">Riesgo alto o crítico</div></div>
      <div class="kpi"><div class="num" style="color:var(--crit)">${p.sin_dpa}</div><div class="eti">Sin DPA</div></div>
      <div class="kpi"><div class="num" style="color:var(--med)">${p.alertas.length}</div><div class="eti">DPAs por vencer o vencidos</div></div>
      <div class="kpi"><div class="num">${p.pendientes.length}</div><div class="eti">Decisiones pendientes (HITL)</div></div>
    </div>
    <div class="dos" style="margin-top:18px">
      <section class="tarjeta">
        <h3>Alertas de renovación</h3>
        ${p.alertas.length ? `<ul class="lista-limpia">${p.alertas.map((a) => `
          <li class="fila"><a href="#proveedor/${a.proveedor_id}">${esc(a.proveedor)}</a>
          <span class="espacio"></span>${chip(a.tipo)}
          <span class="muted">${a.dias_restantes < 0 ? `venció hace ${-a.dias_restantes} d` : `vence en ${a.dias_restantes} d`} (${esc(a.fecha_vencimiento)})</span></li>`).join("")}</ul>`
          : `<p class="vacio">Sin DPAs próximos a vencer.</p>`}
      </section>
      <section class="tarjeta">
        <h3>Pendientes de aprobación legal</h3>
        ${p.pendientes.length ? `<ul class="lista-limpia">${p.pendientes.map((a) => `
          <li class="fila">${chip("pendiente")} <span>${esc(a.descripcion)}</span></li>`).join("")}</ul>
          <div class="acciones"><a href="#aprobaciones"><button class="sec">Ir a aprobaciones</button></a></div>`
          : `<p class="vacio">Nada pendiente.</p>`}
      </section>
    </div>
    <section class="tarjeta">
      <h3>Actividad reciente</h3>
      ${tablaHistorial(p.historial)}
    </section>`;
}

function tablaHistorial(h) {
  if (!h.length) return `<p class="vacio">Sin actividad.</p>`;
  return `<div class="tabla-scroll"><table><thead><tr><th>Fecha</th><th>Actor</th><th>Acción</th><th>Detalle</th></tr></thead><tbody>
    ${h.map((x) => `<tr><td class="mono">${esc(x.ts.replace("T", " "))}</td><td>${esc(x.actor)}</td><td><code>${esc(x.accion)}</code></td><td>${esc(x.detalle)}</td></tr>`).join("")}
  </tbody></table></div>`;
}

async function vistaProveedores() {
  const lista = await api("/api/proveedores");
  $vista.innerHTML = `
    <div class="fila"><h2>Encargados y terceros</h2><span class="espacio"></span>
      <button id="btn-nuevo">+ Registrar proveedor</button></div>
    <section class="tarjeta" id="form-nuevo" hidden>${formProveedor()}</section>
    <section class="tarjeta tabla-scroll">
      ${lista.length ? `<table><thead><tr><th>Proveedor</th><th>Servicio</th><th>País</th><th>DPA</th><th>Cumplimiento</th><th>Riesgo</th></tr></thead><tbody>
        ${lista.map((p) => `<tr class="click" data-id="${p.id}">
          <td><strong>${esc(p.nombre)}</strong>${p.datos_sensibles ? ` <span class="chip gris">datos sensibles</span>` : ""}</td>
          <td>${esc(p.servicio)}</td><td>${esc(p.pais)}</td>
          <td>${chip(p.dpa.estado)}</td>
          <td style="min-width:120px">${p.dpa.cumplimiento == null ? `<span class="muted">—</span>` : `${p.dpa.cumplimiento.toFixed(0)}% ${medidor(p.dpa.cumplimiento)}`}</td>
          <td>${chip(p.riesgo.nivel)} <span class="muted">${p.riesgo.probabilidad}×${p.riesgo.impacto}</span></td></tr>`).join("")}
      </tbody></table>` : `<p class="vacio">Aún no hay proveedores. Registra uno o ejecuta <code>agente-terceros demo</code>.</p>`}
    </section>`;
  $vista.querySelectorAll("tr.click").forEach((tr) => tr.addEventListener("click", () => { location.hash = `proveedor/${tr.dataset.id}`; }));
  const form = document.getElementById("form-nuevo");
  document.getElementById("btn-nuevo").addEventListener("click", () => { form.hidden = !form.hidden; });
  form.querySelector("form").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const f = new FormData(ev.target);
    const lista = (k) => String(f.get(k) || "").split(",").map((s) => s.trim()).filter(Boolean);
    try {
      const { id } = await postJSON("/api/proveedores", {
        nombre: f.get("nombre"), ruc: f.get("ruc"), pais: f.get("pais"), servicio: f.get("servicio"),
        contacto: f.get("contacto"), categorias_datos: lista("categorias_datos"), sistemas: lista("sistemas"),
        certificaciones: lista("certificaciones"), volumen: f.get("volumen"),
        incidentes_12m: Number(f.get("incidentes_12m") || 0), datos_sensibles: f.has("datos_sensibles"),
        transferencia_internacional: f.has("transferencia_internacional"), pais_adecuado: f.has("pais_adecuado"),
      });
      location.hash = `proveedor/${id}`;
    } catch (e) { mostrarError(form, e); }
  });
}

function formProveedor() {
  return `<form>
    <h3>Nuevo encargado del tratamiento</h3>
    <div class="campos">
      <label>Razón social *<input name="nombre" required></label>
      <label>RUC<input name="ruc" inputmode="numeric"></label>
      <label>País<input name="pais" value="Perú"></label>
      <label>Servicio prestado<input name="servicio"></label>
      <label>Contacto (DPO)<input name="contacto" type="email"></label>
      <label>Categorías de datos (coma)<input name="categorias_datos" placeholder="identificación, salud"></label>
      <label>Sistemas afectados (coma)<input name="sistemas" placeholder="ERP, CRM"></label>
      <label>Certificaciones (coma)<input name="certificaciones" placeholder="ISO 27001, ISO 27701"></label>
      <label>Volumen de titulares<select name="volumen">
        <option value="bajo">Bajo (&lt; 1 000)</option><option value="medio">Medio (&lt; 100 000)</option><option value="alto">Alto (≥ 100 000)</option></select></label>
      <label>Incidentes en 12 meses<input name="incidentes_12m" type="number" min="0" value="0"></label>
    </div>
    <div class="fila" style="margin-top:10px">
      <label class="check"><input type="checkbox" name="datos_sensibles"> Trata datos sensibles</label>
      <label class="check"><input type="checkbox" name="transferencia_internacional"> Transferencia internacional</label>
      <label class="check"><input type="checkbox" name="pais_adecuado" checked> País destino con nivel adecuado</label>
    </div>
    <div class="acciones"><button type="submit">Guardar</button></div>
  </form>`;
}

async function vistaProveedor(id) {
  const p = await api(`/api/proveedores/${id}`);
  const r = p.riesgo;
  const ultimo = p.dpas[0];
  $vista.innerHTML = `
    <p><a href="#proveedores">← Proveedores</a></p>
    <div class="fila"><h2>${esc(p.nombre)}</h2>${chip(r.nivel)}</div>
    <p class="muted">${esc(p.servicio)} · ${esc(p.pais)} · RUC ${esc(p.ruc || "—")} · ${esc(p.contacto || "")}</p>
    <div class="dos">
      <section class="tarjeta">
        <h3>Riesgo del proveedor <span class="muted">(evaluate_vendor)</span></h3>
        <p><span class="porcentaje">${r.puntaje}</span> <span class="muted">/ 16 · probabilidad ${r.probabilidad} × impacto ${r.impacto} · revisar cada ${r.revision_meses} meses</span></p>
        <ul>${r.factores.map((f) => `<li>${esc(f)}</li>`).join("")}</ul>
        ${r.recomendaciones.length ? `<h3>Recomendaciones</h3><ul>${r.recomendaciones.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>` : ""}
      </section>
      <section class="tarjeta">
        <h3>Contrato de encargo <span class="muted">(check_dpa_status)</span></h3>
        <p>${chip(p.dpa.estado)} ${p.dpa.fecha_vencimiento ? `<span class="muted">vence ${esc(p.dpa.fecha_vencimiento)}${p.dpa.dias_restantes != null ? ` (${p.dpa.dias_restantes} d)` : ""}</span>` : ""}</p>
        ${p.dpa.cumplimiento != null ? `<p><strong>${p.dpa.cumplimiento.toFixed(1)}%</strong> de cláusulas mínimas</p>${medidor(p.dpa.cumplimiento)}` : ""}
        <p class="muted" style="margin-top:12px">Categorías: ${esc(p.categorias_datos.join(", ") || "—")}<br>Sistemas: ${esc(p.sistemas.join(", ") || "—")}<br>Certificaciones: ${esc(p.certificaciones.join(", ") || "ninguna")}</p>
        <div class="acciones"><a href="#revisar/${p.id}"><button>Revisar un DPA</button></a></div>
      </section>
    </div>
    <section class="tarjeta">
      <h3>Subencargados <span class="muted">(A.2.5.7 · A.2.5.8 · A.2.5.9)</span></h3>
      ${p.subencargados.length ? `<table><thead><tr><th>Nombre</th><th>País</th><th>Servicio</th><th>Estado</th></tr></thead><tbody>
        ${p.subencargados.map((s) => `<tr><td>${esc(s.nombre)}</td><td>${esc(s.pais)}</td><td>${esc(s.servicio)}</td><td>${chip(s.estado)}</td></tr>`).join("")}</tbody></table>`
        : `<p class="vacio">No declara subencargados.</p>`}
      <form id="form-sub" class="campos" style="margin-top:12px">
        <label>Nuevo subencargado<input name="nombre" required></label>
        <label>País<input name="pais"></label>
        <label>Servicio<input name="servicio"></label>
        <label>&nbsp;<button type="submit" class="sec">Notificar cambio</button></label>
      </form>
      <p class="muted">El cambio queda pendiente hasta que Legal lo apruebe (el responsable puede oponerse).</p>
    </section>
    <section class="tarjeta">
      <h3>Historial de DPAs</h3>
      ${p.dpas.length ? `<table><thead><tr><th>Archivo</th><th>Firma</th><th>Vence</th><th>Cumplimiento</th><th>Estado</th></tr></thead><tbody>
        ${p.dpas.map((d) => `<tr><td>${esc(d.archivo)}</td><td>${esc(d.fecha_firma)}</td><td>${esc(d.fecha_vencimiento)}</td><td>${d.cumplimiento == null ? "—" : d.cumplimiento.toFixed(1) + "%"}</td><td>${chip(d.estado)}</td></tr>`).join("")}</tbody></table>`
        : `<p class="vacio">Sin contratos registrados.</p>`}
      ${ultimo && ultimo.revision.resultados && ultimo.revision.resultados.length ? `<details style="margin-top:12px"><summary>Ver última revisión del agente</summary>${informeRevision(ultimo.revision)}</details>` : ""}
    </section>`;
  document.getElementById("form-sub").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const f = new FormData(ev.target);
    try {
      await postJSON(`/api/proveedores/${id}/subencargados`, Object.fromEntries(f));
      await vistaProveedor(id);
      refrescarBadge();
    } catch (e) { mostrarError(ev.target.parentElement, e); }
  });
}

function informeRevision(rev) {
  const orden = { falta: 0, parcial: 1, cumple: 2 };
  const items = [...rev.resultados].sort((a, b) => orden[a.estado] - orden[b.estado] || b.peso - a.peso);
  const cuenta = (e) => rev.resultados.filter((r) => r.estado === e).length;
  return `
    <div class="fila" style="margin:12px 0">
      <span class="porcentaje" style="color:${colorPct(rev.cumplimiento)}">${rev.cumplimiento.toFixed(1)}%</span>
      <div class="espacio">${medidor(rev.cumplimiento)}
        <p class="muted">${cuenta("cumple")} cumplen · ${cuenta("parcial")} parciales · ${cuenta("falta")} faltan (ponderado por criticidad)</p></div>
    </div>
    ${rev.resumen ? `<p>${esc(rev.resumen)}</p>` : ""}
    ${items.map((r) => `
      <div class="clausula">
        <div class="cab"><strong>${esc(r.titulo)}</strong>${chip(r.estado)}</div>
        <div class="refs">RGPD ${esc(r.rgpd)} · ${esc(r.peru)} · ISO/IEC 27701 ${esc(r.iso.join(", "))} · peso ${r.peso}</div>
        ${r.evidencia ? `<blockquote>${esc(r.evidencia)}</blockquote>${r.evidencia_verificada ? "" : `<div class="aviso">⚠ La cita no aparece literal en el contrato: verificar manualmente.</div>`}` : ""}
        ${r.recomendacion ? `<p><strong>Recomendación:</strong> ${esc(r.recomendacion)}</p>` : ""}
        ${r.fundamento.length ? `<details><summary>Fundamento normativo (${r.fundamento.map((n) => esc(rev.fuentes[n]?.etiqueta || n)).join(" · ")})</summary>
          ${r.fundamento.map((n) => rev.fuentes[n] ? `<div class="fuente"><strong>[${n}] ${esc(rev.fuentes[n].etiqueta)}</strong> — ${esc(rev.fuentes[n].titulo)}<br>${esc(rev.fuentes[n].texto)}</div>` : "").join("")}
        </details>` : ""}
      </div>`).join("")}`;
}

async function vistaRevisar(idPreseleccionado) {
  const lista = await api("/api/proveedores");
  const hoy = new Date().toISOString().slice(0, 10);
  const enUnAnio = new Date(Date.now() + 365 * 864e5).toISOString().slice(0, 10);
  $vista.innerHTML = `
    <h2>Revisar contrato de encargo (DPA)</h2>
    <p class="muted">El agente contrasta el contrato con 13 cláusulas mínimas (RGPD art. 28.3, LPDP art. 30, RLPDP arts. 29-33 y 36, ISO/IEC 27701 A.1.2.7 y A.2) usando RAG sobre FAISS. El resultado queda <strong>pendiente de aprobación legal</strong>.</p>
    <section class="tarjeta">
      ${lista.length ? `<form id="form-dpa">
        <div class="campos">
          <label>Proveedor<select name="proveedor">${lista.map((p) => `<option value="${p.id}" ${String(p.id) === String(idPreseleccionado) ? "selected" : ""}>${esc(p.nombre)}</option>`).join("")}</select></label>
          <label>Contrato (PDF o TXT)<input type="file" name="archivo" accept=".pdf,.txt" required></label>
          <label>Fecha de firma<input type="date" name="fecha_firma" value="${hoy}" required></label>
          <label>Fecha de vencimiento<input type="date" name="fecha_vencimiento" value="${enUnAnio}" required></label>
        </div>
        <div class="acciones"><button type="submit">Analizar con el agente</button></div>
      </form>` : `<p class="vacio">Registra primero un proveedor.</p>`}
    </section>
    <section id="resultado"></section>`;
  const form = document.getElementById("form-dpa");
  if (!form) return;
  form.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const f = new FormData(form);
    const res = document.getElementById("resultado");
    const btn = form.querySelector("button");
    btn.disabled = true;
    res.replaceChildren(cargando("Recuperando normativa y analizando cláusulas… (20-60 s)"));
    try {
      const d = await api(`/api/proveedores/${f.get("proveedor")}/dpa`, { method: "POST", body: f });
      res.innerHTML = `<div class="tarjeta"><div class="fila"><h3>Informe de revisión</h3><span class="espacio"></span>${chip("pendiente_aprobacion")}</div>${informeRevision(d.revision)}
        <div class="acciones"><a href="#aprobaciones"><button>Enviar a aprobación legal</button></a><a href="#proveedor/${f.get("proveedor")}"><button class="sec">Ver proveedor</button></a></div></div>`;
      refrescarBadge();
    } catch (e) { res.innerHTML = ""; mostrarError(res, e); }
    btn.disabled = false;
  });
}

async function vistaAprobaciones() {
  const pend = await api("/api/aprobaciones");
  $vista.innerHTML = `
    <h2>Aprobaciones (human-in-the-loop)</h2>
    <p class="muted">Ningún DPA nuevo ni cambio de subencargado surte efecto sin la decisión de Asesoría Legal / DPO. Cada decisión queda en la bitácora.</p>
    ${pend.length ? pend.map((a) => `
      <section class="tarjeta" data-id="${a.id}">
        <div class="fila"><strong>${esc(a.descripcion)}</strong><span class="espacio"></span>${chip("pendiente")}</div>
        <p class="muted">Tipo: ${esc(a.tipo)} · solicitado ${esc(a.solicitado.replace("T", " "))} · <a href="#proveedor/${a.proveedor_id}">ver proveedor</a></p>
        <div class="campos" style="display:grid;grid-template-columns:1fr 2fr;gap:12px">
          <label>Revisor<input name="revisor" value="Asesoría Legal"></label>
          <label>Comentario<input name="comentario" placeholder="Motivo de la decisión"></label>
        </div>
        <div class="acciones"><button class="ok" data-ok="1">Aprobar</button><button class="mal" data-ok="0">Rechazar</button></div>
      </section>`).join("") : `<section class="tarjeta"><p class="vacio">No hay decisiones pendientes.</p></section>`}`;
  $vista.querySelectorAll("section[data-id] button").forEach((b) => b.addEventListener("click", async () => {
    const s = b.closest("section");
    try {
      await postJSON(`/api/aprobaciones/${s.dataset.id}`, {
        aprobado: b.dataset.ok === "1",
        revisor: s.querySelector("[name=revisor]").value,
        comentario: s.querySelector("[name=comentario]").value,
      });
      await vistaAprobaciones();
      refrescarBadge();
    } catch (e) { mostrarError(s, e); }
  }));
}

async function vistaBrecha() {
  $vista.innerHTML = `
    <h2>Brecha de seguridad: encargados implicados</h2>
    <p class="muted">Apoyo al Agente de Incidentes: dada una categoría de datos o un sistema afectado, identifica qué encargados lo tratan y si su DPA les obliga a notificar.</p>
    <section class="tarjeta"><form id="form-brecha" class="fila">
      <label style="flex:1">Categoría de datos o sistema<input name="termino" placeholder="salud, ERP, económicos…" required></label>
      <label>&nbsp;<button type="submit">Buscar</button></label>
    </form></section>
    <section id="res-brecha"></section>`;
  document.getElementById("form-brecha").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const res = document.getElementById("res-brecha");
    res.replaceChildren(cargando());
    try {
      const t = new FormData(ev.target).get("termino");
      const lista = await api(`/api/brecha?termino=${encodeURIComponent(t)}`);
      res.innerHTML = lista.length ? lista.map((p) => `
        <div class="tarjeta">
          <div class="fila"><a href="#proveedor/${p.id}"><strong>${esc(p.nombre)}</strong></a><span class="espacio"></span>DPA ${chip(p.dpa.estado)} Cláusula de notificación ${chip(p.clausula_notificacion)}</div>
          <p class="muted">Contacto: ${esc(p.contacto || "—")} · Datos: ${esc(p.categorias_datos.join(", "))} · Sistemas: ${esc(p.sistemas.join(", "))}</p>
          ${p.evidencia ? `<blockquote>${esc(p.evidencia)}</blockquote>` : ""}
          ${p.subencargados.length ? `<p class="muted">Subencargados autorizados: ${p.subencargados.map((s) => esc(`${s.nombre} (${s.pais})`)).join(", ")}</p>` : ""}
          ${p.clausula_notificacion !== "cumple" ? `<p class="aviso">⚠ El contrato no garantiza la notificación oportuna: contactar al encargado de inmediato y documentarlo (RLPDP art. 36).</p>` : ""}
        </div>`).join("") : `<div class="tarjeta"><p class="vacio">Ningún encargado registrado trata “${esc(t)}”.</p></div>`;
    } catch (e) { res.innerHTML = ""; mostrarError(res, e); }
  });
}

async function vistaConsulta() {
  $vista.innerHTML = `
    <h2>Consulta normativa</h2>
    <p class="muted">RAG sobre LPDP, RLPDP, RGPD, Directrices 07/2020 del CEPD y cláusulas tipo de la Decisión (UE) 2021/915. Las respuestas citan fuente, artículo y página.</p>
    <section class="tarjeta"><form id="form-consulta">
      <label>Pregunta<textarea name="pregunta" required placeholder="¿Puede el encargado subcontratar sin autorización del responsable?"></textarea></label>
      <div class="fila" style="margin-top:10px">
        <label>Jurisdicción<select name="jurisdiccion"><option value="">Todas</option><option>Perú</option><option>Unión Europea</option></select></label>
        <span class="espacio"></span><button type="submit">Consultar</button>
      </div>
      <div class="fila muted" style="margin-top:8px">Ejemplos:
        ${["¿Qué debe contener un contrato de encargo?", "¿En qué plazo debe el encargado notificar un incidente en el Perú?", "¿Cuánto tiempo puede conservar los datos el encargado al terminar el servicio?"]
          .map((q) => `<a href="#" class="ej">${esc(q)}</a>`).join(" · ")}
      </div>
    </form></section>
    <section id="res-consulta"></section>`;
  const form = document.getElementById("form-consulta");
  form.querySelectorAll("a.ej").forEach((a) => a.addEventListener("click", (ev) => {
    ev.preventDefault();
    form.pregunta.value = a.textContent;
  }));
  form.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const res = document.getElementById("res-consulta");
    const btn = form.querySelector("button");
    btn.disabled = true;
    res.replaceChildren(cargando("Recuperando fragmentos y generando respuesta…"));
    try {
      const d = await postJSON("/api/consulta", { pregunta: form.pregunta.value, jurisdiccion: form.jurisdiccion.value });
      res.innerHTML = `<div class="tarjeta"><h3>Respuesta</h3><div class="respuesta">${esc(d.respuesta)}</div></div>
        <div class="tarjeta"><h3>Fragmentos recuperados</h3>${d.fuentes.map((f) => `
          <details><summary>[${f.n}] ${esc(f.etiqueta)} — ${esc(f.titulo)}</summary><div class="fuente">${esc(f.texto)}</div></details>`).join("")}</div>`;
    } catch (e) { res.innerHTML = ""; mostrarError(res, e); }
    btn.disabled = false;
  });
}

async function vistaBitacora() {
  const h = await api("/api/historial");
  $vista.innerHTML = `<h2>Bitácora de auditoría</h2>
    <p class="muted">Registro de cada acción del agente y de cada decisión humana (trazabilidad, cláusula 9 de ISO/IEC 27701).</p>
    <section class="tarjeta">${tablaHistorial(h)}</section>`;
}

// ---------------------------------------------------------------- router
const RUTAS = {
  panel: vistaPanel, proveedores: vistaProveedores, proveedor: vistaProveedor, revisar: vistaRevisar,
  aprobaciones: vistaAprobaciones, brecha: vistaBrecha, consulta: vistaConsulta, bitacora: vistaBitacora,
};

async function navegar() {
  const [ruta, arg] = (location.hash.slice(1) || "panel").split("/");
  const vista = RUTAS[ruta] || vistaPanel;
  const seccion = ruta === "proveedor" ? "proveedores" : ruta;
  document.querySelectorAll("#nav a").forEach((a) => a.classList.toggle("activo", a.getAttribute("href") === `#${seccion}`));
  $vista.replaceChildren(cargando());
  try {
    await vista(arg);
  } catch (e) {
    $vista.innerHTML = "";
    mostrarError($vista, e);
  }
  window.scrollTo(0, 0);
}

window.addEventListener("hashchange", navegar);
navegar();
refrescarBadge();
