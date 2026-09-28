document.addEventListener("DOMContentLoaded", function () {

    function calculateTotalHours(row) {
        const start = row.querySelector("input[name$='-start']");
        const stop = row.querySelector("input[name$='-stop']");
        const total = row.querySelector("input[name$='-total_hours']");
        if (!start || !stop || !total || !start.value || !stop.value) return;

        const [startHour, startMinute] = start.value.split(':').map(Number);
        const [stopHour, stopMinute] = stop.value.split(':').map(Number);
        let minutes = (stopHour * 60 + stopMinute) - (startHour * 60 + startMinute);
        if (minutes < 0) minutes += 24 * 60;

        const hours = Math.floor(minutes / 60).toString().padStart(2, '0');
        const remainder = (minutes % 60).toString().padStart(2, '0');
        total.value = `${hours}:${remainder}`;
    }

    function bindTimeCalculation(container) {
        container.querySelectorAll('.formset-row').forEach(calculateTotalHours);
        container.addEventListener('input', function (event) {
            if (event.target.matches("input[name$='-start'], input[name$='-stop']")) {
                calculateTotalHours(event.target.closest('.formset-row'));
            }
        });
        container.addEventListener('change', function (event) {
            if (event.target.matches("input[name$='-start'], input[name$='-stop']")) {
                calculateTotalHours(event.target.closest('.formset-row'));
            }
        });
    }

    function setupFormset(addBtnId, containerId, templateId, prefix) {
        const addBtn = document.getElementById(addBtnId);
        const container = document.getElementById(containerId);
        const template = document.getElementById(templateId);
        const totalFormsInput = document.getElementById(`id_${prefix}-TOTAL_FORMS`);

        if (!addBtn || !container || !template || !totalFormsInput) return;

        // 1. ADICIONAR NOVO FORMULÁRIO
        addBtn.addEventListener("click", function () {
            // Pega o total atual como índice para a nova linha
            let formIdx = parseInt(totalFormsInput.value);
            
            // Pega o HTML do template e substitui __prefix__ pelo valor do índice atual
            let newRowHtml = template.querySelector("tbody").innerHTML;
            newRowHtml = newRowHtml.replace(/__prefix__/g, formIdx);

            container.insertAdjacentHTML("beforeend", newRowHtml);

            // Incrementa o contador do TOTAL_FORMS
            totalFormsInput.value = formIdx + 1;
        });

        // 2. REMOVER FORMULÁRIO
        container.addEventListener("click", function (event) {
            const removeBtn = event.target.closest(".remove-form");
            if (!removeBtn) return;

            const row = removeBtn.closest(".formset-row");
            const deleteCheckbox = row.querySelector("input[type='checkbox'][name$='-DELETE']");

            // SE A LINHA VEIO DO BANCO DE DADOS (Tem o checkbox de DELETE ativo/existente):
            if (deleteCheckbox) {
                deleteCheckbox.checked = true; // Marca para o Django deletar no banco
                row.style.display = "none";    // Oculta da visão do usuário
            } 
            // SE É UMA LINHA NOVA (Adicionada agora via JavaScript):
            else {
                // Em vez de deletar o DOM e reindexar (o que quebra os nomes dos inputs),
                // limpamos os campos e ocultamos a linha da tela.
                row.querySelectorAll("input, select, textarea").forEach((input) => {
                    if (input.type === "checkbox" || input.type === "radio") {
                        input.checked = false;
                    } else {
                        input.value = "";
                    }
                });
                row.style.display = "none";
            }
        });
    }

    // Inicializa Peças e Tempo de Serviço
    setupFormset("add-part-btn", "parts-container", "empty-part-template", "service_order_part");
    setupFormset("add-time-btn", "time-container", "empty-time-template", "time_service");

    const timeContainer = document.getElementById('time-container');
    if (timeContainer) bindTimeCalculation(timeContainer);
});
