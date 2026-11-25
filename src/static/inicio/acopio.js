(() => {
  const nombres = { kg: "kg", unidad: "piezas", caja: "cajas" };
  const numero = new Intl.NumberFormat("es-BO", { maximumFractionDigits: 3 });
  const etiqueta = (unidad) => nombres[unidad] || "kg";
  const cantidad = (valor, unidad) => valor == null ? "—" : numero.format(valor) + " " + etiqueta(unidad);

  function comprobante(datos) {
    let dialog = document.getElementById("comprobante-recepcion");
    if (!dialog) {
      dialog = document.createElement("dialog");
      dialog.id = "comprobante-recepcion";
      dialog.setAttribute("aria-labelledby", "comprobante-titulo");
      dialog.innerHTML = '<article><h2 id="comprobante-titulo">Comprobante de recepción</h2><dl></dl></article>' +
        '<div class="comprobante-acciones"><button type="button">Cerrar</button><button type="button">Imprimir comprobante</button></div>';
      const [cerrar, imprimir] = dialog.querySelectorAll("button");
      cerrar.addEventListener("click", () => dialog.close());
      imprimir.addEventListener("click", () => window.print());
      dialog.addEventListener("close", () => document.body.classList.remove("imprimir-comprobante"));
      document.body.append(dialog);
    }
    const campos = [
      ["Recepción", "#" + datos.id], ["Fecha", datos.fecha_recepcion], ["Finca", datos.finca],
      ["Cosechero", datos.cosechero], ["Producto", datos.producto], ["Lote", datos.codigo_lote],
      ["Documento", datos.documento_recepcion], ["Recibida", cantidad(datos.recibida, datos.unidad)],
      ["Rechazada", cantidad(datos.rechazada, datos.unidad)], ["Aceptada", cantidad(datos.cantidad, datos.unidad)],
      ["Monto registrado (Bs)", datos.monto_bs == null ? null : numero.format(datos.monto_bs)],
      ["Motivo del rechazo", datos.motivo_rechazo],
      ["Medición adicional de la entrega", datos.cantidad_secundaria == null ? null :
        cantidad(datos.cantidad_secundaria, datos.unidad_secundaria)]
    ];
    const lista = dialog.querySelector("dl");
    lista.replaceChildren();
    for (const [titulo, valor] of campos) {
      if (valor == null || valor === "") continue;
      const fila = document.createElement("div");
      const term = document.createElement("dt");
      const detail = document.createElement("dd");
      term.textContent = titulo;
      detail.textContent = valor;
      fila.append(term, detail);
      lista.append(fila);
    }
    document.body.classList.add("imprimir-comprobante");
    dialog.showModal();
  }

  window.acopio = { etiqueta, cantidad, comprobante };
})();
