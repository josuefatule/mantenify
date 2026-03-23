// ======================================================================
// SISTEMA GLOBAL PARA MODALES ANIDADOS (Bootstrap 5 no lo soporta nativo)
// ======================================================================
let previousModalUrl = null;

// ======================================================================
// ABRIR MODAL DESDE URL (con soporte para "chain modals")
// ======================================================================
async function openModal(url, fromModal = false) {
    const modalEl = document.getElementById("mainModal");
    const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
    const modalContent = document.getElementById("modalContent");

    // Si ya hay un modal abierto → guardamos su URL (modal chaining)
    if (modalEl.classList.contains("show") && !fromModal) {
        previousModalUrl = modalEl.getAttribute("data-current-url");
    }

    modalEl.setAttribute("data-current-url", url);
    modalContent.innerHTML = `<div class="p-5 text-center">Cargando...</div>`;

    const response = await fetch(url);
    const content = await response.text();

    modalContent.innerHTML = content;
    modal.show();

    // Reactivar handlers dinámicos
    initModalEnhancements();
}


// ======================================================================
// REABRIR MODAL ANTERIOR AL CERRAR EL ACTUAL (fix del backdrop congelado)
// ======================================================================
document.addEventListener("hidden.bs.modal", function () {
    const modalEl = document.getElementById("mainModal");

    if (previousModalUrl) {
        const reopenUrl = previousModalUrl;
        previousModalUrl = null;
        openModal(reopenUrl, true);
    }
});


// ======================================================================
// SUBMIT AJAX EN FORMULARIOS DENTRO DEL MODAL
// ======================================================================
async function submitForm(event, formElement) {
    event.preventDefault();

    const url = formElement.action;
    const formData = new FormData(formElement);

    const response = await fetch(url, {
        method: "POST",
        body: formData
    });

    if (response.redirected) {
        window.location.href = response.url;
    } else {
        const html = await response.text();
        document.getElementById("modalContent").innerHTML = html;
        initModalEnhancements();
    }
}


// ======================================================================
// SISTEMA UNIFICADO DE HANDLERS PARA TODOS LOS MODALES
// ======================================================================
function initModalEnhancements() {

    // ---------------------------------------------------
    // 1) SOLICITUDES → Proyecto -> Unidad -> Activo
    // ---------------------------------------------------
    const sProyecto = document.getElementById("selectProyecto");
    const sUnidad = document.getElementById("selectUnidad");
    const sActivo = document.getElementById("selectActivo");

    if (sProyecto && sUnidad) {
        sProyecto.onchange = async function () {
            const proyectoId = this.value;
            if (!proyectoId) {
                sUnidad.innerHTML = "<option value=''>Seleccione proyecto</option>";
                if (sActivo) sActivo.innerHTML = "<option value=''>Opcional</option>";
                return;
            }

            sUnidad.innerHTML = "<option>Cargando...</option>";
            const res = await fetch(`/solicitudes/ajax/unidades/${proyectoId}`);
            const data = await res.json();

            sUnidad.innerHTML = "<option value=''>Seleccione...</option>";
            data.forEach(u => {
                sUnidad.innerHTML += `<option value="${u.id}">${u.nombre}</option>`;
            });

            if (sActivo) sActivo.innerHTML = "<option value=''>Opcional</option>";
        };

        if (sActivo && sUnidad) {
            sUnidad.onchange = async function () {
                const unidadId = this.value;

                sActivo.innerHTML = "<option>Cargando...</option>";
                const res = await fetch(`/solicitudes/ajax/activos/${unidadId}`);
                const data = await res.json();

                sActivo.innerHTML = "<option value=''>Opcional</option>";
                data.forEach(a => {
                    sActivo.innerHTML += `<option value="${a.id}">${a.nombre}</option>`;
                });
            };
        }
    }


    // ---------------------------------------------------
    // 2) FINANZAS → Proyecto -> Etapa
    // ---------------------------------------------------
    const fProyecto = document.getElementById("masivoProyecto");
    const fEtapa = document.getElementById("masivoEtapa");

    if (fProyecto && fEtapa) {
        fProyecto.onchange = async function () {
            const proyectoId = this.value;

            if (!proyectoId) {
                fEtapa.innerHTML = "<option value=''>Seleccione un proyecto primero</option>";
                return;
            }

            fEtapa.innerHTML = "<option>Cargando...</option>";

            try {
                const res = await fetch(`/finanzas/ajax/etapas/${proyectoId}`);
                const data = await res.json();

                fEtapa.innerHTML = "<option value=''>Seleccione...</option>";
                data.forEach(e => {
                    fEtapa.innerHTML += `<option value="${e.id}">${e.nombre}</option>`;
                });

            } catch (error) {
                console.error("Error cargando etapas:", error);
                fEtapa.innerHTML = "<option value=''>Error cargando etapas</option>";
            }
        };
    }


    // ---------------------------------------------------
    // 3) PERSONAS → Proyecto -> Unidad (desde persona)
    // ---------------------------------------------------
    const pProyecto = document.getElementById("selectProyectoPersona");
    const pUnidad = document.getElementById("selectUnidadPersona");

    if (pProyecto && pUnidad) {
        pProyecto.onchange = async function () {
            const proyectoId = this.value;

            if (!proyectoId) {
                pUnidad.innerHTML = "<option value=''>Seleccione un proyecto</option>";
                return;
            }

            pUnidad.innerHTML = "<option>Cargando...</option>";

            const res = await fetch(`/ajax/unidades/${proyectoId}`);
            const data = await res.json();

            pUnidad.innerHTML = "<option value=''>Seleccione...</option>";
            data.forEach(u => {
                pUnidad.innerHTML += `<option value="${u.id}">${u.nombre}</option>`;
            });
        };
    }
}
