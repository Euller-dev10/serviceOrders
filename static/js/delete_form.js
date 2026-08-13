$(document).ready(function() {

    // Função que verifica e esconde a lixeira se houver apenas 1 linha visível
    function updateDeleteButtons(containerSelector) {
        var visibleRows = $(containerSelector).find('tr.formset-row:visible');
        
        if (visibleRows.length <= 1) {
            // Esconde o botão de remover da única linha restante
            visibleRows.find('.remove-form').addClass('d-none');
        } else {
            // Mostra o botão de remover em todas se houver mais de 1 linha
            visibleRows.find('.remove-form').removeClass('d-none');
        }
    }

    // --- PEÇAS ---
    $('#add-part-btn').click(function() {
        var formIdx = $('#id_parts_useds-TOTAL_FORMS').val();
        var newRow = $('#empty-part-template table tbody').html().replace(/__prefix__/g, formIdx);
        $('#parts-container').append(newRow);
        $('#id_parts_useds-TOTAL_FORMS').val(parseInt(formIdx) + 1);
        
        // Atualiza estado das lixeiras
        updateDeleteButtons('#parts-container');
    });

    // --- TEMPO DE SERVIÇO ---
    $('#add-time-btn').click(function() {
        var formIdx = $('#id_time_service-TOTAL_FORMS').val();
        var newRow = $('#empty-time-template table tbody').html().replace(/__prefix__/g, formIdx);
        $('#time-container').append(newRow);
        $('#id_time_service-TOTAL_FORMS').val(parseInt(formIdx) + 1);
        
        // Atualiza estado das lixeiras
        updateDeleteButtons('#time-container');
    });

    // --- REMOVER LINHA ---
    $(document).on('click', '.remove-form', function() {
        var row = $(this).closest('tr');
        var container = row.closest('tbody'); // identifica qual tabela é (parts ou time)
        var deleteInput = row.find('input[type="checkbox"][name$="-DELETE"]');
        
        if (deleteInput.length > 0) {
            // Registro que veio do banco: marca DELETE e oculta
            deleteInput.prop('checked', true);
            row.hide();
        } else {
            // Linha criada dinamicamente: remove do DOM
            row.remove();
        }

        // Revalida a quantidade de linhas para esconder/exibir as lixeiras restantes
        updateDeleteButtons(container);
    });

    // Executa na inicialização da página
    updateDeleteButtons('#parts-container');
    updateDeleteButtons('#time-container');
});