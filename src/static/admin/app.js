/* ============================================================
   KARDEX Agrícola · Panel de administración
   Adaptado al backend real: login con token JWT, roles
   admin / encargado / trabajador, invitaciones y asignación
   de fincas a los productores.
   ============================================================ */

const API = "";
const TOKEN_KEY = "kardex_admin_token";
const USER_KEY = "kardex_admin_user";
const THEME_KEY = "kardex_admin_theme";

const $ = (s, root = document) => root.querySelector(s);
const $$ = (s, root = document) => [...root.querySelectorAll(s)];

let session = null;
let token = null;
let currentPage = "dashboard";

let cache = {
  fincas: [], parcelas: [], cosecheros: [], lotes: [],
  cosechas: [], movimientos: [], clientes: [], invitaciones: [], usuarios: []
};

const ROLE_LABEL = {
  admin: "Administrador",
  encargado: "Encargado",
  trabajador: "Trabajador",
  cliente: "Productor"
};

const NAV = {
  admin: [
    ["dashboard", "▦", "Resumen"],
    ["lots", "▤", "Productos y lotes"],
    ["movements", "⇄", "Movimientos Kardex"],
    ["harvests", "♧", "Cosechas"],
    ["workers", "♙", "Cosecheros"],
    ["farms", "⌂", "Fincas y parcelas"],
    ["clients", "◈", "Clientes y fincas"],
    ["users", "◍", "Cuentas y usuarios"],
    ["invites", "✉", "Invitaciones"]
  ],
  encargado: [
    ["dashboard", "▦", "Resumen"],
    ["lots", "▤", "Productos y lotes"],
    ["movements", "⇄", "Movimientos Kardex"],
    ["harvests", "♧", "Cosechas"],
    ["workers", "♙", "Cosecheros"],
    ["farms", "⌂", "Fincas y parcelas"]
  ],
  trabajador: [
    ["dashboard", "▦", "Mi espacio"],
    ["harvests", "♧", "Registrar cosecha"],
    ["lots", "▤", "Consultar lotes"]
  ]
};

const PAGE_NAMES = {
  dashboard: "Resumen", lots: "Productos y lotes", movements: "Movimientos Kardex",
  harvests: "Cosechas", workers: "Cosecheros", farms: "Fincas y parcelas",
  clients: "Clientes y fincas", invites: "Invitaciones", users: "Cuentas y usuarios"
};

const today = () => new Date().toISOString().slice(0, 10);
const fmt = (n) => Number(n || 0).toLocaleString("es-BO", { maximumFractionDigits: 3 });
const safe = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({
  "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
}[c]));

/* ---------------------------------------------------------- tema */
function applyTheme(t) {
  document.documentElement.setAttribute("data-theme", t);
  localStorage.setItem(THEME_KEY, t);
  const meta = document.querySelector('meta[name="theme-color"]');
  if (meta) meta.setAttribute("content", t === "dark" ? "#0b1024" : "#f2f5fc");
}

function initTheme() {
  const saved = localStorage.getItem(THEME_KEY);
  if (saved === "dark" || saved === "light") { applyTheme(saved); return; }
  const prefiereOscuro = window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;
  applyTheme(prefiereOscuro ? "dark" : "light");
}

/* ---------------------------------------------------------- avisos */
function toast(message, error = false) {
  const t = $("#toast");
  t.textContent = message;
  t.className = "toast show" + (error ? " error" : "");
  clearTimeout(window.__toastTimer);
  window.__toastTimer = setTimeout(() => { t.className = "toast"; }, 3800);
}

/* ---------------------------------------------------------- API */
async function request(path, options = {}) {
  const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
  if (token) headers.Authorization = "Bearer " + token;

  const response = await fetch(API + path, { ...options, headers });
  let body = {};
  try { body = await response.json(); } catch (e) { /* sin cuerpo */ }

  if (response.status === 401) {
    logout(true);
    throw new Error("La sesión venció. Vuelve a iniciar sesión.");
  }
  if (!response.ok) {
    const d = body.detail;
    const msg = typeof d === "string" ? d : (Array.isArray(d) && d[0] && d[0].msg) || `Error ${response.status}`;
    throw new Error(msg);
  }
  return body;
}

/* ---------------------------------------------------------- sesión */
function showAuth(tab = "login") {
  $("#auth-screen").classList.remove("hidden");
  $("#app-shell").classList.add("hidden");
  $$(".tab").forEach((b) => b.classList.toggle("active", b.dataset.authTab === tab));
  $("#login-form-wrap").classList.toggle("hidden", tab !== "login");
  $("#invite-form-wrap").classList.toggle("hidden", tab !== "invite");
}

function showApp() {
  $("#auth-screen").classList.add("hidden");
  $("#app-shell").classList.remove("hidden");

  const name = session.nombre_completo || session.username || "Usuario";
  const initial = (name[0] || "U").toUpperCase();
  $("#side-user").textContent = name;
  $("#side-role").textContent = ROLE_LABEL[session.rol] || session.rol;
  $("#user-avatar").textContent = initial;
  $("#top-avatar").textContent = initial;
  $("#today-label").textContent = new Intl.DateTimeFormat("es-BO", { dateStyle: "full" }).format(new Date());

  renderNav();
  const destino = pageFromHash();
  loadData()
    .then(() => navigate(destino))
    .catch((e) => { toast(e.message, true); navigate(destino); });
}

/* Permite abrir una vista directamente, por ejemplo /admin#cosechas */
function pageFromHash() {
  const pedida = (window.location.hash || "").replace("#", "");
  const permitidas = (NAV[session.rol] || []).map(([id]) => id);
  return permitidas.includes(pedida) ? pedida : "dashboard";
}

function logout(silencioso = false) {
  session = null;
  token = null;
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
  if (!silencioso) toast("Sesión cerrada.");
  showAuth("login");
}

/* ---------------------------------------------------------- navegación */
function renderNav() {
  const items = NAV[session.rol] || NAV.trabajador;
  $("#side-nav").innerHTML = items.map(([id, ico, label]) =>
    `<button class="nav-item ${id === currentPage ? "active" : ""}" data-page="${id}" type="button"><span class="nav-ico">${ico}</span>${label}</button>`
  ).join("");
  $$("[data-page]").forEach((b) => b.addEventListener("click", () => navigate(b.dataset.page)));
}

function navigate(page) {
  if (!NAV[session.rol] || !NAV[session.rol].some(([id]) => id === page)) page = "dashboard";
  currentPage = page;
  if (window.location.hash !== "#" + page) history.replaceState(null, "", "#" + page);
  renderNav();
  $("#page-crumb").textContent = PAGE_NAMES[page] || "Resumen";
  $("#sidebar").classList.remove("open");

  const vistas = {
    dashboard: dashboardView, lots: lotsView, movements: movementsView,
    harvests: harvestsView, workers: workersView, farms: farmsView,
    clients: clientsView, invites: invitesView, users: usersView
  };
  $("#page-content").innerHTML = (vistas[page] || dashboardView)();
  bindPage();
}

/* ---------------------------------------------------------- carga de datos */
async function loadData() {
  const jobs = [
    ["fincas", "/inventario/fincas"],
    ["parcelas", "/inventario/parcelas"],
    ["cosecheros", "/cosecheros"],
    ["lotes", "/inventario/lotes"],
    ["cosechas", "/kardex/cosechas"],
    ["movimientos", "/kardex/movimientos"]
  ];
  if (session.rol === "admin") {
    jobs.push(
      ["clientes", "/portal/api/admin/clientes"],
      ["invitaciones", "/auth/invitaciones"],
      ["usuarios", "/auth/usuarios"]
    );
  }
  await Promise.allSettled(jobs.map(async ([key, url]) => {
    try { cache[key] = await request(url); }
    catch (e) { cache[key] = []; console.warn(url, e.message); }
  }));
}

/* ---------------------------------------------------------- piezas de UI */
function pageHead(kicker, title, desc, action = "") {
  return `<div class="page-head"><div><div class="page-kicker">${kicker}</div><h1>${title}</h1><p>${desc}</p></div>${action}</div>`;
}

function stat(label, value, note, icon) {
  return `<div class="stat-card"><div class="stat-top"><span>${label}</span><span class="stat-icon">${icon}</span></div><div class="stat-value">${value}</div><div class="stat-note">${note}</div></div>`;
}

function table(headers, rows, empty = "Todavía no hay registros.") {
  return `<div class="table-wrap"><table><thead><tr>${headers.map((h) => `<th>${h}</th>`).join("")}</tr></thead><tbody>${rows.length ? rows.join("") : `<tr><td colspan="${headers.length}" class="empty">${empty}</td></tr>`}</tbody></table></div>`;
}

/* ---------------------------------------------------------- vistas */
function dashboardView() {
  const kgHarvest = cache.cosechas.reduce((s, x) => s + Number(x.kg || 0), 0);
  const stock = cache.movimientos.reduce((s, x) => s + Number(x.entrada_kg || 0) - Number(x.salida_kg || 0), 0);
  const nombre = safe(session.nombre_completo || session.username);

  if (session.rol === "trabajador") {
    return `${pageHead("ESPACIO DEL TRABAJADOR", "Hola, " + nombre, "Registra tu producción y consulta la información de lotes.")}
      <div class="cards">
        ${stat("Cosechas registradas", cache.cosechas.length, "Registros del sistema", "♧")}
        ${stat("Producción acumulada", fmt(kgHarvest) + " kg", "Kilogramos registrados", "↗")}
        ${stat("Fincas", cache.fincas.length, "Fincas disponibles", "⌂")}
        ${stat("Lotes", cache.lotes.length, "Lotes registrados", "▤")}
      </div>
      <div class="panel">
        <div class="panel-head"><div><h3>Acciones de trabajo</h3><p>Operaciones disponibles para tu perfil</p></div></div>
        <div class="quick-actions">
          <button class="quick-action" data-go="harvests" type="button"><span class="quick-ico">♧</span><strong>Registrar cosecha</strong><span>Ingresar fecha, finca, parcela y kilogramos.</span></button>
          <button class="quick-action" data-go="lots" type="button"><span class="quick-ico">▤</span><strong>Consultar lotes</strong><span>Revisar los lotes existentes.</span></button>
        </div>
      </div>`;
  }

  const cards = `<div class="cards">
    ${stat("Cosechas registradas", cache.cosechas.length, "Registros de producción", "♧")}
    ${stat("Producción acumulada", fmt(kgHarvest) + " kg", "Según cosechas registradas", "↗")}
    ${stat("Lotes registrados", cache.lotes.length, "Productos identificados", "▤")}
    ${stat("Existencia calculada", fmt(stock) + " kg", "Entradas menos salidas", "◉")}
  </div>`;

  return `${pageHead("PANEL DE CONTROL", "Resumen general", "Indicadores principales de producción e inventario.",
      '<button class="btn btn-primary" data-go="lots" type="button">＋ Agregar producto</button>')}
    ${cards}
    <div class="grid-two">
      <div class="panel">
        <div class="panel-head"><div><h3>Últimas cosechas</h3><p>Actividad reciente de producción</p></div><button class="btn btn-soft" data-go="harvests" type="button">Ver todas</button></div>
        ${harvestsTable(5)}
      </div>
      <div class="panel">
        <div class="panel-head"><div><h3>Accesos rápidos</h3><p>Administración del sistema</p></div></div>
        <div class="quick-actions" style="grid-template-columns:1fr 1fr">
          <button class="quick-action" data-go="lots" type="button"><span class="quick-ico">＋</span><strong>Agregar producto</strong><span>Registrar un lote.</span></button>
          <button class="quick-action" data-go="movements" type="button"><span class="quick-ico">⇄</span><strong>Movimiento</strong><span>Registrar entrada o salida.</span></button>
          <button class="quick-action" data-go="workers" type="button"><span class="quick-ico">♙</span><strong>Cosecheros</strong><span>Gestionar trabajadores.</span></button>
          <button class="quick-action" data-go="farms" type="button"><span class="quick-ico">⌂</span><strong>Fincas</strong><span>Gestionar fincas y parcelas.</span></button>
        </div>
      </div>
    </div>`;
}

function lotsTable() {
  const rows = cache.lotes.slice().reverse().map((l) => {
    const f = cache.fincas.find((x) => x.id === l.finca_id);
    return `<tr><td><b>${safe(l.codigo)}</b></td><td>${safe(l.fecha_ingreso)}</td><td>${safe(f ? (f.nombre || "Finca " + f.numero) : (l.finca_id ?? "—"))}</td><td>${safe(l.detalle || "—")}</td><td><span class="pill">Registrado</span></td></tr>`;
  });
  return table(["CÓDIGO DE LOTE", "FECHA DE INGRESO", "FINCA", "DETALLE", "ESTADO"], rows, "No hay lotes registrados todavía.");
}

function lotsView() {
  const canManage = session.rol === "admin" || session.rol === "encargado";
  return `${pageHead("INVENTARIO", "Productos y lotes", "Consulta los productos ingresados y registra nuevos lotes.",
      canManage ? '<button class="btn btn-primary" data-scroll="lot-form" type="button">＋ Agregar producto</button>' : "")}
    <div class="panel">
      <div class="panel-head"><div><h3>Catálogo de productos</h3><p>Los productos se representan mediante lotes de ingreso.</p></div><span class="pill violet">${cache.lotes.length} lotes</span></div>
      ${lotsTable()}
    </div>
    ${canManage ? `<div class="panel" id="lot-form">
      <div class="panel-head"><div><h3>Agregar producto / lote</h3><p>Registra el lote y después su entrada en el Kardex.</p></div></div>
      <form id="create-lot-form">
        <div class="form-grid">
          <label class="field">Código de lote<input name="codigo" placeholder="Ej. TVH194E" required maxlength="30"></label>
          <label class="field">Fecha de ingreso<input type="date" name="fecha_ingreso" value="${today()}" required></label>
          <label class="field">Finca<select name="finca_id"><option value="">Sin finca asignada</option>${cache.fincas.map((f) => `<option value="${f.id}">${safe(f.nombre || "Finca " + f.numero)} (#${f.id})</option>`).join("")}</select></label>
          <label class="field">Detalle / producto<input name="detalle" placeholder="Ej. Hoja fresca"></label>
        </div>
        <div class="form-actions"><button class="btn btn-primary" type="submit">Guardar lote</button></div>
      </form>
    </div>` : ""}`;
}

function harvestsTable(limit = 100) {
  const rows = cache.cosechas.slice().reverse().slice(0, limit).map((c) => {
    const w = cache.cosecheros.find((x) => x.id === c.cosechero_id);
    const f = cache.fincas.find((x) => x.id === c.finca_id);
    return `<tr><td>${safe(c.fecha)}</td><td>${safe(w ? w.nombre : "#" + c.cosechero_id)}</td><td>${safe(f ? (f.nombre || "Finca " + f.numero) : "Finca " + c.finca_id)}</td><td><b>${fmt(c.kg)} kg</b></td><td>Bs ${fmt(c.monto_bs)}</td></tr>`;
  });
  return table(["FECHA", "COSECHERO", "FINCA", "CANTIDAD", "MONTO"], rows, "No hay cosechas registradas.");
}

function harvestsView() {
  const canCreate = session.rol !== "cliente";
  return `${pageHead("PRODUCCIÓN", "Registro de cosechas", "Control de producción por cosechero, finca y parcela.")}
    ${canCreate ? `<div class="panel">
      <div class="panel-head"><div><h3>Registrar nueva cosecha</h3><p>Completa los datos de producción para guardar el registro.</p></div></div>
      ${(cache.cosecheros.length && cache.fincas.length) ? "" : '<div class="notice-inline">Para registrar una cosecha primero deben existir al menos un cosechero y una finca.</div>'}
      <form id="create-harvest-form">
        <div class="form-grid">
          <label class="field">Fecha<input type="date" name="fecha" value="${today()}" required></label>
          <label class="field">Cosechero<select name="cosechero_id" required><option value="">Seleccionar cosechero</option>${cache.cosecheros.filter((x) => x.activo !== false).map((x) => `<option value="${x.id}">${safe(x.nombre)}</option>`).join("")}</select></label>
          <label class="field">Finca<select name="finca_id" required><option value="">Seleccionar finca</option>${cache.fincas.map((x) => `<option value="${x.id}">${safe(x.nombre || "Finca " + x.numero)}</option>`).join("")}</select></label>
          <label class="field">Parcela<select name="parcela_id"><option value="">Sin parcela</option>${cache.parcelas.map((x) => `<option value="${x.id}">Parcela ${x.numero} · Finca ${x.finca_id}</option>`).join("")}</select></label>
          <label class="field">Tipo de cosecha<input name="tipo_cosecha" value="HOJA FRESCA" required></label>
          <label class="field">Cantidad (kg)<input name="kg" type="number" min="0.001" step="0.001" required></label>
          <label class="field">Monto (Bs)<input name="monto_bs" type="number" min="0" step="0.01" value="0"></label>
          <label class="field span-2">Observación<input name="observacion" maxlength="200" placeholder="Observaciones opcionales"></label>
        </div>
        <div class="form-actions"><button class="btn btn-primary" type="submit" ${(!cache.cosecheros.length || !cache.fincas.length) ? "disabled" : ""}>Guardar cosecha</button></div>
      </form>
    </div>` : ""}
    <div class="panel">
      <div class="panel-head"><div><h3>Historial de cosechas</h3><p>Registros almacenados en la base de datos.</p></div></div>
      ${harvestsTable()}
    </div>`;
}

function movementsView() {
  const canManage = session.rol === "admin" || session.rol === "encargado";
  const rows = cache.movimientos.slice().reverse().map((m) =>
    `<tr><td>${safe(m.fecha)}</td><td>${safe(m.detalle)}</td><td>${safe(m.doc || "—")}</td><td>${fmt(m.entrada_kg)} kg</td><td>${fmt(m.salida_kg)} kg</td><td><b>${fmt(m.saldo_kg)} kg</b></td></tr>`
  );
  return `${pageHead("CONTROL DE EXISTENCIAS", "Movimientos Kardex", "Historial de entradas, salidas y saldos.")}
    ${canManage ? `<div class="panel">
      <div class="panel-head"><div><h3>Registrar movimiento</h3><p>Registra una entrada o salida de inventario.</p></div></div>
      <form id="create-movement-form">
        <div class="form-grid">
          <label class="field">Fecha<input type="date" name="fecha" value="${today()}" required></label>
          <label class="field">Detalle<input name="detalle" placeholder="Ej. Ingreso de producto" required maxlength="150"></label>
          <label class="field">Documento<input name="doc" placeholder="N.º de documento"></label>
          <label class="field">Lote<select name="lote_id"><option value="">Sin lote</option>${cache.lotes.map((l) => `<option value="${l.id}">${safe(l.codigo)}</option>`).join("")}</select></label>
          <label class="field">Finca<select name="finca_id"><option value="">Sin finca</option>${cache.fincas.map((f) => `<option value="${f.id}">${safe(f.nombre || "Finca " + f.numero)}</option>`).join("")}</select></label>
          <label class="field">Entrada (kg)<input name="entrada_kg" type="number" min="0" step="0.001" value="0"></label>
          <label class="field">Salida (kg)<input name="salida_kg" type="number" min="0" step="0.001" value="0"></label>
          <label class="field">Observación<input name="observacion" placeholder="Opcional"></label>
        </div>
        <div class="notice-inline">El saldo se calcula automáticamente: existencia actual + entrada − salida.</div>
        <div class="form-actions"><button class="btn btn-primary" type="submit">Guardar movimiento</button></div>
      </form>
    </div>` : ""}
    <div class="panel">
      <div class="panel-head"><div><h3>Libro de movimientos</h3><p>Información consultada desde kardex_movimientos.</p></div></div>
      ${table(["FECHA", "DETALLE", "DOCUMENTO", "ENTRADA", "SALIDA", "SALDO"], rows, "No hay movimientos registrados.")}
    </div>`;
}

function workersView() {
  if (session.rol === "trabajador") return dashboardView();
  const rows = cache.cosecheros.map((w) =>
    `<tr><td>${safe(w.nombre)}</td><td>${safe(w.ci || "—")}</td><td>${safe(w.telefono || "—")}</td><td><span class="pill ${w.activo ? "violet" : "gray"}">${w.activo ? "Activo" : "Inactivo"}</span></td></tr>`
  );
  return `${pageHead("PERSONAL", "Cosecheros", "Administra las personas que realizan las labores de cosecha.")}
    <div class="panel">
      <div class="panel-head"><div><h3>Registrar cosechero</h3><p>El cosechero es independiente de la cuenta de acceso al sistema.</p></div></div>
      <form id="create-worker-form">
        <div class="form-grid">
          <label class="field">Nombre completo<input name="nombre" required></label>
          <label class="field">Cédula de identidad<input name="ci"></label>
          <label class="field">Teléfono<input name="telefono"></label>
        </div>
        <div class="form-actions"><button class="btn btn-primary" type="submit">Guardar cosechero</button></div>
      </form>
    </div>
    <div class="panel">
      <div class="panel-head"><h3>Personal registrado</h3><span class="pill">${cache.cosecheros.length} personas</span></div>
      ${table(["NOMBRE", "CI", "TELÉFONO", "ESTADO"], rows)}
    </div>`;
}

function farmsView() {
  if (session.rol === "trabajador") return dashboardView();
  const frows = cache.fincas.map((f) =>
    `<tr><td>${safe(f.numero)}</td><td>${safe(f.nombre || "—")}</td><td>${safe(f.ubicacion || "—")}</td><td>${cache.parcelas.filter((p) => p.finca_id === f.id).length}</td><td>${f.usuario_id ? `<span class="pill violet">Productor #${f.usuario_id}</span>` : `<span class="pill gray">Sin asignar</span>`}</td></tr>`
  );
  const prows = cache.parcelas.map((p) =>
    `<tr><td>${safe(p.numero)}</td><td>${safe(p.finca_id)}</td><td>${safe(p.superficie_ha ?? "—")} ha</td></tr>`
  );
  return `${pageHead("ESTRUCTURA AGRÍCOLA", "Fincas y parcelas", "Organiza los espacios de producción agrícola.")}
    <div class="grid-two">
      <div class="panel">
        <div class="panel-head"><h3>Registrar finca</h3></div>
        <form id="create-farm-form">
          <div class="form-grid">
            <label class="field">Número<input name="numero" type="number" min="1" required></label>
            <label class="field">Nombre<input name="nombre"></label>
            <label class="field span-2">Ubicación<input name="ubicacion"></label>
          </div>
          <div class="form-actions"><button class="btn btn-primary" type="submit">Guardar finca</button></div>
        </form>
        <div style="margin-top:22px">${table(["N.º", "NOMBRE", "UBICACIÓN", "PARCELAS", "PRODUCTOR"], frows)}</div>
      </div>
      <div class="panel">
        <div class="panel-head"><h3>Registrar parcela</h3></div>
        <form id="create-plot-form">
          <div class="form-grid">
            <label class="field">Finca<select name="finca_id" required><option value="">Seleccionar</option>${cache.fincas.map((f) => `<option value="${f.id}">${safe(f.nombre || "Finca " + f.numero)}</option>`).join("")}</select></label>
            <label class="field">Número<input name="numero" type="number" min="1" required></label>
            <label class="field span-2">Superficie (ha)<input name="superficie_ha" type="number" min="0" step="0.01"></label>
          </div>
          <div class="form-actions"><button class="btn btn-primary" type="submit">Guardar parcela</button></div>
        </form>
        <div style="margin-top:22px">${table(["PARCELA", "FINCA ID", "SUPERFICIE"], prows)}</div>
      </div>
    </div>`;
}

function clientsView() {
  if (session.rol !== "admin") return dashboardView();

  const filas = cache.clientes.map((c) => {
    const chips = (c.fincas || []).map((f) =>
      `<span class="pill violet" style="margin:2px 3px 2px 0">${safe(f.nombre || "Finca " + f.numero)} <button class="copy-btn" style="padding:1px 6px;margin-left:6px" data-unassign="${f.id}" title="Quitar esta finca">×</button></span>`
    ).join("") || '<span class="pill gray">Sin fincas</span>';
    return `<tr><td><b>${safe(c.nombre_completo)}</b></td><td>${safe(c.username)}</td><td><span class="pill ${c.activo ? "violet" : "gray"}">${c.activo ? "Activo" : "Inactivo"}</span></td><td style="white-space:normal">${chips}</td></tr>`;
  });

  const opcionesProductor = cache.clientes.length
    ? cache.clientes.map((c) => `<option value="${c.id}">${safe(c.nombre_completo)} (${safe(c.username)})</option>`).join("")
    : '<option value="">No hay productores todavía</option>';

  const opcionesFinca = cache.fincas.length
    ? cache.fincas.map((f) => {
        const dueno = cache.clientes.find((c) => c.id === f.usuario_id);
        const estado = dueno ? `asignada a ${dueno.nombre_completo}` : "sin asignar";
        return `<option value="${f.id}">${safe(f.nombre || "Finca " + f.numero)} (#${f.id}) · ${safe(estado)}</option>`;
      }).join("")
    : '<option value="">No hay fincas todavía</option>';

  const faltantes = [];
  if (!cache.clientes.length) faltantes.push("todavía no hay productores registrados");
  if (!cache.fincas.length) faltantes.push("todavía no hay fincas creadas");

  return `${pageHead("PRODUCTORES", "Clientes y fincas", "Asigna a cada productor las fincas que podrá ver en su portal.",
      '<button class="btn btn-soft" data-go="users" type="button">＋ Crear cuenta</button>')}
    <div class="panel">
      <div class="panel-head"><div><h3>Asignar finca a un productor</h3><p>Elige el productor y la finca. El productor solo verá las fincas que le asignes aquí.</p></div></div>
      ${faltantes.length ? `<div class="notice-inline">Para asignar necesitas que existan ${safe(faltantes.join(" y "))}. Usa los botones de abajo para crearlos.</div>` : ""}
      <form id="assign-farm-form">
        <div class="form-grid">
          <label class="field">Productor<select name="usuario_id" required>${opcionesProductor}</select></label>
          <label class="field">Finca<select name="finca_id" required>${opcionesFinca}</select></label>
        </div>
        <div class="notice-inline">Los productores pueden registrarse solos en el <a href="/portal" target="_blank" rel="noopener">portal del productor</a>, o los puedes crear tú en <b>Cuentas y usuarios</b>.</div>
        <div class="form-actions">
          <button class="btn btn-soft" data-go="users" type="button">Crear cuenta</button>
          <button class="btn btn-soft" data-go="farms" type="button">Crear finca</button>
          <button class="btn btn-primary" type="submit">Asignar finca</button>
        </div>
      </form>
    </div>
    <div class="panel">
      <div class="panel-head"><div><h3>Productores registrados</h3><p>Cada productor con sus fincas asignadas.</p></div><span class="pill violet">${cache.clientes.length} productores</span></div>
      ${table(["NOMBRE", "USUARIO", "ESTADO", "FINCAS ASIGNADAS"], filas, "Todavía no hay productores registrados. Crea uno en «Cuentas y usuarios».")}
    </div>`;
}

function usersView() {
  if (session.rol !== "admin") return dashboardView();

  const filas = cache.usuarios.map((u) =>
    `<tr><td><b>${safe(u.nombre_completo)}</b></td><td>${safe(u.username)}</td><td><span class="pill ${u.rol === "admin" ? "rose" : (u.rol === "cliente" ? "violet" : "orange")}">${safe(ROLE_LABEL[u.rol] || u.rol)}</span></td><td><span class="pill ${u.activo ? "violet" : "gray"}">${u.activo ? "Activo" : "Inactivo"}</span></td></tr>`
  );

  return `${pageHead("USUARIOS", "Cuentas y usuarios", "Crea cuentas de productor, encargado o trabajador sin usar códigos.")}
    <div class="panel">
      <div class="panel-head"><div><h3>Registrar una cuenta nueva</h3><p>Elige el rol. El administrador principal no se puede crear desde aquí.</p></div></div>
      <form id="create-user-form">
        <div class="form-grid">
          <label class="field">Nombre completo<input name="nombre_completo" placeholder="Ej. Julio Mamani" required maxlength="100"></label>
          <label class="field">Nombre de usuario<input name="username" placeholder="Ej. julio" required minlength="3" maxlength="50"></label>
          <label class="field">Contraseña<input name="password" type="password" placeholder="Mínimo 6 caracteres" required minlength="6"></label>
          <label class="field">Rol<select name="rol">
            <option value="cliente">Productor / Cliente</option>
            <option value="encargado">Encargado</option>
            <option value="trabajador">Trabajador</option>
          </select></label>
        </div>
        <div class="notice-inline">Las cuentas de <b>productor</b> entran por el portal del productor (<a href="/portal" target="_blank" rel="noopener">/portal</a>). Encargados y trabajadores entran por este panel.</div>
        <div class="form-actions"><button class="btn btn-primary" type="submit">Crear cuenta</button></div>
      </form>
    </div>
    <div class="panel">
      <div class="panel-head"><div><h3>Usuarios del sistema</h3><p>Todas las cuentas registradas y su rol.</p></div><span class="pill violet">${cache.usuarios.length} usuarios</span></div>
      ${table(["NOMBRE", "USUARIO", "ROL", "ESTADO"], filas, "Todavía no hay usuarios.")}
    </div>`;
}

function inviteRows() {
  return cache.invitaciones.map((i) =>
    `<tr><td><b>${safe(i.codigo)}</b></td><td><span class="pill violet">${safe(i.rol)}</span></td><td>${safe(String(i.expira_en).replace("T", " ").slice(0, 16))}</td><td><span class="pill ${i.usado ? "gray" : (i.activo ? "violet" : "rose")}">${i.usado ? "Usado" : (i.activo ? "Disponible" : "Inactivo")}</span></td></tr>`
  ).join("") || `<tr><td colspan="4" class="empty">Todavía no hay invitaciones.</td></tr>`;
}

function invitesView() {
  if (session.rol !== "admin") return dashboardView();
  return `${pageHead("PERSONAL", "Invitaciones", "Genera códigos de un solo uso para encargados y trabajadores.")}
    <div class="panel">
      <div class="panel-head"><div><h3>Crear invitación</h3><p>El código vence según los días que indiques y solo sirve una vez.</p></div></div>
      <form id="create-invite-form">
        <div class="form-grid">
          <label class="field">Rol<select name="rol"><option value="encargado">Encargado</option><option value="trabajador">Trabajador</option></select></label>
          <label class="field">Días de vigencia<input name="dias_vigencia" type="number" min="1" max="90" value="7" required></label>
        </div>
        <div class="form-actions"><button class="btn btn-primary" type="submit">Generar código</button></div>
      </form>
      <div id="invite-result"></div>
    </div>
    <div class="panel">
      <div class="panel-head"><div><h3>Historial de invitaciones</h3><p>Códigos generados y su estado.</p></div></div>
      <div class="table-wrap"><table><thead><tr><th>CÓDIGO</th><th>ROL</th><th>VENCE</th><th>ESTADO</th></tr></thead><tbody id="invite-table-body">${inviteRows()}</tbody></table></div>
    </div>`;
}

/* ---------------------------------------------------------- formularios */
function formObject(form) {
  const o = Object.fromEntries(new FormData(form).entries());
  Object.keys(o).forEach((k) => { if (o[k] === "") o[k] = null; });
  return o;
}

function num(o, keys) {
  keys.forEach((k) => { if (o[k] !== null && o[k] !== undefined) o[k] = Number(o[k]); });
  return o;
}

function bindPage() {
  $$("[data-go]").forEach((b) => b.addEventListener("click", () => navigate(b.dataset.go)));
  $$("[data-scroll]").forEach((b) => b.addEventListener("click", () => {
    const el = $("#" + b.dataset.scroll);
    if (el) el.scrollIntoView({ behavior: "smooth" });
  }));

  const bind = (id, url, transform = (x) => x, success = "Registro guardado correctamente.") => {
    const f = $("#" + id);
    if (!f) return;
    f.addEventListener("submit", async (e) => {
      e.preventDefault();
      const btn = f.querySelector('button[type="submit"]');
      if (btn) btn.disabled = true;
      try {
        await request(url, { method: "POST", body: JSON.stringify(transform(formObject(f))) });
        toast(success);
        await loadData();
        navigate(currentPage);
      } catch (err) {
        toast(err.message, true);
        if (btn) btn.disabled = false;
      }
    });
  };

  bind("create-lot-form", "/inventario/lotes",
    (o) => ({ ...o, finca_id: o.finca_id ? Number(o.finca_id) : null }),
    "Lote registrado. Ahora puedes registrar su entrada en el Kardex.");

  bind("create-harvest-form", "/kardex/cosechas",
    (o) => ({ ...o, ...num(o, ["cosechero_id", "finca_id", "parcela_id", "kg", "monto_bs"]) }),
    "Cosecha registrada correctamente.");

  bind("create-movement-form", "/kardex/movimientos", (o) => {
    const stock = cache.movimientos.reduce((s, m) => s + Number(m.entrada_kg || 0) - Number(m.salida_kg || 0), 0);
    const entrada = Number(o.entrada_kg || 0);
    const salida = Number(o.salida_kg || 0);
    return { ...o, ...num(o, ["lote_id", "finca_id", "entrada_kg", "salida_kg"]), saldo_kg: stock + entrada - salida };
  }, "Movimiento registrado correctamente.");

  bind("create-worker-form", "/cosecheros", (o) => o, "Cosechero registrado.");
  bind("create-farm-form", "/inventario/fincas", (o) => ({ ...o, numero: Number(o.numero) }), "Finca registrada.");
  bind("create-plot-form", "/inventario/parcelas",
    (o) => ({ ...o, ...num(o, ["finca_id", "numero", "superficie_ha"]) }), "Parcela registrada.");

  bind("create-user-form", "/auth/usuarios", (o) => o, "Cuenta creada correctamente.");

  // Asignar finca a un productor
  const assignForm = $("#assign-farm-form");
  if (assignForm) {
    assignForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const o = formObject(assignForm);
      try {
        await request("/portal/api/admin/asignar-finca", {
          method: "POST",
          body: JSON.stringify({ finca_id: Number(o.finca_id), usuario_id: Number(o.usuario_id) })
        });
        toast("Finca asignada al productor.");
        await loadData();
        navigate("clients");
      } catch (err) { toast(err.message, true); }
    });
  }

  // Quitar una finca a un productor
  $$("[data-unassign]").forEach((b) => b.addEventListener("click", async () => {
    const fincaId = Number(b.dataset.unassign);
    if (!window.confirm("¿Quitar esta finca al productor?")) return;
    try {
      await request("/portal/api/admin/asignar-finca", {
        method: "POST",
        body: JSON.stringify({ finca_id: fincaId, usuario_id: null })
      });
      toast("Finca quitada al productor.");
      await loadData();
      navigate("clients");
    } catch (err) { toast(err.message, true); }
  }));

  // Crear invitación (se conserva el código en pantalla)
  const inviteForm = $("#create-invite-form");
  if (inviteForm) {
    inviteForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const o = formObject(inviteForm);
      try {
        const data = await request("/auth/invitaciones", {
          method: "POST",
          body: JSON.stringify({ rol: o.rol, dias_vigencia: Number(o.dias_vigencia) })
        });
        $("#invite-result").innerHTML =
          `<div class="code-box"><div><div style="font-size:11px;color:var(--muted)">Código para <b>${safe(data.rol)}</b></div><code>${safe(data.codigo)}</code></div><button class="copy-btn" data-copy="${safe(data.codigo)}" type="button">Copiar</button></div>`;
        toast("Código de invitación creado.");
        await loadData();
        const tbody = $("#invite-table-body");
        if (tbody) tbody.innerHTML = inviteRows();
        bindCopies();
      } catch (err) { toast(err.message, true); }
    });
  }

  bindCopies();
}

function bindCopies() {
  $$("[data-copy]").forEach((b) => b.addEventListener("click", async () => {
    const code = b.dataset.copy;
    try {
      await navigator.clipboard.writeText(code);
      toast("Código copiado: " + code);
    } catch (e) {
      toast("Código: " + code);
    }
  }));
}

/* ---------------------------------------------------------- eventos fijos */
$("#theme-toggle").addEventListener("click", () => {
  const actual = document.documentElement.getAttribute("data-theme");
  applyTheme(actual === "dark" ? "light" : "dark");
});

$$(".tab").forEach((b) => b.addEventListener("click", () => showAuth(b.dataset.authTab)));

$("#login-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const o = formObject(e.currentTarget);
  try {
    const data = await request("/auth/login", { method: "POST", body: JSON.stringify(o) });
    if (data.usuario.rol === "cliente") {
      toast("Tu cuenta es de productor. Entra por el portal del productor.", true);
      return;
    }
    token = data.access_token;
    session = data.usuario;
    localStorage.setItem(TOKEN_KEY, token);
    localStorage.setItem(USER_KEY, JSON.stringify(session));
    showApp();
  } catch (err) { toast(err.message, true); }
});

$("#invite-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const o = formObject(e.currentTarget);
  if (String(o.password || "").length < 6) { toast("La contraseña debe tener al menos 6 caracteres.", true); return; }
  try {
    await request("/auth/register-staff", { method: "POST", body: JSON.stringify(o) });
    toast("Cuenta creada. Ahora puedes iniciar sesión.");
    e.currentTarget.reset();
    showAuth("login");
    $("#login-form [name=username]").value = o.username;
  } catch (err) { toast(err.message, true); }
});

$("#logout-btn").addEventListener("click", () => logout());
$("#menu-toggle").addEventListener("click", () => $("#sidebar").classList.toggle("open"));

/* ---------------------------------------------------------- arranque */
(async function init() {
  initTheme();
  const savedToken = localStorage.getItem(TOKEN_KEY);
  const savedUser = localStorage.getItem(USER_KEY);
  if (savedToken && savedUser) {
    token = savedToken;
    try {
      session = JSON.parse(savedUser);
      const me = await request("/auth/me");
      if (me.rol === "cliente") { logout(true); showAuth("login"); return; }
      session = me;
      localStorage.setItem(USER_KEY, JSON.stringify(me));
      showApp();
      return;
    } catch (e) { /* token inválido: se muestra el login */ }
  }
  showAuth("login");
})();
