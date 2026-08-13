document.addEventListener('DOMContentLoaded', function() {
    const searchInput = document.getElementById('searchScaleInput');
    
    // Só executa se o campo de busca existir na tela (se houver balanças)
    if (searchInput) {
        const scaleItems = document.querySelectorAll('.scale-item');
        const noResultsMessage = document.getElementById('noScaleResults');

        searchInput.addEventListener('input', function() {
            const searchTerm = searchInput.value.toLowerCase().trim();
            let hasVisibleItems = false;

            scaleItems.forEach(function(item) {
                const serieElement = item.querySelector('.balanca-serie');
                const serieText = serieElement.getAttribute('data-serie').toLowerCase();

                if (serieText.includes(searchTerm)) {
                    item.classList.remove('d-none'); // Exibe o card
                    hasVisibleItems = true;
                } else {
                    item.classList.add('d-none');    // Oculta o card
                }
            });

            // Gerencia a exibição do alerta de "Nenhum resultado"
            if (hasVisibleItems) {
                noResultsMessage.classList.add('d-none');
            } else {
                noResultsMessage.classList.remove('d-none');
            }
        });
    }
});