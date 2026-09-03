# password_security.py
"""
Módulo de Seguridad de Contraseñas
Proporciona validación y generación de contraseñas seguras y robustas.
"""

import re
import secrets
import string
from typing import Dict, List, Tuple

class PasswordValidator:
    """Validador de contraseñas con requisitos de seguridad mejorados"""
    
    # Requisitos de contraseña fortalecida
    MIN_LENGTH = 12  # Mínimo recomendado por NIST
    MAX_LENGTH = 128
    
    # Patrones de complejidad
    PATTERNS = {
        'lowercase': r'[a-z]',
        'uppercase': r'[A-Z]',
        'digits': r'\d',
        'special': r'[!@#$%^&*()_+\-=\[\]{};:\'",.<>?/`~|\\]',
        'common_weak': [
            'password', 'admin', '123456', 'qwerty', 'letmein',
            'welcome', 'monkey', 'dragon', 'master', '000000',
            'sunshine', 'shadow', 'ashley', 'bailey', 'passw0rd'
        ]
    }
    
    @staticmethod
    def validate_password(password: str) -> Dict[str, any]:
        """
        Valida una contraseña según criterios de seguridad mejorados.
        
        Args:
            password (str): Contraseña a validar
            
        Returns:
            Dict: {
                'is_valid': bool,
                'score': int (0-100),
                'issues': List[str],
                'suggestions': List[str],
                'strength': str ('Muy Débil' | 'Débil' | 'Media' | 'Fuerte' | 'Muy Fuerte')
            }
        """
        issues = []
        suggestions = []
        score = 0
        
        # 1. VALIDAR LONGITUD
        if len(password) < PasswordValidator.MIN_LENGTH:
            issues.append(f"Longitud insuficiente (mínimo {PasswordValidator.MIN_LENGTH} caracteres)")
            suggestions.append(f"Aumenta a {PasswordValidator.MIN_LENGTH} caracteres o más")
        elif len(password) >= PasswordValidator.MIN_LENGTH:
            score += 20
            
        if len(password) > PasswordValidator.MAX_LENGTH:
            issues.append(f"Contraseña demasiado larga (máximo {PasswordValidator.MAX_LENGTH} caracteres)")
        
        # 2. VALIDAR COMPLEJIDAD
        complexity_score = 0
        
        # Minúsculas
        if re.search(PasswordValidator.PATTERNS['lowercase'], password):
            complexity_score += 1
            score += 15
        else:
            suggestions.append("Añade letras minúsculas (a-z)")
        
        # Mayúsculas
        if re.search(PasswordValidator.PATTERNS['uppercase'], password):
            complexity_score += 1
            score += 15
        else:
            suggestions.append("Añade letras mayúsculas (A-Z)")
        
        # Dígitos
        if re.search(PasswordValidator.PATTERNS['digits'], password):
            complexity_score += 1
            score += 15
        else:
            suggestions.append("Añade números (0-9)")
        
        # Caracteres especiales
        if re.search(PasswordValidator.PATTERNS['special'], password):
            complexity_score += 1
            score += 15
        else:
            suggestions.append("Añade caracteres especiales (!@#$%^&* etc.)")
        
        if complexity_score < 4:
            issues.append(f"Complejidad insuficiente ({complexity_score}/4 tipos de caracteres)")
        
        # 3. RECHAZAR PATRONES DÉBILES COMUNES
        pwd_lower = password.lower()
        for weak_pattern in PasswordValidator.PATTERNS['common_weak']:
            if weak_pattern in pwd_lower:
                issues.append(f"Contiene patrón débil conocido: '{weak_pattern}'")
                suggestions.append("Evita contraseñas comunes o palabras del diccionario")
                score -= 20
                break
        
        # 4. DETECTAR SECUENCIAS Y REPETICIONES
        if PasswordValidator._has_sequential_chars(password):
            issues.append("Contiene caracteres secuenciales (ej: abc, 123)")
            suggestions.append("Evita secuencias numéricas o alfabéticas")
            score -= 10
        
        if PasswordValidator._has_repeated_chars(password):
            issues.append("Contiene demasiadas repeticiones de caracteres")
            suggestions.append("No repitas el mismo carácter más de 2 veces seguidas")
            score -= 10
        
        # 5. BONUS PUNTOS EXTRA (Seguridad adicional)
        if len(password) >= 16:
            score += 10
        
        if complexity_score == 4 and len(password) >= 14:
            score += 10
        
        # Límite de score
        score = min(100, max(0, score))
        
        # 6. DETERMINAR FORTALEZA
        if score >= 80:
            strength = "Muy Fuerte"
            is_valid = True
        elif score >= 60:
            strength = "Fuerte"
            is_valid = True
        elif score >= 40:
            strength = "Media"
            is_valid = len(issues) == 0
        elif score >= 20:
            strength = "Débil"
            is_valid = False
        else:
            strength = "Muy Débil"
            is_valid = False
        
        return {
            'is_valid': is_valid and len(issues) == 0,
            'score': score,
            'strength': strength,
            'issues': issues,
            'suggestions': suggestions,
            'complexity': complexity_score
        }
    
    @staticmethod
    def _has_sequential_chars(password: str) -> bool:
        """Detecta secuencias de caracteres (abc, 123, etc.)"""
        for i in range(len(password) - 2):
            if ord(password[i]) + 1 == ord(password[i+1]) and ord(password[i+1]) + 1 == ord(password[i+2]):
                return True
        return False
    
    @staticmethod
    def _has_repeated_chars(password: str) -> bool:
        """Detecta más de 2 repeticiones del mismo carácter"""
        for i in range(len(password) - 2):
            if password[i] == password[i+1] == password[i+2]:
                return True
        return False
    
    @staticmethod
    def format_report(validation_result: Dict) -> str:
        """Formatea un reporte legible de validación"""
        report = f"""
╔════════════════════════════════════════════════════════════════╗
║                   ANÁLISIS DE CONTRASEÑA                      ║
╚════════════════════════════════════════════════════════════════╝

 PUNTUACIÓN: {validation_result['score']}/100
 FORTALEZA: {validation_result['strength']}
 VÁLIDA: {'Sí' if validation_result['is_valid'] else 'No'}

"""
        if validation_result['issues']:
            report += " PROBLEMAS DETECTADOS:\n"
            for issue in validation_result['issues']:
                report += f"   • {issue}\n"
            report += "\n"
        
        if validation_result['suggestions']:
            report += " SUGERENCIAS:\n"
            for suggestion in validation_result['suggestions']:
                report += f"   • {suggestion}\n"
        
        return report


class PasswordGenerator:
    """Generador de contraseñas seguras y memorables"""
    
    @staticmethod
    def generate_secure(length: int = 16, 
                       use_uppercase: bool = True,
                       use_lowercase: bool = True,
                       use_digits: bool = True,
                       use_special: bool = True) -> str:
        """
        Genera una contraseña criptográficamente segura.
        
        Args:
            length (int): Longitud deseada (mínimo 12)
            use_uppercase (bool): Incluir mayúsculas
            use_lowercase (bool): Incluir minúsculas
            use_digits (bool): Incluir números
            use_special (bool): Incluir caracteres especiales
            
        Returns:
            str: Contraseña segura generada
        """
        if length < 12:
            length = 12
        
        characters = ""
        if use_lowercase:
            characters += string.ascii_lowercase
        if use_uppercase:
            characters += string.ascii_uppercase
        if use_digits:
            characters += string.digits
        if use_special:
            characters += "!@#$%^&*()_+-=[]{}:;,.<>?"
        
        if not characters:
            raise ValueError("Debes seleccionar al menos un tipo de carácter")
        
        # Generar contraseña usando secrets para criptografía segura
        password = ''.join(secrets.choice(characters) for _ in range(length))
        
        # Asegurar que tiene todos los tipos de caracteres solicitados
        password = PasswordGenerator._ensure_variety(password, length, use_uppercase, 
                                                      use_lowercase, use_digits, use_special)
        
        return password
    
    @staticmethod
    def _ensure_variety(password: str, length: int, 
                       use_uppercase: bool, use_lowercase: bool, 
                       use_digits: bool, use_special: bool) -> str:
        """Asegura que la contraseña tiene variedad de caracteres"""
        pwd_list = list(password)
        
        checks = [
            (use_uppercase, string.ascii_uppercase),
            (use_lowercase, string.ascii_lowercase),
            (use_digits, string.digits),
            (use_special, "!@#$%^&*()_+-=[]{}:;,.<>?")
        ]
        
        for should_have, chars in checks:
            if should_have and not any(c in chars for c in pwd_list):
                # Insertar un carácter del tipo faltante
                idx = secrets.randbelow(len(pwd_list))
                pwd_list[idx] = secrets.choice(chars)
        
        return ''.join(pwd_list)
    
    @staticmethod
    def generate_memorable(word_count: int = 4) -> str:
        """
        Genera una contraseña memorable usando palabras + números + símbolos.
        (Útil para usuarios, pero menos segura que generate_secure)
        """
        # Lista de palabras comunes en español (fáciles de recordar pero aleatorias)
        words = [
            'gato', 'perro', 'casa', 'árbol', 'mesa', 'silla', 'puerta', 'ventana',
            'libro', 'flor', 'montaña', 'río', 'nube', 'estrella', 'luna', 'sol',
            'mariposa', 'águila', 'tigre', 'león', 'fuego', 'agua', 'tierra', 'viento',
            'castillo', 'barco', 'caballo', 'elefante', 'ballena', 'delfín'
        ]
        
        # Seleccionar palabras aleatorias
        selected_words = [secrets.choice(words) for _ in range(word_count)]
        password = '-'.join(selected_words)
        
        # Añadir número y símbolo para complejidad
        number = secrets.randbelow(100)
        special_char = secrets.choice("!@#$%")
        
        password += f"{number}{special_char}"
        return password.capitalize()


# --- FUNCIONES DE CONVENIENCIA ---

def validate_new_password(password: str, min_score: int = 60) -> Tuple[bool, str]:
    """
    Valida una contraseña para registro de nuevo usuario.
    
    Returns:
        Tuple: (is_valid, message)
    """
    result = PasswordValidator.validate_password(password)
    
    if result['score'] < min_score:
        message = f"Contraseña demasiado débil (Score: {result['score']}/100, requerido: {min_score})\n"
        message += "\n".join(result['suggestions'])
        return False, message
    
    if result['issues']:
        message = "La contraseña tiene problemas:\n"
        message += "\n".join(result['issues'])
        return False, message
    
    return True, "Contraseña válida y segura ✓"


def generate_password_reset_token(length: int = 32) -> str:
    """
    Genera un token criptográfico para reset de contraseña.
    
    Args:
        length (int): Longitud del token
        
    Returns:
        str: Token hexadecimal seguro
    """
    return secrets.token_hex(length)


# --- EJEMPLO DE USO ---
if __name__ == "__main__":
    print("\n" + "="*70)
    print("         PRUEBA DE MÓDULO DE SEGURIDAD DE CONTRASEÑAS")
    print("="*70 + "\n")
    
    # Test 1: Validar contraseña débil
    print("TEST 1: Validando contraseña débil")
    print("-" * 70)
    weak_pwd = "password123"
    result = PasswordValidator.validate_password(weak_pwd)
    print(PasswordValidator.format_report(result))
    
    # Test 2: Validar contraseña fuerte
    print("\nTEST 2: Validando contraseña fuerte")
    print("-" * 70)
    strong_pwd = "MiC@s4Segur@2026!X"
    result = PasswordValidator.validate_password(strong_pwd)
    print(PasswordValidator.format_report(result))
    
    # Test 3: Generar contraseña segura
    print("\nTEST 3: Generando contraseña segura aleatoria")
    print("-" * 70)
    generated = PasswordGenerator.generate_secure(16)
    print(f"Contraseña generada: {generated}")
    result = PasswordValidator.validate_password(generated)
    print(f"Puntuación: {result['score']}/100 ({result['strength']})")
    
    # Test 4: Generar contraseña memorable
    print("\nTEST 4: Generando contraseña memorable")
    print("-" * 70)
    memorable = PasswordGenerator.generate_memorable()
    print(f"Contraseña memorable: {memorable}")
    result = PasswordValidator.validate_password(memorable)
    print(f"Puntuación: {result['score']}/100 ({result['strength']})")
    
    # Test 5: Token de reset
    print("\nTEST 5: Generando token de reset de contraseña")
    print("-" * 70)
    token = generate_password_reset_token()
    print(f"Token generado: {token}")
    print(f"Longitud: {len(token)} caracteres")
    
    print("\n" + "="*70)
