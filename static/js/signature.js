document.addEventListener("DOMContentLoaded", function () {
    const canvas = document.getElementById("signature-canvas");
    const signatureInput = document.getElementById("id_signature");
    const clearButton = document.getElementById("clear-signature");
    const changeButton = document.getElementById("btn-change-signature");
    const savedBlock = document.getElementById("saved-signature-block");
    const padBlock = document.getElementById("signature-pad-block");
    const form = document.getElementById("os-form");

    if (!canvas) return;

    const signaturePad = new SignaturePad(canvas, {
        backgroundColor: 'rgba(255, 255, 255, 0)'
    });

    // Função para recalcular a dimensão real do canvas na tela
    function resizeCanvas() {
        if (!padBlock || padBlock.style.display === "none") return;

        const ratio = Math.max(window.devicePixelRatio || 1, 1);
        canvas.width = canvas.offsetWidth * ratio;
        canvas.height = canvas.offsetHeight * ratio;
        
        const ctx = canvas.getContext("2d");
        ctx.scale(ratio, ratio);
        signaturePad.clear(); // Limpa a memória de traços ao redimensionar
    }

    window.addEventListener("resize", resizeCanvas);

    // Clique no botão "Alterar Assinatura"
    if (changeButton) {
        changeButton.addEventListener("click", function (e) {
            e.preventDefault();

            // 1. Alterna a exibição dos blocos
            if (savedBlock) savedBlock.style.display = "none";
            if (padBlock) padBlock.style.display = "block";

            // 2. Limpa o valor antigo do input do Django
            if (signatureInput) signatureInput.value = "";
            signaturePad.clear();

            // 3. Força o navegador a calcular o layout antes de redimensionar o canvas
            requestAnimationFrame(function () {
                resizeCanvas();
            });
        });
    }

    // Clique no botão "Limpar"
    if (clearButton) {
        clearButton.addEventListener("click", function (e) {
            e.preventDefault();
            signaturePad.clear();
            if (signatureInput) signatureInput.value = "";
        });
    }

    // Ao submeter o formulário
    if (form) {
        form.addEventListener("submit", function () {
            // Se a área de desenho estive ativa/visível
            if (padBlock && padBlock.style.display !== "none") {
                if (!signaturePad.isEmpty()) {
                    if (signatureInput) {
                        signatureInput.value = signaturePad.toDataURL("image/png");
                    }
                } else {
                    if (signatureInput) {
                        signatureInput.value = "";
                    }
                }
            }
        });
    }
});