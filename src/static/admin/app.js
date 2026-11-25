const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
const TOKEN_KEY = "kardex_admin_token";
const THEME_KEY = "kardex_admin_theme";
const ROLE_LABEL = { admin: "Administrador operativo", jefe: "Jefe de empresa", soporte: "Soporte técnico" };
const PAGES = {
  dashboard: ["▦", "Resumen"],
  harvests: ["♧", "Cosechas"],
  lots: ["▤", "Lotes"],
  movements: ["⇄", "Kardex"],
  products: ["◫", "Productos y unidades"],
  finance: ["▥", "Ventas y costos"],
  journal: ["▤", "Bitácora por parcela"],
  farms: ["⌂", "Fincas y parcelas"],
  workers: ["♙", "Cosecheros"],
  clients: ["◈", "Afiliaciones"],
  users: ["◍", "Cuentas"]
};
const NAV = {
  admin: ["dashboard", "harvests", "journal", "lots", "movements", "products", "finance", "farms", "workers", "clients", "users"],
};

let session;
let token;
let currentPage = "dashboard";
let cache = {};
let filtros = {};
let scopeTables = false;
let scopeLot = null;
let scopeProduct = null;
let detailProduct = null;
let requestId = 0;

const fmt = (value, digits = 3) => Number(value || 0).toLocaleString("es-BO", { maximumFractionDigits: digits });
const safe = (value) => String(value ?? "").replace(/[&<>"']/g, (c) => ({
  "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
}[c]));
const fechaActual = () => new Intl.DateTimeFormat("en-CA", {
  timeZone: "America/La_Paz", year: "numeric", month: "2-digit", day: "2-digit"
}).format(new Date());
const admin = () => session?.rol === "admin";

function toast(message, error = false) {
  const node = $("#toast");
  node.textContent = message;
  node.className = "toast show" + (error ? " error" : "");
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => { node.className = "toast"; }, 4300);
}

async function fetchAuth(path, options = {}) {
  const headers = { ...options.headers };
  if (options.body) headers["Content-Type"] = "application/json";
  if (token) headers.Authorization = "Bearer " + token;
  const response = await fetch(path, { ...options, headers });
  if (response.ok) return response;
  if (response.status === 401 && token) logout();
  const body = await response.json().catch(() => ({}));
  throw new Error(typeof body.detail === "string" ? body.detail :
    body.detail?.[0]?.msg || `La operación devolvió el error ${response.status}.`);
}

async function api(path, options) {
  const response = await fetchAuth(path, options);
  return response.status === 204 ? null : response.json();
}

function applyTheme(theme) {
  document.documentElement.dataset.theme = theme;
  localStorage.setItem(THEME_KEY, theme);
}

function showLogin() {
  $("#auth-screen").classList.remove("hidden");
  $("#app-shell").classList.add("hidden");
}

function logout() {
  requestId++;
  session = null;
  token = null;
  cache = {};
  filtros = {};
  scopeTables = false;
  scopeLot = null;
  scopeProduct = null;
  detailProduct = null;
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem("kardex_admin_user");
  showLogin();
}

async function actualizarAviso() {
  const aviso = $("#aviso-solicitudes");
  aviso.hidden = true;
  if (session?.rol !== "admin") return;
  try {
    const solicitudes = await api("/auth/solicitudes");
    if (session?.rol !== "admin") return;
    aviso.textContent = `Solicitudes pendientes (${solicitudes.length})`;
    aviso.hidden = !solicitudes.length;
  } catch { aviso.hidden = true; }
}
setInterval(() => { if (!document.hidden && session?.rol === "admin") actualizarAviso(); }, 30000);

function showApp() {
  $("#auth-screen").classList.add("hidden");
  $("#app-shell").classList.remove("hidden");
  $("#side-user").textContent = session.nombre_completo;
  $("#side-role").textContent = ROLE_LABEL[session.rol];
  $("#user-avatar").textContent = session.nombre_completo.charAt(0).toUpperCase();
  $("#today-label").textContent = new Intl.DateTimeFormat("es-BO", { dateStyle: "full" }).format(new Date());
  navigate(window.location.hash.slice(1) || "dashboard");
}

function params(values) {
  return new URLSearchParams(Object.entries(values).filter(([, value]) => value !== "" && value != null)).toString();
}

const dataPath = {
  bitacora: "/bitacora",
  fincas: "/inventario/fincas", parcelas: "/inventario/parcelas", cosecheros: "/cosecheros",
  lotes: "/inventario/lotes", cosechas: "/kardex/cosechas", movimientos: "/kardex/movimientos",
  solicitudes: "/auth/solicitudes", clientes: "/portal/api/admin/clientes", cuentas: "/auth/usuarios", diagnostico: "/reportes/diagnostico",
  resultados: "/finanzas/lotes", finanzas: "/finanzas", productos: "/inventario/productos"
};

function dependencies(page) {
  switch (page) {
    case "dashboard": return session.rol === "soporte" ? ["diagnostico"] : ["fincas"];
    case "harvests": return admin() ? ["fincas", "parcelas", "cosecheros", "cosechas", "lotes", "productos"] : ["fincas", "cosechas", "lotes", "productos"];
    case "lots": return ["fincas", "lotes", "productos"];
    case "movements": return ["fincas", "lotes", "movimientos", "productos"];
    case "products": return ["productos"];
    case "finance": return ["fincas", "finanzas", "lotes"];
    case "journal": return ["bitacora", "parcelas", "fincas", "cosechas"];
    case "farms": return ["fincas", "parcelas"];
    case "workers": return ["cosecheros"];
    case "clients": return ["fincas", "clientes", "solicitudes"];
    case "users": return ["cuentas"];
    default: return [];
  }
}

async function navigate(page) {
  if (!session) return;
  if (!NAV[session.rol].includes(page)) page = "dashboard";
  currentPage = page;
  actualizarAviso();
  const id = ++requestId;
  history.replaceState(null, "", "#" + page);
  $("#sidebar").classList.remove("open");
  $("#page-crumb").textContent = page === "dashboard" && session.rol === "soporte" ? "Diagnóstico" : PAGES[page][1];
  $("#side-nav").innerHTML = NAV[session.rol].map((key) => {
    const [icon, label] = PAGES[key];
    return `<button class="nav-item ${page === key ? "active" : ""}" type="button" data-page="${key}" ${page === key ? 'aria-current="page"' : ""}><span class="nav-ico" aria-hidden="true">${icon}</span>${key === "dashboard" && session.rol === "soporte" ? "Diagnóstico" : label}</button>`;
  }).join("");
  $("#page-content").innerHTML = '<p class="loading" role="status">Cargando información…</p>';
  try {
    const pairs = await Promise.all(dependencies(page).map(async (key) => {
      let path = dataPath[key];
      if (key === "resultados" && scopeTables) path += "?" + params({ hasta: filtros.fecha_hasta, finca_id: filtros.finca_id });
      if (key === "movimientos") {
        const consulta = params({ finca_id: scopeTables ? filtros.finca_id : null, lote_id: scopeLot, producto_id: scopeProduct });
        if (consulta) path += "?" + consulta;
      }
      return [key, await api(path)];
    }));
    if (id !== requestId) return;
    cache = Object.fromEntries(pairs);
    if (page === "dashboard" && session.rol !== "soporte") {
      cache.resumen = await api("/reportes/resumen?" + params(filtros));
      if (id !== requestId) return;
      filtros = { ...filtros, fecha_desde: cache.resumen.desde, fecha_hasta: cache.resumen.hasta };
    }
    $("#page-content").innerHTML = views[page]();
    if (page === "journal") bindJournal($("#journal-form"));
    if (page === "harvests" && admin()) bindHarvest($("#harvest-form"));
    if (page === "movements" && admin()) bindMovement($("#movement-form"));
  } catch (error) {
    if (id !== requestId) return;
    $("#page-content").innerHTML = `<div class="panel"><p role="alert">${safe(error.message)}</p><button class="btn btn-soft" type="button" data-page="${page}">Reintentar</button></div>`;
  }
}

function head(title, detail, action = "") {
  return `<div class="page-head"><div><h1>${title}</h1><p>${detail}</p></div>${action}</div>`;
}

function panel(title, content, action = "") {
  return `<section class="panel"><div class="panel-head"><h3>${title}</h3>${action}</div>${content}</section>`;
}

function table(headers, rows) {
  return `<div class="table-wrap"><table><thead><tr>${headers.map((name) => `<th scope="col">${name}</th>`).join("")}</tr></thead><tbody>${rows.length ? rows.map((cells) => "<tr>" + cells.map((value) => `<td>${value}</td>`).join("") + "</tr>").join("") : `<tr><td class="empty" colspan="${headers.length}">Sin registros para esta consulta.</td></tr>`}</tbody></table></div>`;
}

function excel(tabla) {
  return `<button class="btn btn-excel" type="button" data-export="${tabla}">↓ Descargar Excel</button>`;
}

function button(label, attrs, kind = "soft") {
  return `<button class="btn btn-${kind}" type="button" ${attrs}>${label}</button>`;
}

function field(label, control) {
  return `<label class="field">${label}${control}</label>`;
}

function input(name, options = "", value = "") {
  return `<input name="${name}" value="${safe(value)}" ${options}>`;
}

function selector(name, items, placeholder, selected = "", required = false) {
  return `<select name="${name}" ${required ? "required" : ""}><option value="">${placeholder}</option>${items.map(([id, label]) => `<option value="${safe(id)}" ${String(id) === String(selected) ? "selected" : ""}>${safe(label)}</option>`).join("")}</select>`;
}

function form(id, fields, label, extra = "") {
  return `<form id="${id}" ${extra}><div class="form-grid">${fields.join("")}</div><div class="form-actions"><button class="btn btn-primary" type="submit">${label}</button></div></form>`;
}

const fincaNombre = (id) => {
  const finca = cache.fincas?.find((f) => f.id === id);
  return finca ? finca.nombre || `Finca ${finca.numero}` : "Sin finca atribuida";
};
const fincaItems = (onlyActive = false) => (cache.fincas || []).filter((f) => !onlyActive || f.activo).map((f) => [f.id, fincaNombre(f.id)]);
const loteCodigo = (id) => cache.lotes?.find((l) => l.id === id)?.codigo || "—";
const pill = (label, tone = "") => `<span class="pill ${tone}">${label}</span>`;

function chart(semanas, unidad) {
  if (!semanas.length) return '<p class="empty">No hay entradas o salidas en el período seleccionado.</p>';
  const maximo = Math.max(1, ...semanas.flatMap((row) => [Number(row.entrada), Number(row.salida)]));
  const rows = semanas.map((row) => {
    const fecha = new Date(row.fecha + "T12:00:00").toLocaleDateString("es-BO", { day: "numeric", month: "short" });
    const barra = (tipo, valor) => `<div class="chart-series"><div class="chart-track"><span class="chart-fill ${tipo}" style="--fill:${Math.max(0, Math.min(100, Number(valor) / maximo * 100))}%"></span></div><span class="chart-value">${acopio.cantidad(valor, unidad)}</span></div>`;
    return `<div class="chart-week"><span>${safe(fecha)}</span><div>${barra("in", row.entrada)}${barra("out", row.salida)}</div></div>`;
  }).join("");
  return `<div class="chart-legend"><span class="chart-key in"></span> Entradas <span class="chart-key out"></span> Salidas</div><div class="chart-weeks">${rows}</div>`;
}

function dashboard() {
  const r = cache.resumen;
  const titulo = "Control de cosecha y almacén";
  return `<section class="harvest-hero"><div><h1>${titulo}</h1><p>Recepciones, despachos y existencias de cada producto del acopio.</p></div></section>
    <form class="period-form panel" id="period-form">
      ${field("Desde", input("fecha_desde", 'type="date" required', r.desde))}
      ${field("Hasta", input("fecha_hasta", 'type="date" required', r.hasta))}
      ${field("Finca", selector("finca_id", fincaItems(), "Todas las fincas", filtros.finca_id))}
      <button class="btn btn-primary" type="submit">Aplicar filtros</button>
    </form>
    <div class="cierre-bar"><h2>Existencias por producto</h2><div>${button("Cierre de hoy", "data-cierre-hoy")} ${excel("existencias")}</div></div>
    <div id="detalle-existencias">${existenciasVista(r.existencias)}</div>
`;
}

function existenciasVista(productos) {
  if (!productos.length) return panel("Saldo al cierre", '<p class="empty">Todavía no hay recepciones o movimientos para este corte.</p>');
  const activo = productos.find((p) => (p.producto_id ?? 0) === detailProduct) || productos[0];
  detailProduct = activo.producto_id ?? 0;
  const tonos = ["teal", "blue", "terra", "violet"];
  const tarjetas = productos.map((p, i) => {
    const id = p.producto_id ?? 0;
    return `<button class="stat-card metric ${tonos[i % tonos.length]} product-card" type="button" data-detail-product="${id}" aria-pressed="${id === detailProduct}">
      <span class="stat-top">${safe(p.producto)}</span><strong class="stat-value">${acopio.cantidad(p.saldo, p.unidad)}</strong>
      <span class="stat-note">Saldo al cierre</span></button>`;
  }).join("");
  const valores = [["Saldo inicial", activo.apertura], ["Llegó", activo.recibida], ["Rechazado", activo.rechazada],
    ["Entradas al Kardex", activo.entrada], ["Salidas, incluidas mermas", activo.salida], ["Merma neta", activo.merma]];
  const resumen = valores.map(([nombre, valor]) => `<div><dt>${nombre}</dt><dd>${acopio.cantidad(valor, activo.unidad)}</dd></div>`).join("");
  return `<div class="cards kpi-grid product-grid">${tarjetas}</div><div class="overview-grid">
    ${panel("Detalle de " + safe(activo.producto), `<dl class="finance-totals">${resumen}</dl>`,
      button("Ver Kardex", `data-kardex-product="${detailProduct}"`))}
    ${panel("Entradas y salidas por semana", chart(activo.semanas, activo.unidad))}
  </div>`;
}

function scopeParams() {
  if (!scopeTables) return {};
  if (scopeTables === "balance") return { finca_id: filtros.finca_id, fecha_hasta: filtros.fecha_hasta };
  return filtros;
}

function periodoVisible(rows, dateKey) {
  if (scopeProduct !== null && ["harvests", "lots", "movements"].includes(currentPage)) {
    rows = rows.filter((row) => (row.producto_id ?? 0) === scopeProduct);
  }
  if (!scopeTables) return rows;
  const { finca_id: finca, fecha_desde: desde, fecha_hasta: hasta } = scopeParams();
  return rows.filter((row) => {
    const fecha = dateKey === "recepcion" ? row.fecha_recepcion || row.fecha : row[dateKey];
    return (!finca || Number(finca) === row.finca_id) &&
      (!dateKey || ((!desde || fecha >= desde) && (!hasta || fecha <= hasta)));
  });
}

function bannerPeriodo() {
  if (!scopeTables) return "";
  const { finca_id: finca, fecha_desde: desde, fecha_hasta: hasta } = scopeParams();
  return `<div class="scope-banner"><span>${desde ? safe(desde) + " a " : "Hasta "}${safe(hasta)} · ${finca ? safe(fincaNombre(Number(finca))) : "Todas las fincas"}</span>${button("Ver todos los registros", 'data-clear-scope')}</div>`;
}

function cosechaFields(row = {}) {
  return [
    field("Fecha", input("fecha", 'type="date" required', row.fecha || fechaActual())),
    field("Cosechero", selector("cosechero_id", cache.cosecheros.filter((u) => u.activo).map((u) => [u.id, u.nombre]), "Elegir cosechero", row.cosechero_id, true)),
    field("Finca", selector("finca_id", fincaItems(true), "Elegir finca", row.finca_id, true)),
    field("Parcela", selector("parcela_id", [], "Sin parcela", row.parcela_id)),
    field("Producto", selector("producto_id", cache.productos.map((p) => [p.id, p.nombre + " · " + acopio.etiqueta(p.unidad)]),
      "Elegir producto", row.producto_id, true)),
    field('<span class="cantidad-label">Cantidad estimada</span>', input("cantidad", 'type="number" min="0.001" step="0.001" required', row.cantidad)),
    field("Monto estimado (Bs)", input("monto_bs", 'type="number" min="0" step="0.01" required', row.monto_bs ?? 0)),
    field("Observación", input("observacion", 'maxlength="200"', row.observacion))
  ];
}

function harvests() {
  const cosechas = scopeTables ? cache.cosechas.filter((c) => !c.borrador) : cache.cosechas;
  const rows = periodoVisible(cosechas, "recepcion").slice().reverse().map((c) => {
    const estado = c.borrador ? pill("Pendiente de recepción", "orange") :
      c.lote_id ? pill("Lote " + safe(loteCodigo(c.lote_id))) : pill("Histórico", "gray");
    const ticket = c.recibida == null ? "—" : button("Comprobante", `data-receipt="${c.id}"`);
    const acciones = admin() && c.borrador ? `<div class="table-actions">${button("Recibir", `data-receive="${c.id}"`, "primary")}${button("Editar", `data-edit-harvest="${c.id}"`)}${button("Eliminar", `data-delete-harvest="${c.id}"`, "danger")}</div>` : ticket;
    return ["#" + c.id, safe(c.fecha_recepcion || c.fecha), safe(fincaNombre(c.finca_id)), safe(c.producto),
      acopio.cantidad(c.cantidad, c.unidad), acopio.cantidad(c.rechazada, c.unidad), "Bs " + fmt(c.monto_bs, 2), estado, acciones];
  });
  const headers = ["Cosecha", "Fecha", "Finca", "Producto", "Cantidad registrada", "Rechazada", "Monto registrado", "Recepción", "Acciones"];
  return head("Cosechas y recepciones", "Registra el origen del producto y confirma cuánto ingresa al acopio.", excel("cosechas")) +
    (admin() ? panel("Nueva cosecha", form("harvest-form", cosechaFields(), "Guardar borrador", 'data-submit="harvest"')) : "") +
    bannerPeriodo() + panel("Registro de cosechas", table(headers, rows), filtroProducto(cache.cosechas));
}

function pasoCantidad(unidad) { return unidad === "kg" ? "0.001" : "1"; }

function vincularUnidad(form, key, getUnidad, label) {
  const aplicar = () => {
    const unidad = getUnidad();
    const texto = unidad ? `${label} (${acopio.etiqueta(unidad)})` : label;
    $(".cantidad-label", form).textContent = texto;
    form.elements.cantidad.step = pasoCantidad(unidad);
    form.elements.cantidad.min = pasoCantidad(unidad);
  };
  aplicar();
  form.elements[key].addEventListener("change", aplicar);
}

function bindHarvest(form, parcelaId = "") {
  if (!form) return;
  vincularUnidad(form, "producto_id", () => cache.productos.find((p) => p.id === Number(form.elements.producto_id.value))?.unidad, "Cantidad estimada");
  const finca = form.elements.finca_id;
  const parcelas = form.elements.parcela_id;
  const fill = () => {
    parcelas.innerHTML = '<option value="">Sin parcela</option>' + cache.parcelas
      .filter((p) => p.activo && p.finca_id === Number(finca.value))
      .map((p) => `<option value="${p.id}">Parcela ${p.numero}</option>`).join("");
  };
  fill();
  parcelas.value = parcelaId || "";
  finca.addEventListener("change", fill);
}

function filtroProducto(filas) {
  const opciones = cache.productos.map((p) => [p.id, p.nombre + " · " + acopio.etiqueta(p.unidad)]);
  if (scopeProduct === 0 || filas.some((f) => f.producto_id == null)) opciones.push([0, "Histórico sin clasificar"]);
  return field("Producto", selector("filtrar_producto", opciones, "Todos los productos", scopeProduct ?? ""));
}

function lots() {
  const rows = periodoVisible(cache.lotes, "fecha_ingreso").map((l) => [
    safe(l.codigo), safe(l.producto), safe(acopio.etiqueta(l.unidad)), safe(l.fecha_ingreso), safe(fincaNombre(l.finca_id)),
    l.cosecha_id ? "#" + l.cosecha_id : "—", safe(l.detalle || "—"),
    button("Ver movimientos", `data-lot-history="${l.id}"`)
  ]);
  return head("Lotes", "La recepción vincula el lote con la finca, la cosecha y la entrada al almacén.", excel("lotes")) +
    (admin() ? button("Ir a recepción de cosechas", 'data-page="harvests"', "primary") : "") +
    bannerPeriodo() + panel("Lotes de ingreso", table(["Código", "Producto", "Unidad", "Fecha de ingreso", "Finca", "Cosecha de origen", "Detalle", "Kardex"], rows), filtroProducto(cache.lotes));
}

function movements() {
  const anulados = new Set(cache.movimientos.map((m) => m.anula_movimiento_id).filter(Boolean));
  const rows = periodoVisible(cache.movimientos, "fecha").slice().reverse().map((m) => {
    const detalle = safe(m.detalle) + (m.tipo === "merma" ? " " + pill("Merma", "orange") : "") +
      (anulados.has(m.id) ? ' ' + pill("Anulado", "rose") : "");
    const base = [safe(m.fecha), safe(m.producto), detalle, safe(fincaNombre(m.finca_id)), safe(loteCodigo(m.lote_id)),
      acopio.cantidad(m.cantidad_entrada, m.unidad), acopio.cantidad(m.cantidad_salida, m.unidad),
      '<b>' + acopio.cantidad(m.cantidad_saldo, m.unidad) + '</b>', safe(m.doc || "—")];
    return admin() ? [...base, !m.anula_movimiento_id && !anulados.has(m.id) && m.finca_id ?
      button("Anular", `data-reverse="${m.id}"`, "danger") : "—"] : base;
  });
  const fields = [
    field("Fecha", input("fecha", 'type="date" required', fechaActual())),
    field("Detalle", input("detalle", 'required maxlength="150"')),
    field("Lote", selector("lote_id", cache.lotes.map((l) => [l.id, l.codigo + " · " + l.producto]), "Elegir lote", scopeLot, true)),
    field("Tipo", selector("accion", [["salida", "Despacho"], ["merma", "Merma"], ["entrada", "Entrada manual"]], "Elegir tipo", "salida", true)),
    field('<span class="cantidad-label">Cantidad</span>', input("cantidad", 'type="number" min="0.001" step="0.001" required')),
    field("Documento", input("doc", 'maxlength="30"')),
    field("Observación o motivo de merma", input("observacion", 'maxlength="200"')),
    field("Finca para lote sin origen", selector("finca_id", fincaItems(true), "Usar la finca del lote"))
  ];
  const headers = ["Fecha", "Producto", "Movimiento", "Finca", "Lote", "Entrada", "Salida", "Saldo", "Documento"];
  if (admin()) headers.push("Acción");
  const descripcion = scopeLot ? `Saldo e historial del lote ${safe(loteCodigo(scopeLot))}.` :
    scopeTables && filtros.finca_id ? "Saldo por producto dentro de la finca seleccionada." : "Cada saldo se calcula para su producto y unidad.";
  return head("Kardex", descripcion, excel("kardex")) +
    (admin() ? panel("Registrar un movimiento", form("movement-form", fields, "Guardar movimiento", 'data-submit="movement"')) : "") +
    (scopeLot ? button("Volver al listado de lotes", 'data-page="lots"') : "") +
    bannerPeriodo() + panel("Historial de movimientos", table(headers, rows), filtroProducto(cache.movimientos));
}

function bindMovement(form) {
  if (!form) return;
  vincularUnidad(form, "lote_id", () => cache.lotes.find((l) => l.id === Number(form.elements.lote_id.value))?.unidad, "Cantidad");
  const tipo = form.elements.accion;
  const actualizar = () => { form.elements.observacion.required = tipo.value === "merma"; };
  tipo.addEventListener("change", actualizar);
  actualizar();
}

function products() {
  const rows = cache.productos.map((p) => [safe(p.nombre), safe(acopio.etiqueta(p.unidad))]);
  return head("Productos y unidades", "Elige la medida con la que se controla el saldo de cada producto.", excel("productos")) +
    panel("Nuevo producto", form("product-form", [
        field("Nombre", input("nombre", 'required minlength="2" maxlength="70"')),
        field("Unidad de inventario", selector("unidad", [["unidad", "Piezas"], ["caja", "Cajas"], ["kg", "Kilogramos"]], "Elegir unidad", "", true)),
      ], "Agregar producto", 'data-submit="product"')) +
    panel("Catálogo", table(["Producto", "Unidad de inventario"], rows));
}

function farms() {
  const farmRows = cache.fincas.map((f) => [f.numero, safe(fincaNombre(f.id)), safe(f.ubicacion || "—")]);
  const plotRows = cache.parcelas.map((p) => [safe(fincaNombre(p.finca_id)), p.numero, p.superficie_ha == null ? "—" : fmt(p.superficie_ha, 2)]);
  const farmForm = form("farm-form", [
    field("Número", input("numero", 'type="number" min="1" required')),
    field("Nombre", input("nombre", 'maxlength="100"')),
    field("Ubicación", input("ubicacion", 'maxlength="150"'))
  ], "Guardar finca", 'data-submit="farm"');
  const plotForm = form("plot-form", [
    field("Finca", selector("finca_id", fincaItems(true), "Elegir finca", "", true)),
    field("Número de parcela", input("numero", 'type="number" min="1" required')),
    field("Superficie (ha)", input("superficie_ha", 'type="number" min="0" step="0.01"'))
  ], "Guardar parcela", 'data-submit="plot"');
  return head("Fincas y parcelas", "Identifica el terreno de origen de cada cosecha.") +
    (admin() ? `<div class="grid-two">${panel("Nueva finca", farmForm)}${panel("Nueva parcela", plotForm)}</div>` : "") +
    panel("Fincas", table(["Número", "Nombre", "Ubicación"], farmRows), excel("fincas")) +
    panel("Parcelas", table(["Finca", "Número", "Superficie (ha)"], plotRows), excel("parcelas"));
}

function finance() {
  const rows = periodoVisible(cache.finanzas, "fecha").slice().reverse().map((r) => {
    const base = [safe(r.fecha), pill(r.tipo === "venta" ? "Venta" : r.tipo === "compra" ? "Compra" : "Gasto", r.tipo === "venta" ? "" : "orange"),
      safe(r.concepto), r.lote_id ? safe(loteCodigo(r.lote_id)) : "Sin lote", r.finca_id ? safe(fincaNombre(r.finca_id)) : "Empresa", "Bs " + fmt(r.monto_bs, 2),
      r.anulado ? pill("Anulado", "rose") : pill("Vigente"), safe(r.motivo_anulacion || "—")];
    return admin() ? [...base, r.anulado ? "—" : button("Anular", `data-reverse-finance="${r.id}"`, "danger")] : base;
  });
  const fields = [
    field("Fecha", input("fecha", 'type="date" required', fechaActual())),
    field("Tipo", selector("tipo", [["venta", "Venta"], ["costo", "Gasto adicional"], ["compra", "Completar compra pendiente"]], "Seleccionar tipo", "", true)),
    field("Concepto", input("concepto", 'required minlength="3" maxlength="150"')),
    field("Monto (Bs)", input("monto_bs", 'type="number" min="0.01" step="0.01" required')),
    field("Lote", selector("lote_id", cache.lotes.map(l => [l.id, l.codigo + " · " + l.producto]), "Sin lote (solo gasto general)"))
  ];
  const headers = ["Fecha", "Tipo", "Concepto", "Lote", "Ámbito", "Monto (Bs)", "Estado", "Motivo"];
  if (admin()) headers.push("Acción");
  return head("Ventas y costos", "Consulta los importes que componen el resultado registrado.", excel("finanzas")) +
    (admin() ? panel("Nuevo registro", form("finance-form", fields, "Guardar registro", 'data-submit="finance"')) : "") +
    bannerPeriodo() + panel("Registros del período", table(headers, rows));
}

function workerFields(c = {}) {
  return [
    field("Nombre completo", input("nombre", 'required maxlength="100"', c.nombre)),
    field("Documento", input("ci", 'maxlength="20"', c.ci)),
    field("Teléfono", input("telefono", 'maxlength="20"', c.telefono))
  ];
}

function workers() {
  const rows = cache.cosecheros.map((c) => [safe(c.nombre), safe(c.ci || "—"), safe(c.telefono || "—"),
    pill(c.activo ? "Activo" : "Inactivo", c.activo ? "" : "gray"),
    c.activo ? `<div class="table-actions">${button("Editar", `data-edit-worker="${c.id}"`)}${button("Desactivar", `data-disable-worker="${c.id}"`, "danger")}</div>` : "—"]);
  return head("Cosecheros", "Personas que entregan la cosecha.", excel("cosecheros")) +
    panel("Nuevo cosechero", form("worker-form", workerFields(), "Guardar cosechero", 'data-submit="worker"')) +
    panel("Registro de cosecheros", table(["Nombre", "Documento", "Teléfono", "Estado", "Acciones"], rows));
}

function clients() {
  const libres = cache.fincas.filter(f => f.activo && f.usuario_id == null).map(f => [f.id, fincaNombre(f.id)]);
  const pendientes = cache.solicitudes.map(u => [
    safe(u.nombre_completo), safe(u.username),
    form("aprobar-" + u.id, [field("Finca sin asignar", selector("finca_id", libres, "Selecciona la finca", "", true))],
      "Aprobar acceso", `data-submit="approve" data-id="${u.id}"`)
  ]);
  const rows = cache.clientes.map((c) => [safe(c.nombre_completo), safe(c.username), c.fincas.map((f) =>
    `<span class="affiliation">${safe(fincaNombre(f.id))} ${button("Quitar", `data-unassign="${f.id}"`, "danger")}</span>`
  ).join(" ") || "Sin fincas"]);
  const fields = [
    field("Productor", selector("usuario_id", cache.clientes.filter((u) => u.activo).map((u) => [u.id, u.nombre_completo]), "Elegir productor", "", true)),
    field("Finca", selector("finca_id", fincaItems(true), "Elegir finca", "", true))
  ];
  return head("Afiliaciones", "Vincula cada cuenta de productor con las fincas que puede consultar.", excel("afiliaciones")) +
    panel("Solicitudes pendientes", table(["Nombre", "Usuario", "Asignación"], pendientes)) +
    panel("Asignar acceso", form("assign-form", fields, "Asignar finca", 'data-submit="assign"')) +
    panel("Productores y fincas", table(["Productor", "Usuario", "Fincas asociadas"], rows));
}

function users() {
  const rol = admin() ? "Productor" : "Administrador operativo";
  const rows = cache.cuentas.map((u) => [
    safe(u.nombre_completo), safe(u.username), pill(u.activo ? "Activa" : "Inactiva", u.activo ? "" : "gray"),
    button(u.activo ? "Desactivar" : "Activar", `data-user-id="${u.id}" data-next-state="${!u.activo}"`, u.activo ? "danger" : "soft")
  ]);
  const fields = [
    field("Nombre completo", input("nombre_completo", 'required maxlength="100"')),
    field("Usuario", input("username", 'required minlength="3" maxlength="50" autocomplete="off"')),
    field("Contraseña inicial", input("password", 'type="password" required minlength="12" maxlength="72" autocomplete="new-password"'))
  ];
  return head("Cuentas", `Administra los accesos del perfil ${rol.toLowerCase()}.`, excel("cuentas")) +
    panel("Nueva cuenta · " + rol, form("user-form", fields, "Crear cuenta", 'data-submit="user"')) +
    panel("Cuentas registradas", table(["Nombre", "Usuario", "Estado", "Acción"], rows));
}

function journal() {
  const parcelas = cache.parcelas.filter(p => p.activo).map(p => [p.id, fincaNombre(p.finca_id) + " · Parcela " + p.numero]);
  const campos = [
    field("Parcela", selector("parcela_id", parcelas, "Elegir parcela", "", true)),
    field("Actividad", selector("tipo", ["Abono","Cosecha","Incidencia"].map(t => [t,t]), "Elegir actividad", "Abono", true)),
    field("Fecha", input("fecha", 'type="date" required', fechaActual())),
    field("Abono aplicado", input("insumo", 'maxlength="100"')),
    field("Dosis aplicada", input("dosis", 'type="number" min="0.001" step="0.001"')),
    field("Unidad de dosis", selector("unidad_dosis", ["kg/ha","L/ha","g/planta","mL/planta"].map(u => [u,u]), "Elegir unidad")),
    field("Cosecha recibida", selector("cosecha_id", [], "Elegir cosecha")),
    field("Superficie cosechada (ha)", input("area_ha", 'type="number" min="0.0001" step="0.0001"')),
    field("Descripción de la labor o incidencia", input("detalle", 'required minlength="3" maxlength="250"'))
  ];
  const filas = cache.bitacora.map(r => [safe(r.fecha),safe(r.parcela),safe(r.tipo),safe(r.detalle),
    safe(r.insumo ? r.insumo + " · " + r.dosis + " " + r.unidad_dosis : r.lote ? r.lote + " · " + r.area_ha + " ha" : "—")]);
  return head("Bitácora por parcela","Registra la labor y su fecha. Para medir el rendimiento, vincula una cosecha recibida con su superficie efectiva.",excel("bitacora")) +
    panel("Nueva anotación",form("journal-form",campos,"Guardar anotación",'data-submit="journal"')) +
    panel("Historial de campo",table(["Fecha","Parcela","Actividad","Descripción","Aplicación o cosecha"],filas));
}
function bindJournal(f) {
  const e = f.elements;
  const usadas = new Set(cache.bitacora.map(r => r.cosecha_id));
  function fechaCosecha() {
    const seleccion = cache.cosechas.find(c => c.id === Number(e.cosecha_id.value));
    if (seleccion) e.fecha.value = seleccion.fecha;
  }
  function opciones() {
    const filas = cache.cosechas.filter(c => c.parcela_id === Number(e.parcela_id.value) && c.recibida != null && !c.borrador && !usadas.has(c.id));
    e.cosecha_id.replaceChildren(new Option(filas.length ? "Elegir cosecha" : "Sin recepciones disponibles", ""));
    filas.forEach(c => e.cosecha_id.add(new Option(c.fecha + " · " + c.producto + " · #" + c.id, c.id)));
  }
  function mostrar() {
    const cosecha = e.tipo.value === "Cosecha";
    for (const [nombre,visible] of Object.entries({insumo:e.tipo.value==="Abono",dosis:e.tipo.value==="Abono",unidad_dosis:e.tipo.value==="Abono",cosecha_id:cosecha,area_ha:cosecha})) {
      const control=e[nombre]; control.disabled=!visible; control.required=visible;
      control.closest("label").hidden=!visible;
    }
    e.fecha.readOnly=cosecha;
    if(cosecha) opciones();
  }
  e.tipo.onchange=mostrar; e.parcela_id.onchange=opciones; e.cosecha_id.onchange=fechaCosecha; mostrar();
}


const views = { journal, dashboard, harvests, lots, movements, products, finance, farms, workers, clients, users };

function openDialog(title, content) {
  const dialog = $("#action-dialog");
  $("#dialog-title").textContent = title;
  $("#dialog-content").innerHTML = content;
  dialog.showModal();
  return dialog;
}

function receive(id) {
  const row = cache.cosechas.find((c) => c.id === id);
  if (!row.producto_id) {
    toast("Edita el borrador y elige un producto antes de recibirlo.", true);
    return;
  }
  const paso = pasoCantidad(row.unidad);
  const opciones = [["kg", "Kilogramos"], ["unidad", "Piezas"], ["caja", "Cajas"]].filter(([id]) => id !== row.unidad);
  const dialog = openDialog("Recepción de " + row.producto,
    `<p class="muted">${safe(fincaNombre(row.finca_id))} · Cosecha #${id}</p><p class="receipt-accepted" id="aceptada-en-vivo" aria-live="polite"></p>` +
    form("receive-form", [
      field("Código de lote", input("codigo", 'required maxlength="30"')),
      field("Fecha de recepción", input("fecha", `type="date" required min="${safe(row.fecha)}"`, fechaActual())),
      field("Llegó (" + acopio.etiqueta(row.unidad) + ")", input("recibida", `type="number" min="${paso}" step="${paso}" required`, row.cantidad)),
      field("Rechazada (" + acopio.etiqueta(row.unidad) + ")", input("rechazada", `type="number" min="0" step="${paso}" required`, 0)),
      field("Motivo del rechazo", input("motivo_rechazo", 'minlength="4" maxlength="200"')),
      field("Monto registrado (Bs)", input("monto_bs", 'type="number" min="0" step="0.01" required', row.monto_bs)),
      field("Documento", input("doc", 'maxlength="30"')),
      field("Unidad adicional del total", selector("unidad_secundaria", opciones, "Sin medición adicional")),
      field("Cantidad medida", input("cantidad_secundaria", 'type="number" min="0.001" step="0.001"'))
    ], "Confirmar recepción", `data-submit="receive" data-id="${id}"`));
  const f = $("#receive-form", dialog);
  const actualizar = () => {
    const recibida = Number(f.elements.recibida.value);
    const rechazada = Number(f.elements.rechazada.value);
    f.elements.rechazada.max = f.elements.recibida.value;
    f.elements.motivo_rechazo.required = rechazada > 0;
    const unidad = f.elements.unidad_secundaria.value;
    const adicional = f.elements.cantidad_secundaria;
    adicional.disabled = !unidad;
    adicional.required = Boolean(unidad);
    adicional.min = pasoCantidad(unidad);
    adicional.step = pasoCantidad(unidad);
    if (!unidad) adicional.value = "";
    $("#aceptada-en-vivo", dialog).textContent = rechazada > recibida ?
      "El rechazo supera la cantidad recibida." : "Entrará al Kardex: " + acopio.cantidad(recibida - rechazada, row.unidad);
  };
  f.addEventListener("input", actualizar);
  f.addEventListener("change", actualizar);
  actualizar();
}

function editHarvest(id) {
  const row = cache.cosechas.find((c) => c.id === id);
  const dialog = openDialog("Editar cosecha #" + id, form("edit-form", cosechaFields(row), "Guardar cambios",
    `data-submit="edit" data-id="${id}"`));
  bindHarvest($("#edit-form", dialog), row.parcela_id);
}

function reverse(id, finance = false) {
  openDialog((finance ? "Anular registro #" : "Anular movimiento #") + id,
    `<p class="muted">${finance ? "Se conservará el registro con su motivo de anulación." : "Se creará un movimiento compensatorio y quedará registrada la justificación."}</p>` +
    form("reverse-form", [field("Motivo", input("motivo", 'required minlength="4" maxlength="200"'))],
      "Confirmar anulación", `data-submit="${finance ? "reverseFinance" : "reverse"}" data-id="${id}"`));
}

const endpoints = {
  journal: "/bitacora",
  farm: "/inventario/fincas", plot: "/inventario/parcelas", worker: "/cosecheros",
  harvest: "/kardex/cosechas", movement: "/kardex/movimientos",
  user: "/auth/usuarios", assign: "/portal/api/admin/asignar-finca", finance: "/finanzas",
  product: "/inventario/productos"
};

function payload(form) {
  const data = Object.fromEntries(new FormData(form).entries());
  const numeric = ["cosechero_id", "finca_id", "parcela_id", "lote_id", "usuario_id", "numero", "superficie_ha", "producto_id"];
  for (const [key, value] of Object.entries(data)) {
    if (value === "") data[key] = null;
    else if (numeric.includes(key)) data[key] = Number(value);
  }
  return data;
}

async function submit(event) {
  const form = event.target;
  if (form.id === "period-form") {
    event.preventDefault();
    const next = payload(form);
    if (next.fecha_desde > next.fecha_hasta) {
      toast("La fecha inicial debe ser anterior o igual a la final.", true);
      return;
    }
    filtros = next;
    await navigate("dashboard");
    return;
  }
  if (!form.dataset.submit) return;
  event.preventDefault();
  const action = form.dataset.submit;
  const id = form.dataset.id;
  const special = { approve: `/auth/solicitudes/${id}/aprobar`, receive: `/kardex/cosechas/${id}/recepcion`, edit: `/kardex/cosechas/${id}`,
    editWorker: `/cosecheros/${id}`, reverse: `/kardex/movimientos/${id}/anular`,
    reverseFinance: `/finanzas/${id}/anular` };
  const data = payload(form);
  if (action === "user") data.rol = admin() ? "cliente" : "admin";
  if (action === "movement") {
    data.cantidad_entrada = data.accion === "entrada" ? data.cantidad : 0;
    data.cantidad_salida = data.accion === "entrada" ? 0 : data.cantidad;
    data.tipo = data.accion === "merma" ? "merma" : "movimiento";
    delete data.accion;
    delete data.cantidad;
  }
  if (action === "assign") {
    const actual = cache.fincas.find((f) => f.id === data.finca_id)?.usuario_id;
    if (actual && actual !== data.usuario_id && !window.confirm("¿Transferir esta finca y su historial al nuevo productor?")) return;
  }
  const submitButton = $('button[type="submit"]', form);
  submitButton.disabled = true;
  try {
    const resultado = await api(endpoints[action] || special[action], { method: action.startsWith("edit") ? "PUT" : "POST", body: JSON.stringify(data) });
    if ($("#action-dialog").open) $("#action-dialog").close();
    toast(action === "receive" ? (resultado.movimiento ? "Recepción registrada. Solo lo aceptado ingresó al Kardex." :
      "Recepción registrada como rechazo total.") : "Cambios guardados.");
    await navigate(currentPage);
  } catch (error) {
    toast(error.message, true);
    submitButton.disabled = false;
  }
}

async function download(tabla, btn) {
  const useScope = scopeTables && ["cosechas", "lotes", "kardex", "finanzas", "resultado-lotes"].includes(tabla);
  const filtrosExcel = tabla === "existencias" ? { ...filtros } :
    useScope ? { ...scopeParams(), confirmadas: tabla === "cosechas" ? true : null } : {};
  if (["cosechas", "lotes", "kardex"].includes(tabla)) filtrosExcel.producto_id = scopeProduct;
  if (tabla === "kardex" && scopeLot) filtrosExcel.lote_id = scopeLot;
  btn.disabled = true;
  try {
    const response = await fetchAuth(`/reportes/excel/${tabla}?${params(filtrosExcel)}`);
    const url = URL.createObjectURL(await response.blob());
    const a = document.createElement("a");
    a.href = url;
    a.download = `kardex-${tabla}.xlsx`;
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1500);
  } catch (error) { toast(error.message, true); }
  finally { btn.disabled = false; }
}

async function update(path, options, confirmation) {
  if (confirmation && !window.confirm(confirmation)) return;
  try {
    await api(path, options);
    toast("Cambios guardados.");
    await navigate(currentPage);
  } catch (error) { toast(error.message, true); }
}

$("#app-shell").addEventListener("submit", submit);
$("#action-dialog").addEventListener("submit", submit);
$("#dialog-close").addEventListener("click", () => $("#action-dialog").close());
$("#app-shell").addEventListener("change", (event) => {
  if (event.target.name !== "filtrar_producto") return;
  scopeProduct = event.target.value === "" ? null : Number(event.target.value);
  scopeLot = null;
  navigate(currentPage);
});
$("#app-shell").addEventListener("click", (event) => {
  const btn = event.target.closest("button");
  if (!btn) return;
  const d = btn.dataset;
  if (d.page) { scopeTables = false; scopeLot = null; scopeProduct = null; navigate(d.page); }
  if (d.periodPage) { scopeTables = d.periodMode || "period"; scopeLot = null; scopeProduct = null; navigate(d.periodPage); }
  if (d.lotHistory) { scopeTables = false; scopeLot = Number(d.lotHistory); scopeProduct = null; navigate("movements"); }
  if (d.cierreHoy !== undefined) {
    const hoy = fechaActual();
    filtros = { ...filtros, fecha_desde: hoy, fecha_hasta: hoy };
    navigate("dashboard");
  }
  if (d.detailProduct !== undefined) {
    detailProduct = Number(d.detailProduct);
    $("#detalle-existencias").innerHTML = existenciasVista(cache.resumen.existencias);
    $(`[data-detail-product="${detailProduct}"]`).focus();
  }
  if (d.kardexProduct !== undefined) {
    scopeTables = "balance";
    scopeLot = null;
    scopeProduct = Number(d.kardexProduct);
    navigate("movements");
  }
  if (d.clearScope !== undefined) { scopeTables = false; navigate(currentPage); }
  if (d.export) download(d.export, btn);
  if (d.receive) receive(Number(d.receive));
  if (d.receipt) {
    const row = cache.cosechas.find((c) => c.id === Number(d.receipt));
    if (row?.recibida != null) acopio.comprobante({ ...row, finca: fincaNombre(row.finca_id), codigo_lote: loteCodigo(row.lote_id) });
  }
  if (d.editHarvest) editHarvest(Number(d.editHarvest));
  if (d.editWorker) {
    const row = cache.cosecheros.find((c) => c.id === Number(d.editWorker));
    openDialog("Editar cosechero", form("edit-worker-form", workerFields(row), "Guardar cambios", `data-submit="editWorker" data-id="${row.id}"`));
  }
  if (d.disableWorker) update(`/cosecheros/${d.disableWorker}`, { method: "DELETE" }, "¿Desactivar este cosechero?");
  if (d.reverse) reverse(Number(d.reverse));
  if (d.reverseFinance) reverse(Number(d.reverseFinance), true);
  if (d.deleteHarvest) update(`/kardex/cosechas/${d.deleteHarvest}`, { method: "DELETE" }, "¿Eliminar este borrador de cosecha?");
  if (d.unassign) update("/portal/api/admin/asignar-finca",
    { method: "POST", body: JSON.stringify({ finca_id: Number(d.unassign), usuario_id: null }) }, "¿Quitar el acceso a esta finca?");
  if (d.userId) update(`/auth/usuarios/${d.userId}/estado`,
    { method: "PATCH", body: JSON.stringify({ activo: d.nextState === "true" }) });
});
$("#theme-toggle").addEventListener("click", () => applyTheme(document.documentElement.dataset.theme === "dark" ? "light" : "dark"));
$("#logout-btn").addEventListener("click", logout);
$("#menu-toggle").addEventListener("click", () => $("#sidebar").classList.toggle("open"));
$("#login-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const submitButton = $('button[type="submit"]', form);
  submitButton.disabled = true;
  try {
    const data = await api("/auth/login", { method: "POST", body: JSON.stringify(payload(form)) });
    if (data.usuario.rol !== "admin") {
      toast("Este acceso requiere una cuenta de administrador.", true);
      return;
    }
    session = data.usuario;
    token = data.access_token;
    localStorage.setItem(TOKEN_KEY, token);
    form.reset();
    showApp();
  } catch (error) { toast(error.message, true); }
  finally { submitButton.disabled = false; }
});

(async function init() {
  const theme = localStorage.getItem(THEME_KEY);
  applyTheme(theme === "dark" || theme === "light" ? theme : "light");
  token = localStorage.getItem(TOKEN_KEY);
  if (!token) return;
  try {
    session = await api("/auth/me");
    if (session.rol === "admin") showApp();
    else logout();
  } catch { logout(); }
})();
