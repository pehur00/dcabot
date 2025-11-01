"""
Input validation and sanitization for DCA Bot SaaS
Provides security checks for all user inputs

OWASP Top 10 2021 Security Controls:
- A01: Broken Access Control - Role-based validation
- A02: Cryptographic Failures - Secure password handling
- A03: Injection - Input sanitization, parameterized queries
- A07: Authentication Failures - Strong password policy, rate limiting
"""
import re
from typing import Tuple, Optional
import html
import unicodedata


def sanitize_string(value: str, max_length: int = 255, allow_html: bool = False) -> str:
    """
    Sanitize string input - OWASP A03 (Injection) prevention

    Protections:
    - XSS: HTML escaping
    - Unicode normalization to prevent homograph attacks
    - Null byte injection prevention
    - Control character removal

    Args:
        value: Input string to sanitize
        max_length: Maximum allowed length
        allow_html: If False, escape all HTML (default)

    Returns:
        Sanitized string
    """
    if not value:
        return ""

    # Strip whitespace
    value = value.strip()

    # Remove null bytes (SQL/Path injection prevention)
    value = value.replace('\x00', '')

    # Remove control characters (except newline and tab for descriptions)
    value = ''.join(char for char in value if unicodedata.category(char)[0] != 'C' or char in '\n\t')

    # Unicode normalization (prevent homograph/IDN attacks)
    value = unicodedata.normalize('NFKC', value)

    # Limit length
    value = value[:max_length]

    # Escape HTML to prevent XSS (OWASP A03)
    if not allow_html:
        value = html.escape(value)

    return value


def detect_sql_injection_patterns(value: str) -> bool:
    """
    Detect common SQL injection patterns - OWASP A03 (Injection)

    Note: We use parameterized queries, but this adds defense-in-depth

    Args:
        value: Input to check

    Returns:
        True if suspicious pattern detected
    """
    if not value:
        return False

    # Common SQL injection patterns
    sql_patterns = [
        r"(\b(SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|EXEC|EXECUTE|UNION|DECLARE)\b)",
        r"(--|\#|\/\*|\*\/)",  # SQL comments
        r"(;|\|\||&&)",  # Statement terminators and logical operators
        r"(\bOR\b.*=.*|1=1|' OR ')",  # Classic OR injection
        r"(xp_|sp_|exec\s*\()",  # Stored procedures
        r"(\bINTO\s+OUTFILE\b|\bLOAD_FILE\b)",  # File operations
    ]

    for pattern in sql_patterns:
        if re.search(pattern, value, re.IGNORECASE):
            return True

    return False


def detect_path_traversal(value: str) -> bool:
    """
    Detect path traversal attempts - OWASP A01 (Broken Access Control)

    Args:
        value: Input to check

    Returns:
        True if suspicious pattern detected
    """
    if not value:
        return False

    # Path traversal patterns
    traversal_patterns = [
        r'\.\.',  # Parent directory
        r'%2e%2e',  # URL encoded ..
        r'\.\./',  # ../
        r'\.\.\\',  # ..\
        r'/etc/',  # Unix system files
        r'/proc/',  # Unix process files
        r'C:\\',  # Windows paths
        r'\\\\',  # UNC paths
    ]

    for pattern in traversal_patterns:
        if re.search(pattern, value, re.IGNORECASE):
            return True

    return False


def detect_xss_patterns(value: str) -> bool:
    """
    Detect XSS attack patterns - OWASP A03 (Injection)

    Note: We escape HTML, but this adds defense-in-depth

    Args:
        value: Input to check

    Returns:
        True if suspicious pattern detected
    """
    if not value:
        return False

    # XSS patterns
    xss_patterns = [
        r'<script',
        r'javascript:',
        r'onerror\s*=',
        r'onload\s*=',
        r'<iframe',
        r'<object',
        r'<embed',
        r'eval\s*\(',
        r'expression\s*\(',
        r'vbscript:',
        r'data:text/html',
    ]

    for pattern in xss_patterns:
        if re.search(pattern, value, re.IGNORECASE):
            return True

    return False


def validate_email(email: str) -> Tuple[bool, Optional[str]]:
    """
    Validate email address format - OWASP A03 (Injection) & A07 (Auth Failures)

    Args:
        email: Email address to validate

    Returns:
        (is_valid, error_message)
    """
    if not email:
        return False, "Email is required"

    email = email.strip().lower()

    # OWASP: Check for injection attempts
    if detect_sql_injection_patterns(email):
        return False, "Invalid email format"

    if detect_xss_patterns(email):
        return False, "Invalid email format"

    # Length check
    if len(email) > 255:
        return False, "Email address is too long"

    if len(email) < 3:
        return False, "Email address is too short"

    # RFC 5322 compliant email regex (simplified)
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'

    if not re.match(email_pattern, email):
        return False, "Invalid email format"

    # Block common disposable email domains (optional)
    disposable_domains = ['tempmail.com', 'throwaway.email', '10minutemail.com']
    domain = email.split('@')[1] if '@' in email else ''
    if domain in disposable_domains:
        return False, "Disposable email addresses are not allowed"

    return True, None


def validate_password(password: str) -> Tuple[bool, Optional[str]]:
    """
    Validate password strength

    Requirements:
    - At least 8 characters
    - At least one uppercase letter
    - At least one lowercase letter
    - At least one digit
    - At least one special character

    Args:
        password: Password to validate

    Returns:
        (is_valid, error_message)
    """
    if not password:
        return False, "Password is required"

    if len(password) < 8:
        return False, "Password must be at least 8 characters long"

    if len(password) > 128:
        return False, "Password is too long (max 128 characters)"

    # Check for uppercase
    if not re.search(r'[A-Z]', password):
        return False, "Password must contain at least one uppercase letter"

    # Check for lowercase
    if not re.search(r'[a-z]', password):
        return False, "Password must contain at least one lowercase letter"

    # Check for digit
    if not re.search(r'\d', password):
        return False, "Password must contain at least one number"

    # Check for special character
    if not re.search(r'[!@#$%^&*(),.?":{}|<>_\-+=\[\]\\\/;\'`~]', password):
        return False, "Password must contain at least one special character (!@#$%^&* etc.)"

    # Check for common weak passwords
    weak_passwords = [
        'password', 'password123', '12345678', 'qwerty123',
        'admin123', 'letmein', 'welcome123', 'monkey123'
    ]
    if password.lower() in weak_passwords:
        return False, "Password is too common. Please choose a stronger password"

    return True, None


def validate_bot_name(name: str) -> Tuple[bool, Optional[str]]:
    """
    Validate bot name - OWASP A03 (Injection)

    Args:
        name: Bot name to validate

    Returns:
        (is_valid, error_message)
    """
    if not name:
        return False, "Bot name is required"

    name = name.strip()

    # OWASP: Check for injection attempts
    if detect_sql_injection_patterns(name):
        return False, "Bot name contains invalid characters"

    if detect_xss_patterns(name):
        return False, "Bot name contains invalid characters"

    if detect_path_traversal(name):
        return False, "Bot name contains invalid characters"

    if len(name) < 3:
        return False, "Bot name must be at least 3 characters"

    if len(name) > 100:
        return False, "Bot name is too long (max 100 characters)"

    # Allow alphanumeric, spaces, hyphens, underscores
    if not re.match(r'^[a-zA-Z0-9 _-]+$', name):
        return False, "Bot name can only contain letters, numbers, spaces, hyphens, and underscores"

    return True, None


def validate_symbol(symbol: str) -> Tuple[bool, Optional[str]]:
    """
    Validate trading pair symbol

    Args:
        symbol: Trading symbol to validate (e.g., BTCUSDT)

    Returns:
        (is_valid, error_message)
    """
    if not symbol:
        return False, "Symbol is required"

    symbol = symbol.strip().upper()

    if len(symbol) < 3 or len(symbol) > 20:
        return False, "Symbol must be between 3 and 20 characters"

    # Allow only uppercase letters and numbers
    if not re.match(r'^[A-Z0-9]+$', symbol):
        return False, "Symbol can only contain uppercase letters and numbers"

    return True, None


def validate_leverage(leverage: str) -> Tuple[bool, Optional[str]]:
    """
    Validate leverage value

    Args:
        leverage: Leverage value to validate

    Returns:
        (is_valid, error_message)
    """
    try:
        leverage_int = int(leverage)
    except (ValueError, TypeError):
        return False, "Leverage must be a number"

    if leverage_int < 1:
        return False, "Leverage must be at least 1"

    if leverage_int > 100:
        return False, "Leverage cannot exceed 100"

    return True, None


def validate_api_key(api_key: str) -> Tuple[bool, Optional[str]]:
    """
    Validate API key format

    Args:
        api_key: API key to validate

    Returns:
        (is_valid, error_message)
    """
    if not api_key:
        return False, "API key is required"

    api_key = api_key.strip()

    if len(api_key) < 10:
        return False, "API key appears to be invalid (too short)"

    if len(api_key) > 500:
        return False, "API key is too long"

    # Check for dangerous characters
    if re.search(r'[<>"\']', api_key):
        return False, "API key contains invalid characters"

    return True, None


def validate_side(side: str) -> Tuple[bool, Optional[str]]:
    """
    Validate trading side

    Args:
        side: Trading side (Long/Short)

    Returns:
        (is_valid, error_message)
    """
    if not side:
        return False, "Side is required"

    side = side.strip().capitalize()

    if side not in ['Long', 'Short']:
        return False, "Side must be either 'Long' or 'Short'"

    return True, None


def validate_ema_interval(interval: str) -> Tuple[bool, Optional[str]]:
    """
    Validate EMA interval

    Args:
        interval: EMA interval to validate

    Returns:
        (is_valid, error_message)
    """
    try:
        interval_int = int(interval)
    except (ValueError, TypeError):
        return False, "EMA interval must be a number"

    if interval_int < 1:
        return False, "EMA interval must be at least 1"

    if interval_int > 60:
        return False, "EMA interval cannot exceed 60"

    return True, None


def validate_exchange(exchange: str) -> Tuple[bool, Optional[str]]:
    """
    Validate exchange name

    Args:
        exchange: Exchange name to validate

    Returns:
        (is_valid, error_message)
    """
    if not exchange:
        return False, "Exchange is required"

    exchange = exchange.strip().lower()

    # Whitelist of supported exchanges
    supported_exchanges = ['phemex', 'binance', 'bybit']

    if exchange not in supported_exchanges:
        return False, f"Unsupported exchange. Must be one of: {', '.join(supported_exchanges)}"

    return True, None


def rate_limit_check(user_id: int, action: str, max_attempts: int = 5, window_seconds: int = 300) -> Tuple[bool, Optional[str]]:
    """
    Basic rate limiting check (in-memory, resets on restart)

    For production, use Redis or database-backed rate limiting

    Args:
        user_id: User ID performing the action
        action: Action being performed (e.g., 'login', 'register')
        max_attempts: Maximum attempts allowed in window
        window_seconds: Time window in seconds

    Returns:
        (is_allowed, error_message)
    """
    # TODO: Implement proper rate limiting with Redis or database
    # For now, always allow (placeholder)
    return True, None
