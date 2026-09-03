// static/js/login.js

// --- UTILIDADES: Obtener token CSRF del meta tag ---
function getCsrfToken() {
    const meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.content : '';
}

// --- VALIDACIÓN DE CONTRASEÑA EN TIEMPO REAL ---
async function validatePasswordStrength(passwordInput) {
    const password = passwordInput.value;
    const containerId = passwordInput.id === 'registerPassword'
        ? 'passwordStrengthRegister'
        : 'passwordStrengthLogin';
    const container = document.getElementById(containerId);

    if (!container) return;
    if (!password) { container.innerHTML = ''; return; }

    try {
        const response = await fetch('/api/validate-password', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCsrfToken()
            },
            body: JSON.stringify({ password })
        });
        const data = await response.json();

        let colorClass, iconClass;
        switch (data.strength) {
            case 'Muy Débil':
            case 'Débil':
                colorClass = 'bg-red-100 border-red-300';
                iconClass  = 'text-red-600';
                break;
            case 'Media':
                colorClass = 'bg-yellow-100 border-yellow-300';
                iconClass  = 'text-yellow-600';
                break;
            case 'Fuerte':
            case 'Muy Fuerte':
                colorClass = 'bg-green-100 border-green-300';
                iconClass  = 'text-green-600';
                break;
            default:
                colorClass = 'bg-gray-100 border-gray-300';
                iconClass  = 'text-gray-600';
        }

        let html = `
            <div class="mt-2 p-3 rounded border ${colorClass}">
                <div class="flex items-center justify-between mb-2">
                    <span class="text-xs font-bold ${iconClass}">
                        <i class="fas fa-shield-alt"></i> Fortaleza: ${data.strength}
                    </span>
                    <span class="text-xs font-bold text-gray-600">${data.score}/100</span>
                </div>
                <div class="w-full bg-gray-300 rounded-full h-2">
                    <div class="bg-gradient-to-r from-red-500 to-green-500 h-2 rounded-full transition-all duration-300"
                         style="width: ${data.score}%"></div>
                </div>
                <div class="flex items-center mt-2 text-xs">
                    <span class="text-gray-600">Complejidad: ${data.complexity}/4</span>
                </div>`;

        if (data.issues && data.issues.length > 0) {
            html += '<div class="mt-2 text-xs text-red-700"><strong>Problemas:</strong><ul class="list-disc list-inside">';
            data.issues.forEach(issue => { html += `<li>${issue}</li>`; });
            html += '</ul></div>';
        }
        if (data.suggestions && data.suggestions.length > 0) {
            html += '<div class="mt-2 text-xs text-blue-700"><strong>💡 Sugerencias:</strong><ul class="list-disc list-inside">';
            data.suggestions.forEach(s => { html += `<li>${s}</li>`; });
            html += '</ul></div>';
        }
        html += '</div>';
        container.innerHTML = html;

    } catch (error) {
        console.error('Error validando contraseña:', error);
    }
}

// -- GENERAR CONTRASEÑA SEGURA --
async function generateSecurePassword() {
    try {
        const response = await fetch('/api/generate-password?type=secure');
        const data = await response.json();

        const passwordInput = document.getElementById('registerPassword');
        passwordInput.value = data.password;

        const container = document.getElementById('passwordStrengthRegister');
        if (container) {
            container.innerHTML = `
                <div class="mt-2 p-3 rounded border bg-green-100 border-green-300">
                    <div class="flex items-center gap-2">
                        <i class="fas fa-check-circle text-green-600"></i>
                        <span class="text-sm font-bold text-green-700">
                            Contraseña generada: ${data.strength} (${data.score}/100)
                        </span>
                    </div>
                </div>`;
        }
        validatePasswordStrength(passwordInput);

    } catch (error) {
        console.error('Error generando contraseña:', error);
    }
}

// -- TOGGLE CONTRASEÑA (LOGIN) --
function togglePasswordVisibility() {
    const input = document.getElementById('password');
    const icon  = document.getElementById('passwordIcon');
    const isHidden = input.type === 'password';
    input.type = isHidden ? 'text' : 'password';
    icon.classList.toggle('fa-eye',      !isHidden);
    icon.classList.toggle('fa-eye-slash', isHidden);
}

// -- TOGGLE CONTRASEÑA (REGISTRO) --
function toggleRegPasswordVisibility() {
    const input = document.getElementById('registerPassword');
    const icon  = document.getElementById('registerPasswordIcon');
    const isHidden = input.type === 'password';
    input.type = isHidden ? 'text' : 'password';
    icon.classList.toggle('fa-eye',      !isHidden);
    icon.classList.toggle('fa-eye-slash', isHidden);
}

// -- TOGGLE TOKEN (REGISTRO) --
function toggleRegTokenVisibility() {
    const input = document.getElementById('registerToken');
    const icon  = document.getElementById('registerTokenIcon');
    const isHidden = input.type === 'password';
    input.type = isHidden ? 'text' : 'password';
    icon.classList.toggle('fa-eye',      !isHidden);
    icon.classList.toggle('fa-eye-slash', isHidden);
}

// -- LOGIN --
document.getElementById('loginForm').addEventListener('submit', async (e) => {
    e.preventDefault();

    const btn      = document.getElementById('btnSubmit');
    const btnText  = btn.querySelector('span');
    const errorDiv = document.getElementById('errorMessage');

    // UI: estado de carga
    btnText.innerText = 'VALIDANDO...';
    btn.disabled = true;
    btn.classList.add('opacity-75');
    errorDiv.classList.add('hidden');

    // -- Leer valores directamente del DOM --
    // El backend espera request.form con campos 'usuario' y 'password'
    const formData = new FormData();
    formData.append('usuario',  document.getElementById('usuario').value.trim());
    formData.append('password', document.getElementById('password').value);

    try {
        const res = await fetch('/login', {
            method: 'POST',
            headers: {
                // FormData NO lleva Content-Type manual (el browser lo pone con boundary)
                // Solo agregamos el token CSRF
                'X-CSRFToken': getCsrfToken()
            },
            body: formData
        });
        
        if (res.status === 429) {
            let msg = "Demasiados intentos. Espera antes de intentarlo de nuevo.";
            try {
                const errData = await res.json();
                if (errData.message) msg = errData.message;
            } catch (_) { /* si el body no es JSON, usar el mensaje por defecto */ }
            document.getElementById("errorText").textContent = msg;
            errorDiv.classList.remove("hidden");
            btnText.innerText = "ENTRAR";
            btn.disabled = false;
            btn.classList.remove("opacity-75");
            return;
        }

        const data = await res.json();

        if (data.success) {
            window.location.href = data.redirect;
        } else {
            throw new Error(data.message || 'Credenciales incorrectas.');
        }
    } catch (error) {
        document.getElementById('errorText').textContent =
            error.message || 'Error de conexión. Intenta de nuevo.';
        errorDiv.classList.remove('hidden');
        btnText.innerText = 'ENTRAR';
        btn.disabled = false;
        btn.classList.remove('opacity-75');
    }
});

// -- REGISTRO --
const regModal = document.getElementById('registerModal');

function openRegisterModal() {
    regModal.classList.remove('hidden');
    setTimeout(() => {
        regModal.children[0].classList.remove('scale-95', 'opacity-0');
        regModal.children[0].classList.add('scale-100', 'opacity-100');
    }, 10);
}

function closeRegisterModal() {
    regModal.children[0].classList.remove('scale-100', 'opacity-100');
    regModal.children[0].classList.add('scale-95', 'opacity-0');
    setTimeout(() => regModal.classList.add('hidden'), 150);
    document.getElementById('registerForm').reset();
    document.getElementById('regErrorMsg').classList.add('hidden');
    document.getElementById('regSuccessMsg').classList.add('hidden');
    document.getElementById('passwordStrengthRegister').innerHTML = '';
}

// Validación en tiempo real al escribir la contraseña
document.addEventListener('DOMContentLoaded', () => {
    const regPwdInput = document.getElementById('registerPassword');
    if (regPwdInput) {
        regPwdInput.addEventListener('input', function () {
            validatePasswordStrength(this);
        });
    }
});

document.getElementById('registerForm').addEventListener('submit', async (e) => {
    e.preventDefault();

    const btn        = document.getElementById('btnRegister');
    const originalTx = btn.innerText;
    const errorMsg   = document.getElementById('regErrorMsg');
    const successMsg = document.getElementById('regSuccessMsg');
    const password   = document.getElementById('registerPassword').value;

    btn.innerText = 'CREANDO...';
    btn.disabled  = true;
    errorMsg.classList.add('hidden');
    successMsg.classList.add('hidden');

    // Validar fortaleza antes de enviar
    try {
        const validation = await fetch('/api/validate-password', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCsrfToken()
            },
            body: JSON.stringify({ password })
        }).then(r => r.json());

        if (!validation.is_valid || validation.score < 60) {
            errorMsg.textContent =
                `Contraseña insegura. Puntuación: ${validation.score}/100. ` +
                (validation.suggestions || []).join(' ');
            errorMsg.classList.remove('hidden');
            btn.innerText = originalTx;
            btn.disabled  = false;
            return;
        }
    } catch (err) {
        console.error('Error validando contraseña:', err);
    }

    // Enviar formulario como FormData (el backend usa request.form)
    const formData = new FormData(e.target);

    try {
        const res  = await fetch('/api/register', {
            method: 'POST',
            headers: { 'X-CSRFToken': getCsrfToken() },
            body: formData
        });
        const data = await res.json();

        if (data.success) {
            successMsg.textContent = data.message;
            successMsg.classList.remove('hidden');
            document.getElementById('registerForm').reset();
            setTimeout(() => closeRegisterModal(), 2000);
        } else {
            errorMsg.textContent = data.message || 'Error al registrar usuario.';
            errorMsg.classList.remove('hidden');
        }
    } catch (error) {
        errorMsg.textContent = 'Error al conectar con el servidor.';
        errorMsg.classList.remove('hidden');
    } finally {
        btn.innerText = originalTx;
        btn.disabled  = false;
    }
});