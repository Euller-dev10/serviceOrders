document.addEventListener("DOMContentLoaded", function () {
    const canvas = document.getElementById("signature-canvas");
    const signatureInput = document.getElementById("id_signature");
    const clearButton = document.getElementById("clear-signature");
    const form = document.getElementById("os-form");

    if (canvas) {
        const signaturePad = new SignaturePad(canvas);

        // Função responsável por ajustar a resolução real do Canvas ao tamanho CSS
        function resizeCanvas() {
            const ratio = Math.max(window.devicePixelRatio || 1, 1);

            // Armazena os dados atuais caso a pessoa já tenha começado a desenhar
            const signatureData = signaturePad.toData();

            canvas.width = canvas.offsetWidth * ratio;
            canvas.height = canvas.offsetHeight * ratio;
            canvas.getContext("2d").scale(ratio, ratio);

            // Limpa o canvas e reescreve os dados para ajustar na nova orientação
            signaturePad.clear();
            if (signatureData.length > 0) {
                signaturePad.fromData(signatureData);
            }
        }

        // Executa o ajuste inicial
        resizeCanvas();

        // Recalcula o Canvas quando a tela muda de tamanho ou gira
        window.addEventListener("resize", resizeCanvas);
        window.addEventListener("orientationchange", function() {
            // Um pequeno delay garante que o navegador já recalculou a largura CSS
            setTimeout(resizeCanvas, 200);
        });

        if (clearButton) {
            clearButton.addEventListener("click", function () {
                signaturePad.clear();
                signatureInput.value = "";
            });
        }

        if (form) {
            form.addEventListener("submit", function () {
                if (!signaturePad.isEmpty()) {
                    signatureInput.value = signaturePad.toDataURL();
                }
            });
        }
    }
});