document.addEventListener("DOMContentLoaded", function () {

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
    setupFormset("add-part-btn", "parts-container", "empty-part-template", "parts_useds");
    setupFormset("add-time-btn", "time-container", "empty-time-template", "time_service");
});