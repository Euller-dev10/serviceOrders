document.addEventListener("DOMContentLoaded", function () {
    const canvas = document.getElementById("signature-canvas");
    const signatureInput = document.getElementById("id_signature");
    const clearButton = document.getElementById("clear-signature");
    const form = document.getElementById("os-form");

    if (!canvas || !signatureInput) return;

    const signaturePad = new SignaturePad(canvas, {
        backgroundColor: 'rgba(255, 255, 255, 0)'
    });

    // Ajusta o tamanho do canvas mantendo a nitidez
    function resizeCanvas() {
        const ratio = Math.max(window.devicePixelRatio || 1, 1);
        const oldData = signaturePad.toData(); // Guarda traços atuais
        canvas.width = canvas.offsetWidth * ratio;
        canvas.height = canvas.offsetHeight * ratio;
        canvas.getContext("2d").scale(ratio, ratio);
        signaturePad.clear();
        signaturePad.fromData(oldData); // Restaura os traços após resize
    }

    window.addEventListener("resize", resizeCanvas);
    resizeCanvas();

    // Se já houver assinatura salva no input (edição), carrega no canvas
    if (signatureInput.value && signatureInput.value.trim() !== "") {
        signaturePad.fromDataURL(signatureInput.value);
    }

    // Botão de Limpar
    if (clearButton) {
        clearButton.addEventListener("click", function () {
            signaturePad.clear();
            signatureInput.value = "";
        });
    }

    // Antes de enviar o formulário
    if (form) {
        form.addEventListener("submit", function () {
            // Se o usuário desenhou algo novo, atualiza o input hidden
            if (!signaturePad.isEmpty()) {
                signatureInput.value = signaturePad.toDataURL();
            } 
            // Se o pad estiver limpo porque o usuário clicou em "Limpar", limpa a string
            else if (signaturePad.isEmpty() && signatureInput.value) {
                // Caso queira que ao limpar e salvar zere no banco:
                // signatureInput.value = ""; 
            }
        });
    }
});