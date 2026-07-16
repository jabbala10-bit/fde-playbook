# Developer's Cybersecurity Mastery: The Complete Handbook
## Volume 59–68 | Code Review · Fuzzing · RASP · DLP · SIEM · Streaming · Kyverno · SSRF Bypass · WASM · Master Reference

---

# PART 51 — SECURE CODE REVIEW METHODOLOGY

---

## Chapter 92: The Security Code Review Framework

### 92.1 Security-First Code Review Checklist

```python
# Python — Automated code review security scanner
# Complements manual review — runs in pre-commit and CI

import ast
import re
from pathlib import Path
from dataclasses import dataclass
from typing import Iterator

@dataclass
class SecurityFinding:
    file:     str
    line:     int
    severity: str
    rule:     str
    message:  str
    snippet:  str

class PythonSecurityReviewer:
    """
    AST-based Python security analysis.
    Catches patterns that regex-based tools miss.
    """

    def review_file(self, filepath: str) -> list[SecurityFinding]:
        with open(filepath) as f:
            source = f.read()
            lines  = source.splitlines()

        try:
            tree = ast.parse(source)
        except SyntaxError:
            return []

        findings = []
        for node in ast.walk(tree):
            findings.extend(self._check_node(node, filepath, lines))
        return findings

    def _check_node(
        self, node: ast.AST, filepath: str, lines: list[str]
    ) -> list[SecurityFinding]:
        findings = []
        line_num = getattr(node, "lineno", 0)
        snippet  = lines[line_num - 1].strip() if line_num > 0 and line_num <= len(lines) else ""

        # ── Check 1: subprocess with shell=True ──────────────────────────────
        if isinstance(node, ast.Call):
            func_name = self._get_call_name(node)

            if func_name in ("subprocess.run", "subprocess.Popen", "subprocess.call",
                             "subprocess.check_call", "subprocess.check_output", "os.system"):
                for keyword in node.keywords:
                    if keyword.arg == "shell" and isinstance(keyword.value, ast.Constant):
                        if keyword.value.value is True:
                            findings.append(SecurityFinding(
                                file=filepath, line=line_num, severity="CRITICAL",
                                rule="SUBPROCESS_SHELL_TRUE",
                                message="subprocess with shell=True enables command injection",
                                snippet=snippet,
                            ))

            # ── Check 2: eval() / exec() ─────────────────────────────────────
            if func_name in ("eval", "exec", "compile"):
                # Only flag if argument is not a literal string
                if node.args and not isinstance(node.args[0], ast.Constant):
                    findings.append(SecurityFinding(
                        file=filepath, line=line_num, severity="CRITICAL",
                        rule="EVAL_WITH_VARIABLE",
                        message=f"{func_name}() with variable input enables code injection",
                        snippet=snippet,
                    ))

            # ── Check 3: pickle.loads on non-trusted data ─────────────────────
            if func_name in ("pickle.loads", "pickle.load",
                             "cPickle.loads", "yaml.load"):
                findings.append(SecurityFinding(
                    file=filepath, line=line_num, severity="HIGH",
                    rule="UNSAFE_DESERIALIZATION",
                    message=f"{func_name}() on untrusted data enables RCE",
                    snippet=snippet,
                ))

            # ── Check 4: hashlib with weak algorithms ─────────────────────────
            if func_name == "hashlib.new":
                if node.args and isinstance(node.args[0], ast.Constant):
                    algo = node.args[0].value.lower()
                    if algo in ("md5", "md4", "sha1"):
                        findings.append(SecurityFinding(
                            file=filepath, line=line_num, severity="MEDIUM",
                            rule="WEAK_HASH_ALGORITHM",
                            message=f"hashlib.new('{algo}') - use SHA-256 or stronger",
                            snippet=snippet,
                        ))

            # ── Check 5: SQL string formatting ───────────────────────────────
            if func_name in ("cursor.execute", "conn.execute", "db.execute",
                             "session.execute"):
                if node.args:
                    # Look for f-strings or % formatting in the first arg
                    first_arg = node.args[0]
                    if isinstance(first_arg, ast.JoinedStr):  # f-string
                        findings.append(SecurityFinding(
                            file=filepath, line=line_num, severity="CRITICAL",
                            rule="SQL_INJECTION_FSTRING",
                            message="SQL query uses f-string — use parameterized query",
                            snippet=snippet,
                        ))
                    elif isinstance(first_arg, ast.BinOp):  # % formatting or +
                        if isinstance(first_arg.op, (ast.Mod, ast.Add)):
                            findings.append(SecurityFinding(
                                file=filepath, line=line_num, severity="CRITICAL",
                                rule="SQL_INJECTION_FORMAT",
                                message="SQL query uses string formatting — use parameterized query",
                                snippet=snippet,
                            ))

        # ── Check 6: assert statements for security ────────────────────────────
        if isinstance(node, ast.Assert):
            # assert is removed by Python -O flag — never use for security
            findings.append(SecurityFinding(
                file=filepath, line=line_num, severity="MEDIUM",
                rule="ASSERT_USED_FOR_SECURITY",
                message="assert statements are removed in optimized mode (-O) — use if/raise",
                snippet=snippet,
            ))

        # ── Check 7: Hardcoded secrets detection ──────────────────────────────
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    name_lower = target.id.lower()
                    SENSITIVE_NAMES = {
                        "password", "passwd", "secret", "api_key", "apikey",
                        "private_key", "auth_token", "access_token", "signing_key",
                        "encryption_key", "db_password", "database_password",
                    }
                    if any(s in name_lower for s in SENSITIVE_NAMES):
                        if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                            if len(node.value.value) > 4:  # Not empty or placeholder
                                findings.append(SecurityFinding(
                                    file=filepath, line=line_num, severity="CRITICAL",
                                    rule="HARDCODED_SECRET",
                                    message=f"Possible hardcoded secret in '{target.id}'",
                                    snippet=snippet,
                                ))

        return findings

    def _get_call_name(self, node: ast.Call) -> str:
        if isinstance(node.func, ast.Attribute):
            return f"{self._get_name(node.func.value)}.{node.func.attr}"
        elif isinstance(node.func, ast.Name):
            return node.func.id
        return ""

    def _get_name(self, node: ast.AST) -> str:
        if isinstance(node, ast.Name):     return node.id
        if isinstance(node, ast.Attribute): return f"{self._get_name(node.value)}.{node.attr}"
        return "unknown"


# TypeScript/JavaScript security patterns to check in code review
TYPESCRIPT_REVIEW_CHECKLIST = """
TYPESCRIPT SECURITY CODE REVIEW CHECKLIST
═══════════════════════════════════════════

AUTHENTICATION & SESSION
  □ No JWT verification algorithm set to 'none'
  □ JWT secret loaded from env, not hardcoded
  □ Token expiry validated (exp claim checked)
  □ Session cookies: httpOnly=true, secure=true, sameSite='strict'
  □ No sensitive data in JWT payload (SSN, credit card, full PII)

INPUT VALIDATION
  □ All user inputs validated with Zod/class-validator before processing
  □ No direct req.body spread into database queries
  □ File uploads: extension allowlist + size limit + type validation
  □ No eval(), new Function(), or setTimeout('string', ...) with user input

SQL / DATABASE
  □ No template literals in SQL queries
  □ No string concatenation in Prisma $queryRawUnsafe
  □ All raw SQL uses parameterized form: sql`SELECT * WHERE id = ${id}`
  □ No MongoDB: findOne(req.body) without validation

OUTPUT ENCODING
  □ No dangerouslySetInnerHTML without DOMPurify
  □ No document.write() or element.innerHTML with user data
  □ All text content uses textContent, not innerHTML

NETWORK / HTTP
  □ fetch() calls to user-provided URLs go through SSRF validator
  □ No axios(userProvidedUrl) without allowlist check
  □ External redirects validated against allowlist

DEPENDENCIES
  □ No known CVEs in package.json (checked by npm audit or Snyk)
  □ No packages with recent ownership changes or unusual download spikes
  □ All CDN scripts have SRI integrity hash

SECRETS
  □ No API keys, passwords, or tokens in source code
  □ No process.env.* values logged to console
  □ .env files in .gitignore and not committed
"""

JAVA_REVIEW_CHECKLIST = """
JAVA SECURITY CODE REVIEW CHECKLIST
═════════════════════════════════════

INJECTION
  □ No String concatenation in JDBC queries or JPQL
  □ PreparedStatement used for all parameterized queries
  □ Spring Data repository methods used (safe by default)
  □ No Runtime.exec() or ProcessBuilder with user input
  □ No LDAP queries with string concatenation

DESERIALIZATION
  □ No ObjectInputStream.readObject() on untrusted data
  □ Jackson mapper: FAIL_ON_UNKNOWN_PROPERTIES = true
  □ No enableDefaultTyping() on ObjectMapper (gadget chain risk)
  □ No XStream deserialization without allowlist

CRYPTOGRAPHY
  □ No MD5 or SHA-1 for security-sensitive hashing
  □ No AES/ECB mode — use AES/GCM/NoPadding
  □ No RSA/PKCS1Padding — use RSA/OAEP/SHA-256
  □ BCrypt/Argon2 for password hashing (not SHA-256)
  □ SecureRandom used instead of Random

SPRING SECURITY
  □ CSRF disabled only for stateless API (JWT), not session apps
  □ @PreAuthorize annotations on all admin endpoints
  □ @PostAuthorize for resource ownership validation
  □ Spring Security method security enabled: @EnableMethodSecurity
  □ HttpSecurity configured explicitly (not default)

XML
  □ All XML parsers: setFeature("http://apache.org/xml/features/disallow-doctype-decl", true)
  □ No JAXB or DOM parser used with untrusted input without configuration
"""
```

---

## Chapter 93: Security Fuzzing for Developers

### 93.1 Property-Based and Fuzz Testing

```python
# Python — Security-focused fuzzing with hypothesis
from hypothesis import given, settings, strategies as st, assume
from hypothesis.strategies import text, binary, integers, lists, dictionaries

# ── Property-based test: SQL injection safety ─────────────────────────────────
@given(user_input=text(max_size=1000))
@settings(max_examples=10000, deadline=None)
def test_user_search_never_returns_all_records(user_input):
    """
    Property: No matter what string the user provides,
    the search should never return MORE results than the total number of users.
    """
    # Establish baseline
    total_users = db.count("SELECT COUNT(*) FROM users")

    # Search with arbitrary input
    results = api.search_users(query=user_input)

    # Property: Can never return more users than exist
    # An injection like "' OR 1=1--" would violate this
    assert len(results) <= total_users, \
        f"Search returned {len(results)} results with input: {repr(user_input)[:100]}"

@given(
    user_id=text(alphabet="0123456789abcdef-", max_size=100),
    target_id=text(alphabet="0123456789abcdef-", max_size=100),
)
def test_idor_property(user_id: str, target_id: str):
    """
    Property: User can only access their own resources,
    regardless of how the ID is formatted.
    """
    assume(user_id != target_id)  # Skip when they happen to match

    response = api_client.get(
        f"/api/resources/{target_id}",
        headers={"user-id": user_id},
    )

    # Property: Should never return 200 for a different user's resource
    assert response.status_code in (400, 403, 404), \
        f"Possible IDOR: user {user_id[:8]} accessed resource {target_id[:8]}"

@given(
    headers=dictionaries(
        keys=text(alphabet="a-zA-Z-", max_size=50),
        values=text(max_size=200),
        max_size=20,
    )
)
def test_security_headers_always_present(headers: dict):
    """Property: Security headers present regardless of what the client sends"""
    response = api_client.get("/api/users/me", headers=headers)

    # These must be present in every response
    REQUIRED = ["x-content-type-options", "x-frame-options"]
    response_headers_lower = {k.lower() for k in response.headers}

    for required in REQUIRED:
        assert required in response_headers_lower, \
            f"Missing {required} with client headers: {headers}"
```

```go
// Go — Fuzzing with Go's built-in fuzzing engine (go 1.18+)
package security_test

import (
    "testing"
    "net/http/httptest"
    "net/http"
    "your/app"
)

// Run with: go test -fuzz=FuzzHTTPInput -fuzztime=60s
func FuzzHTTPInput(f *testing.F) {
    // Seed corpus — known interesting inputs
    f.Add([]byte(`{"username": "admin'--", "password": "test"}`))
    f.Add([]byte(`{"username": "admin", "password": "' OR '1'='1"}`))
    f.Add([]byte(`{"username": "<script>alert(1)</script>", "password": "test"}`))
    f.Add([]byte(string(make([]byte, 100000)))) // Very large input

    f.Fuzz(func(t *testing.T, input []byte) {
        // Create test server
        handler := app.NewHandler()
        req := httptest.NewRequest("POST", "/api/auth/login", bytes.NewReader(input))
        req.Header.Set("Content-Type", "application/json")
        w := httptest.NewRecorder()

        // Should never panic or return 500
        handler.ServeHTTP(w, req)

        result := w.Result()

        // Properties that must ALWAYS hold:
        // 1. No 500 errors (unexpected crash)
        if result.StatusCode == 500 {
            t.Errorf("Server returned 500 for input: %q", string(input[:min(100, len(input))]))
        }

        // 2. No SQL error messages in response
        body, _ := io.ReadAll(result.Body)
        if bytes.Contains(bytes.ToLower(body), []byte("sql")) ||
           bytes.Contains(bytes.ToLower(body), []byte("syntax error")) {
            t.Errorf("SQL error exposed for input: %q", string(input[:min(100, len(input))]))
        }

        // 3. Security headers always present
        if result.Header.Get("X-Content-Type-Options") == "" {
            t.Error("Missing X-Content-Type-Options header")
        }
    })
}

func FuzzPathTraversal(f *testing.F) {
    f.Add("normal-file.txt")
    f.Add("../../../etc/passwd")
    f.Add("..%2F..%2F..%2Fetc%2Fpasswd")
    f.Add("....//etc/passwd")

    f.Fuzz(func(t *testing.T, filename string) {
        response, err := http.Get("http://localhost:8080/api/files/" + filename)
        if err != nil { return }

        body, _ := io.ReadAll(response.Body)
        response.Body.Close()

        // Should never return /etc/passwd content
        if bytes.Contains(body, []byte("root:x:0:0")) {
            t.Errorf("Path traversal succeeded with: %q", filename)
        }
    })
}
```

```rust
// Rust — cargo-fuzz integration for Rust security testing
// Add to fuzz/fuzz_targets/fuzz_parser.rs

#![no_main]
use libfuzzer_sys::fuzz_target;
use your_crate::{parse_request, validate_token, decode_jwt};

// Run with: cargo fuzz run fuzz_request_parser
fuzz_target!(|data: &[u8]| {
    // Property: parser should never panic on arbitrary input
    // (panics in Rust = potential DoS or undefined behavior in unsafe code)
    let _ = std::panic::catch_unwind(|| {
        if let Ok(input) = std::str::from_utf8(data) {
            // Should never panic
            let _ = parse_request(input);

            // JWT parsing should handle any base64 input gracefully
            let _ = decode_jwt(input);
        }
    });
});

// Fuzzing for path traversal in file operations
fuzz_target!(|data: &[u8]| {
    if let Ok(path) = std::str::from_utf8(data) {
        let _ = std::panic::catch_unwind(|| {
            // Should safely reject all traversal attempts
            match validate_file_path(path) {
                Ok(safe_path) => {
                    // If it returns Ok, path must be within allowed directory
                    let allowed = std::path::Path::new("/workspace/uploads");
                    let resolved = std::path::Path::new(&safe_path);
                    assert!(
                        resolved.starts_with(allowed),
                        "Path escaped sandbox: {:?}", resolved
                    );
                },
                Err(_) => {} // Rejection is always safe
            }
        });
    }
});
```

---

# PART 52 — RUNTIME APPLICATION SELF-PROTECTION (RASP)

---

## Chapter 94: RASP — Defense From Within

```java
// Java — RASP implementation using Java Instrumentation API
// Instruments running application bytecode to detect and block attacks in real-time

import java.lang.instrument.Instrumentation;
import java.security.Permission;

public class RASPAgent {

    public static void premain(String agentArgs, Instrumentation inst) {
        // Install security monitors
        installSQLInjectionDetector(inst);
        installCommandInjectionDetector(inst);
        installPathTraversalDetector(inst);
        System.out.println("[RASP] Security agent initialized");
    }

    // Override SecurityManager to intercept dangerous operations
    static void installCommandInjectionDetector(Instrumentation inst) {
        System.setSecurityManager(new SecurityManager() {
            @Override
            public void checkExec(String cmd) {
                // Log all exec attempts
                String caller = Thread.currentThread().getStackTrace()[2].getClassName();
                if (!isAllowedCaller(caller)) {
                    String alert = String.format(
                        "[RASP BLOCK] Command execution attempt: %s from %s", cmd, caller
                    );
                    SecurityAuditLog.critical(alert);

                    // Block if command contains suspicious patterns
                    if (containsSuspiciousPattern(cmd)) {
                        throw new SecurityException("RASP: Command execution blocked");
                    }
                }
                super.checkExec(cmd);
            }

            @Override
            public void checkRead(String file) {
                // Check for path traversal
                if (file.contains("../") || file.contains("..\\")) {
                    String caller = Thread.currentThread().getStackTrace()[2].getClassName();
                    SecurityAuditLog.warning(
                        String.format("[RASP] Path traversal attempt: %s from %s", file, caller)
                    );
                    throw new SecurityException("RASP: Path traversal blocked");
                }
                super.checkRead(file);
            }

            private boolean containsSuspiciousPattern(String cmd) {
                String lower = cmd.toLowerCase();
                return lower.contains("/etc/passwd") ||
                       lower.contains("wget ") || lower.contains("curl ") ||
                       lower.contains(" | ") || lower.contains(";rm ") ||
                       lower.contains("nc ") || lower.contains("ncat ");
            }

            private boolean isAllowedCaller(String className) {
                // Allowlist of classes permitted to execute commands
                return className.startsWith("com.myapp.trusted.");
            }
        });
    }
}
```

```python
# Python — Application-level RASP using function monkey-patching

import functools
import subprocess
import os
import builtins
import structlog

logger = structlog.get_logger("rasp")

class PythonRASP:
    """
    Python Runtime Application Self-Protection.
    Patches dangerous functions to add detection and blocking.
    """

    def __init__(self, mode: str = "detect"):  # "detect" or "block"
        self.mode   = mode
        self._active = False

    def activate(self):
        if self._active:
            return
        self._active = True
        self._patch_subprocess()
        self._patch_eval()
        self._patch_open()
        logger.info("rasp.activated", mode=self.mode)

    def _patch_subprocess(self):
        original_run = subprocess.run

        @functools.wraps(original_run)
        def safe_run(*args, **kwargs):
            if kwargs.get("shell") is True:
                # shell=True is almost never legitimate
                import traceback
                logger.warning(
                    "rasp.subprocess_shell_true",
                    args=str(args)[:200],
                    caller=traceback.extract_stack()[-2].filename,
                )
                if self.mode == "block":
                    raise SecurityError("RASP: shell=True subprocess blocked")
            return original_run(*args, **kwargs)

        subprocess.run = safe_run

    def _patch_eval(self):
        original_eval = builtins.eval

        @functools.wraps(original_eval)
        def safe_eval(expr, *args, **kwargs):
            if isinstance(expr, str):
                import traceback
                logger.error(
                    "rasp.eval_called",
                    expr_preview=expr[:100],
                    caller=traceback.extract_stack()[-2].filename,
                )
                if self.mode == "block":
                    raise SecurityError("RASP: eval() blocked")
            return original_eval(expr, *args, **kwargs)

        builtins.eval = safe_eval

    def _patch_open(self):
        original_open = builtins.open
        ALLOWED_PREFIXES = ["/workspace/", "/tmp/", "/app/"]

        @functools.wraps(original_open)
        def safe_open(file, *args, **kwargs):
            if isinstance(file, str):
                import os.path
                normalized = os.path.normpath(os.path.abspath(file))

                # Path traversal detection
                if ".." in file:
                    logger.warning("rasp.path_traversal", path=file)
                    if self.mode == "block":
                        raise SecurityError("RASP: Path traversal blocked")

                # Sensitive file access detection
                SENSITIVE_FILES = {"/etc/passwd", "/etc/shadow", "/etc/hosts",
                                   "/proc/self/environ", "/.aws/credentials"}
                if normalized in SENSITIVE_FILES:
                    logger.critical("rasp.sensitive_file_access", path=normalized)
                    if self.mode == "block":
                        raise SecurityError(f"RASP: Access to {normalized} blocked")

            return original_open(file, *args, **kwargs)

        builtins.open = safe_open

# Activate RASP at application startup
rasp = PythonRASP(mode="detect")  # "block" in production after tuning
rasp.activate()

class SecurityError(Exception):
    pass
```

---

# PART 53 — DATA LOSS PREVENTION (DLP)

---

## Chapter 95: DLP Patterns for Developer Systems

```python
# Python — Application-level DLP for API responses and logs

import re
from dataclasses import dataclass
from enum import Enum
from typing import Any

class SensitivityLevel(Enum):
    PUBLIC       = "public"
    INTERNAL     = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED   = "restricted"   # PII, PHI, PCI data

@dataclass
class DLPPattern:
    name:        str
    pattern:     re.Pattern
    sensitivity: SensitivityLevel
    action:      str  # "redact", "alert", "block"

class ApplicationDLP:
    """
    Data Loss Prevention for application responses.
    Prevents accidental exposure of sensitive data in API responses,
    logs, exports, and search results.
    """

    PATTERNS = [
        DLPPattern(
            name="credit_card", sensitivity=SensitivityLevel.RESTRICTED, action="block",
            pattern=re.compile(r'\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|'
                               r'3[47][0-9]{13}|6(?:011|5[0-9]{2})[0-9]{12})\b'),
        ),
        DLPPattern(
            name="ssn", sensitivity=SensitivityLevel.RESTRICTED, action="block",
            pattern=re.compile(r'\b\d{3}-\d{2}-\d{4}\b'),
        ),
        DLPPattern(
            name="api_key", sensitivity=SensitivityLevel.CONFIDENTIAL, action="alert",
            pattern=re.compile(r'(?:api[_-]?key|apikey)\s*[:=]\s*["\']?([A-Za-z0-9_\-]{20,})',
                               re.IGNORECASE),
        ),
        DLPPattern(
            name="aws_key", sensitivity=SensitivityLevel.RESTRICTED, action="block",
            pattern=re.compile(r'AKIA[0-9A-Z]{16}'),
        ),
        DLPPattern(
            name="private_key_pem", sensitivity=SensitivityLevel.RESTRICTED, action="block",
            pattern=re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
        ),
        DLPPattern(
            name="jwt_token", sensitivity=SensitivityLevel.CONFIDENTIAL, action="redact",
            pattern=re.compile(r'eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}'),
        ),
        DLPPattern(
            name="email_bulk", sensitivity=SensitivityLevel.INTERNAL, action="alert",
            pattern=re.compile(r'\b[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}\b'),
        ),
    ]

    def scan_response(self, content: str, context: dict = None) -> dict:
        """Scan API response content for sensitive data"""
        findings  = []
        should_block = False

        for dlp in self.PATTERNS:
            matches = dlp.pattern.findall(content)
            if matches:
                findings.append({
                    "pattern":     dlp.name,
                    "sensitivity": dlp.sensitivity.value,
                    "action":      dlp.action,
                    "match_count": len(matches),
                })

                if dlp.action == "block":
                    should_block = True

        if findings:
            import structlog
            structlog.get_logger().warning(
                "dlp.sensitive_data_in_response",
                findings=findings,
                context=context,
            )

        return {
            "clean":    not findings,
            "block":    should_block,
            "findings": findings,
        }

    def redact_response(self, content: str) -> str:
        """Redact sensitive patterns from a response"""
        result = content
        for dlp in self.PATTERNS:
            if dlp.action in ("redact", "block"):
                result = dlp.pattern.sub(f"[{dlp.name.upper()}_REDACTED]", result)
        return result

    def scan_export(
        self,
        data: list[dict],
        allowed_fields: set[str],
    ) -> list[dict]:
        """
        Scan and filter data exports.
        Only include fields in the allowed set.
        """
        clean = []
        for record in data:
            filtered = {k: v for k, v in record.items() if k in allowed_fields}
            # Scan values for unexpected sensitive data
            scan_result = self.scan_response(str(filtered))
            if not scan_result["block"]:
                clean.append(filtered)
        return clean

# FastAPI middleware for response DLP scanning
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

class DLPMiddleware(BaseHTTPMiddleware):
    dlp = ApplicationDLP()

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        # Scan response body for sensitive data
        body = b""
        async for chunk in response.body_iterator:
            body += chunk

        content_type = response.headers.get("content-type", "")
        if "json" in content_type or "text" in content_type:
            scan = self.dlp.scan_response(
                body.decode("utf-8", errors="replace"),
                context={
                    "path":   request.url.path,
                    "method": request.method,
                    "user":   request.state.__dict__.get("user_id"),
                }
            )

            if scan["block"]:
                # Block the response — something should not be there
                import json
                return Response(
                    content=json.dumps({"error": "Response blocked by DLP policy"}),
                    status_code=500,
                    media_type="application/json",
                )

        return Response(
            content=body,
            status_code=response.status_code,
            headers=dict(response.headers),
            media_type=content_type,
        )
```

---

# PART 54 — SIEM CUSTOM DETECTION RULES

---

## Chapter 96: Writing Detection Rules for Your Application

```python
# Python — Custom SIEM detection rules using Sigma-compatible format

# Sigma rules can be converted to: Elasticsearch, Splunk, QRadar, Chronicle, etc.

SIGMA_RULES = [
    # Rule 1: Brute force detection
    {
        "title":       "Application Brute Force Attack",
        "id":          "app-brute-force-001",
        "status":      "production",
        "description": "Detects brute force attacks on application login endpoint",
        "references":  ["https://owasp.org/www-community/attacks/Brute_force_attack"],
        "tags":        ["attack.credential-access", "T1110"],
        "logsource": {
            "product":  "webapp",
            "service":  "audit",
            "category": "authentication",
        },
        "detection": {
            "selection": {
                "event_type":  "auth.failure",
                "status_code": 401,
            },
            "timeframe": "5m",
            "condition": "selection | count() by source_ip > 10",
        },
        "falsepositives": ["Password manager misconfiguration", "Integration test runs"],
        "level": "high",
    },

    # Rule 2: Account Takeover - Login from new country after credential change
    {
        "title":       "Suspicious Login After Credential Reset",
        "id":          "app-ato-001",
        "description": "Login from new country within 1h of password reset",
        "detection": {
            "password_reset": {
                "event_type": "user.password_reset",
                "result":     "success",
            },
            "new_country_login": {
                "event_type":  "auth.success",
                "country_code": "!= previous_country",  # Simplified
            },
            "timeframe": "1h",
            "condition": "password_reset followed by new_country_login within 1h",
        },
        "level": "high",
    },

    # Rule 3: Data exfiltration via large API response
    {
        "title":       "Unusually Large API Response - Possible Data Exfiltration",
        "id":          "app-exfil-001",
        "detection": {
            "selection": {
                "event_type":         "api.response",
                "response_size_bytes": "> 10000000",  # 10MB
                "status_code":        200,
            },
            "condition": "selection",
        },
        "level": "medium",
    },

    # Rule 4: Impossible travel
    {
        "title":       "Impossible Travel Detection",
        "id":          "app-travel-001",
        "description": "Two logins from different countries impossible to travel between in timeframe",
        "level": "high",
    },

    # Rule 5: Privilege escalation via role change
    {
        "title":       "Unauthorized Role Change",
        "id":          "app-privesc-001",
        "detection": {
            "selection": {
                "event_type": "admin.role_change",
                "changed_by": "!= 'automated_provisioning'",
            },
            "condition": "selection",
        },
        "level": "critical",
    },
]

# Elasticsearch detection queries generated from Sigma rules
ELASTICSEARCH_QUERIES = {
    "brute_force": {
        "aggs": {
            "by_ip": {
                "terms": {"field": "source_ip", "size": 100},
                "aggs": {
                    "failure_count": {"value_count": {"field": "event_id"}},
                    "bucket_filter": {
                        "bucket_selector": {
                            "buckets_path": {"count": "failure_count"},
                            "script": "params.count > 10",
                        }
                    }
                }
            }
        },
        "query": {
            "bool": {
                "must": [
                    {"term":  {"event_type": "auth.failure"}},
                    {"range": {"@timestamp": {"gte": "now-5m"}}},
                ]
            }
        },
    },
}

class ApplicationSIEM:
    """Send structured events to SIEM with proper categorization"""

    # MITRE ATT&CK technique mappings for application events
    TECHNIQUE_MAP = {
        "auth.failure":         "T1110",   # Brute Force
        "auth.mfa_bypass":      "T1556",   # Modify Authentication Process
        "data.exfiltration":    "T1041",   # Exfiltration Over C2 Channel
        "admin.role_change":    "T1548",   # Abuse Elevation Control Mechanism
        "injection.attempt":    "T1190",   # Exploit Public-Facing Application
        "ssrf.attempt":         "T1190",
        "account.lockout":      "T1110.003", # Password Spraying
        "credential.stuffing":  "T1110.004", # Credential Stuffing
    }

    def emit_detection_event(
        self,
        event_type:  str,
        severity:    str,
        source_ip:   str | None,
        user_id:     str | None,
        details:     dict,
        blocked:     bool = False,
    ) -> None:
        """
        Emit a structured security event to SIEM.
        Format compatible with Elastic Common Schema (ECS).
        """
        import structlog, time

        structlog.get_logger("siem").log(
            severity.lower(),
            # ECS fields
            **{
                "@timestamp":         time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "event.category":     "authentication" if "auth" in event_type else "intrusion_detection",
                "event.type":         "denied" if blocked else "allowed",
                "event.outcome":      "failure" if "failure" in event_type else "success",
                "event.severity":     {"critical": 90, "high": 70, "medium": 50, "low": 25}.get(severity, 50),
                "event.action":       event_type,
                "event.provider":     "application-siem",
                # Threat intelligence
                "threat.technique.id": self.TECHNIQUE_MAP.get(event_type, "T1190"),
                "threat.framework":    "MITRE ATT&CK",
                # Actor
                "source.ip":          source_ip,
                "user.id":            user_id,
                # Response
                "event.blocked":      blocked,
                # Custom fields
                **{f"app.{k}": v for k, v in details.items()},
            }
        )
```

---

# PART 55 — SECURITY FOR STREAMING DATA

---

## Chapter 97: Apache Flink and Spark Streaming Security

```python
# Python — Secure stream processing with PySpark Structured Streaming

from pyspark.sql import SparkSession
from pyspark.sql.functions import col, from_json, udf
from pyspark.sql.types import StringType, StructType, StructField, BooleanType
import hmac
import hashlib

class SecureStreamProcessor:
    """
    Secure stream processing principles:
    1. Validate and authenticate each message
    2. Apply PII masking before writing to storage
    3. Enforce access control on stream sinks
    4. Audit all data transformations
    """

    def __init__(self, spark: SparkSession, signing_key: bytes):
        self.spark       = spark
        self.signing_key = signing_key

    def create_secure_kafka_stream(
        self,
        kafka_servers: str,
        topic: str,
        ssl_config: dict,
    ):
        """Create authenticated Kafka stream with TLS"""
        return (
            self.spark.readStream
            .format("kafka")
            .option("kafka.bootstrap.servers", kafka_servers)
            # TLS authentication
            .option("kafka.security.protocol",  "SASL_SSL")
            .option("kafka.sasl.mechanism",      "SCRAM-SHA-512")
            .option("kafka.ssl.truststore.location", ssl_config["truststore"])
            .option("kafka.ssl.truststore.password", ssl_config["truststore_pass"])
            .option("kafka.sasl.jaas.config",
                    f'org.apache.kafka.common.security.scram.ScramLoginModule required '
                    f'username="{ssl_config["username"]}" password="{ssl_config["password"]}";')
            .option("subscribe", topic)
            # Limit message size — prevent resource exhaustion
            .option("maxOffsetsPerTrigger", 10000)
            .load()
        )

    def verify_message_signature(self, payload: str, signature: str) -> bool:
        """UDF for message signature verification"""
        try:
            expected = hmac.new(
                self.signing_key,
                payload.encode(),
                hashlib.sha256
            ).hexdigest()
            return hmac.compare_digest(signature, expected)
        except Exception:
            return False

    def mask_pii_fields(self, df):
        """Apply PII masking to DataFrame before writing"""
        from pyspark.sql.functions import regexp_replace, sha2, concat, lit

        return df \
            .withColumn("email",
                # Partial masking: j***@example.com
                regexp_replace(col("email"), r'(?<=^.)(.*?)(?=@)', "***")) \
            .withColumn("phone",
                # Keep only last 4 digits
                regexp_replace(col("phone"), r'\d(?=\d{4})', "*")) \
            .withColumn("ssn",
                # Full masking
                regexp_replace(col("ssn"), r'\d{3}-\d{2}-\d{4}', "***-**-****")) \
            .withColumn("ip_address",
                # Mask last octet
                regexp_replace(col("ip_address"), r'\.\d+$', ".0"))

    def process_events_securely(
        self,
        kafka_servers: str,
        input_topic:   str,
        output_path:   str,
        schema:        StructType,
        ssl_config:    dict,
    ):
        """Complete secure stream processing pipeline"""

        # Register signature verification as UDF
        verify_sig_udf = udf(self.verify_message_signature, BooleanType())

        stream = self.create_secure_kafka_stream(kafka_servers, input_topic, ssl_config)

        # Parse and validate messages
        parsed = (
            stream
            .select(
                col("value").cast("string").alias("raw_value"),
                col("headers").getItem("X-Signature").cast("string").alias("signature"),
                col("timestamp").alias("kafka_timestamp"),
            )
            .withColumn("payload", from_json(col("raw_value"), schema))

            # Verify message signatures — drop messages with invalid signatures
            .withColumn("valid_sig", verify_sig_udf(col("raw_value"), col("signature")))
            .filter(col("valid_sig") == True)
            .drop("valid_sig", "raw_value", "signature")
        )

        # Flatten and apply PII masking
        flattened = parsed.select("kafka_timestamp", "payload.*")
        masked    = self.mask_pii_fields(flattened)

        # Write to encrypted storage
        query = (
            masked.writeStream
            .format("delta")
            .option("path", output_path)
            .option("checkpointLocation", output_path + "/_checkpoint")
            # Delta Lake encryption (with Apache Ranger or Databricks)
            .option("delta.enableDeletionVectors", "true")
            .partitionBy("event_date")
            .trigger(processingTime="30 seconds")
            .start()
        )

        return query
```

---

# PART 56 — ADVANCED KUBERNETES SECURITY WITH KYVERNO

---

## Chapter 98: Policy as Code with Kyverno

```yaml
# kyverno/policies/security-standards.yaml
# Kyverno: Kubernetes-native policy engine

# Policy 1: Require security context on all containers
apiVersion: kyverno.io/v1
kind: ClusterPolicy
metadata:
  name: require-security-context
  annotations:
    policies.kyverno.io/title:       Container Security Context Required
    policies.kyverno.io/severity:    high
    policies.kyverno.io/description: >
      All containers must run with a non-root security context.
      Containers running as root are a significant security risk.
spec:
  validationFailureAction: enforce
  rules:
    - name: check-containers
      match:
        any:
          - resources:
              kinds: [Pod]
      validate:
        message: "All containers must run as non-root with explicit securityContext"
        foreach:
          - list: "request.object.spec.containers"
            deny:
              conditions:
                any:
                  # Deny if securityContext is missing
                  - key: "{{ element.securityContext | default('{}') }}"
                    operator: Equals
                    value: "{}"
                  # Deny if running as root
                  - key: "{{ element.securityContext.runAsNonRoot | default(false) }}"
                    operator: NotEquals
                    value: true
                  # Deny if privilege escalation allowed
                  - key: "{{ element.securityContext.allowPrivilegeEscalation | default(true) }}"
                    operator: NotEquals
                    value: false

---
# Policy 2: Require image digest pinning (immutable images)
apiVersion: kyverno.io/v1
kind: ClusterPolicy
metadata:
  name: require-image-digest
  annotations:
    policies.kyverno.io/severity: critical
spec:
  validationFailureAction: enforce
  rules:
    - name: check-image-digest
      match:
        any:
          - resources:
              kinds: [Pod]
      validate:
        message: "Container images must use digest pinning (@sha256:...)"
        foreach:
          - list: "request.object.spec.containers"
            deny:
              conditions:
                all:
                  - key: "{{ element.image }}"
                    operator: NotContains
                    value: "@sha256:"

---
# Policy 3: Restrict host namespaces and volumes
apiVersion: kyverno.io/v1
kind: ClusterPolicy
metadata:
  name: restrict-host-access
spec:
  validationFailureAction: enforce
  rules:
    - name: no-host-namespace
      match:
        any:
          - resources:
              kinds: [Pod]
      validate:
        message: "Pods must not use host namespaces"
        pattern:
          spec:
            =(hostPID):   false
            =(hostIPC):   false
            =(hostNetwork): false

    - name: no-privileged-containers
      match:
        any:
          - resources:
              kinds: [Pod]
      validate:
        message: "Privileged containers are not allowed"
        foreach:
          - list: "request.object.spec.containers"
            deny:
              conditions:
                - key: "{{ element.securityContext.privileged | default(false) }}"
                  operator: Equals
                  value: true

---
# Policy 4: Mutate — auto-add security context if missing (for dev namespace)
apiVersion: kyverno.io/v1
kind: ClusterPolicy
metadata:
  name: add-default-security-context
spec:
  rules:
    - name: add-security-context
      match:
        any:
          - resources:
              kinds:      [Pod]
              namespaces: [development]  # Only in dev; enforce in prod
      mutate:
        foreach:
          - list: "request.object.spec.containers"
            patchStrategicMerge:
              spec:
                containers:
                  - (name): "{{ element.name }}"
                    securityContext:
                      runAsNonRoot:             true
                      allowPrivilegeEscalation: false
                      readOnlyRootFilesystem:   true
                      capabilities:
                        drop: ["ALL"]

---
# Policy 5: Verify image signatures with Cosign (supply chain security)
apiVersion: kyverno.io/v1
kind: ClusterPolicy
metadata:
  name: verify-image-signatures
spec:
  validationFailureAction: enforce
  rules:
    - name: verify-cosign-signature
      match:
        any:
          - resources:
              kinds: [Pod]
      verifyImages:
        - image: "ghcr.io/yourorg/*"
          attestors:
            - count: 1
              entries:
                - keyless:
                    subject: "https://github.com/yourorg/*"
                    issuer:  "https://token.actions.githubusercontent.com"
                    rekor:
                      url: "https://rekor.sigstore.dev"
          mutateDigest: true  # Automatically pin to digest after verification
```

---

## Chapter 99: Advanced SSRF Bypass Techniques and Defenses

```python
# Python — Advanced SSRF bypass techniques and comprehensive defenses

# ALL the ways attackers try to bypass SSRF filters:

SSRF_BYPASS_TECHNIQUES = {
    "IP encoding": [
        "http://2130706433/",           # 127.0.0.1 in decimal
        "http://0x7f000001/",           # 127.0.0.1 in hex
        "http://0177.0.0.1/",           # 127.0.0.1 in octal
        "http://127.0x0.0.01/",         # Mixed encoding
        "http://127.000.000.001/",      # Leading zeros
    ],
    "IPv6": [
        "http://[::1]/",                # IPv6 loopback
        "http://[::ffff:127.0.0.1]/",  # IPv4-mapped IPv6
        "http://[0:0:0:0:0:ffff:127.0.0.1]/",
    ],
    "Protocol bypass": [
        "file:///etc/passwd",
        "gopher://internal-service:6379/_INFO",  # Redis via gopher
        "dict://internal:11211/stats",           # Memcached
        "sftp://internal/etc/passwd",
        "ldap://internal:389/",
        "ftp://internal/",
    ],
    "DNS rebinding": [
        # External domain that resolves to 127.0.0.1 after initial resolution
        "http://attacker.com/",  # DNS rebinds to 127.0.0.1 after allowlist check
    ],
    "Redirect chain": [
        # Target URL redirects to internal resource
        "http://trusted-redirect.com/?url=http://169.254.169.254/",
    ],
    "URL parsing inconsistency": [
        "http://trusted.com@internal.host/",   # URL authority confusion
        "http://internal.host#trusted.com",    # Fragment confusion
        "http://trusted.com\\@internal.host/", # Backslash confusion
    ],
    "Cloud metadata endpoints": [
        "http://169.254.169.254/",                      # AWS/Azure/GCP
        "http://metadata.google.internal/",              # GCP
        "http://169.254.169.254/latest/meta-data/",     # AWS
        "http://[fd00:ec2::254]/latest/meta-data/",     # AWS IPv6
        "http://metadata.azure.com/",                    # Azure
        "http://100.100.100.200/",                       # Alibaba Cloud
    ],
}

import ipaddress
import socket
import re
from urllib.parse import urlparse

class AdvancedSSRFProtection:
    """
    Defense against all known SSRF bypass techniques.
    Must be applied server-side before EVERY external HTTP request.
    """

    BLOCKED_IP_RANGES = [
        ipaddress.ip_network("0.0.0.0/8"),
        ipaddress.ip_network("10.0.0.0/8"),
        ipaddress.ip_network("100.64.0.0/10"),
        ipaddress.ip_network("127.0.0.0/8"),
        ipaddress.ip_network("169.254.0.0/16"),   # Link-local + metadata
        ipaddress.ip_network("172.16.0.0/12"),
        ipaddress.ip_network("192.0.2.0/24"),
        ipaddress.ip_network("192.168.0.0/16"),
        ipaddress.ip_network("198.18.0.0/15"),
        ipaddress.ip_network("198.51.100.0/24"),
        ipaddress.ip_network("203.0.113.0/24"),
        ipaddress.ip_network("224.0.0.0/4"),       # Multicast
        ipaddress.ip_network("240.0.0.0/4"),       # Reserved
        ipaddress.ip_network("255.255.255.255/32"),
        # IPv6
        ipaddress.ip_network("::1/128"),           # Loopback
        ipaddress.ip_network("fc00::/7"),          # Unique local
        ipaddress.ip_network("fe80::/10"),         # Link-local
        ipaddress.ip_network("fd00:ec2::/32"),     # AWS IPv6 metadata
        ipaddress.ip_network("ff00::/8"),          # Multicast
    ]

    ALLOWED_SCHEMES  = frozenset({"http", "https"})
    ALLOWED_PORTS    = frozenset({80, 443, 8080, 8443})

    def validate(self, url: str) -> tuple[bool, str]:
        """
        Returns (is_safe, reason).
        ALWAYS call this before making an HTTP request to a user-provided URL.
        """
        # Step 1: Parse URL
        try:
            parsed = urlparse(url)
        except Exception as e:
            return False, f"URL parse error: {e}"

        # Step 2: Scheme check — only http/https
        if parsed.scheme.lower() not in self.ALLOWED_SCHEMES:
            return False, f"Scheme not allowed: {parsed.scheme}"

        # Step 3: Check for URL authority bypass ─────────────────────────────
        # user:pass@host or user@host — attacker uses trusted.com@evil.com
        if "@" in parsed.netloc:
            return False, "URL contains @ — possible host confusion attack"

        hostname = parsed.hostname
        if not hostname:
            return False, "URL has no hostname"

        # Step 4: Port check
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        if port not in self.ALLOWED_PORTS:
            return False, f"Port not allowed: {port}"

        # Step 5: Block localhost variants
        if hostname.lower() in ("localhost", "ip6-localhost", "ip6-loopback"):
            return False, f"Hostname is localhost variant: {hostname}"

        # Step 6: DNS resolution with IP range check
        # This is the CRITICAL step — bypasses DNS-based attacks
        try:
            # Use getaddrinfo for IPv6-aware resolution
            results = socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
        except socket.gaierror as e:
            return False, f"DNS resolution failed: {e}"

        for (family, _, _, _, sockaddr) in results:
            ip_str = sockaddr[0]
            try:
                ip = ipaddress.ip_address(ip_str)
            except ValueError:
                continue

            # Check against all blocked ranges
            for blocked_range in self.BLOCKED_IP_RANGES:
                if ip in blocked_range:
                    return False, f"IP {ip} is in blocked range {blocked_range}"

        # Step 7: Anti-rebinding — resolve AGAIN right before connecting
        # (HTTP library should use the same resolved IP)
        # This prevents DNS rebinding attacks where:
        # First resolution: legitimate public IP (passes check)
        # Second resolution (at connection time): 127.0.0.1
        # Solution: resolve once and connect to IP directly, not hostname

        return True, "OK"

    def make_safe_request(self, url: str, **kwargs) -> "httpx.Response":
        """Make HTTP request to user-provided URL with SSRF protection"""
        import httpx

        is_safe, reason = self.validate(url)
        if not is_safe:
            raise ValueError(f"SSRF blocked: {reason}")

        # Use resolved IP directly to prevent DNS rebinding
        parsed = urlparse(url)
        hostname = parsed.hostname
        ip = socket.gethostbyname(hostname)  # Final resolution

        # Build URL with IP instead of hostname
        safe_url = url.replace(hostname, ip, 1)

        return httpx.get(
            safe_url,
            headers={"Host": hostname},  # Preserve original Host header
            follow_redirects=False,       # Don't follow redirects (may point to internal)
            timeout=10,
            verify=True,
        )
```

---

# PART 57 — WEBASSEMBLY SECURITY

---

## Chapter 100: Security for WASM Applications

```typescript
// TypeScript — Secure WebAssembly usage patterns

class WASMSecurityManager {
    private moduleCache: Map<string, WebAssembly.Module> = new Map();

    /**
     * WASM Security Principles:
     * 1. Memory isolation: WASM runs in a sandboxed linear memory space
     * 2. No direct DOM access: must go through explicit JS bindings
     * 3. No system calls: can only call imported JS functions
     * 4. Validate imports: WASM can only call functions you explicitly provide
     * 5. SRI for WASM modules: verify integrity before loading
     */

    async loadWASMModule(
        url:       string,
        expectedHash: string,  // SHA-256 hash of the WASM binary
        imports:   WebAssembly.Imports,
    ): Promise<WebAssembly.Instance> {
        // Step 1: Fetch with SRI-equivalent check
        const response = await fetch(url);
        const buffer   = await response.arrayBuffer();

        // Step 2: Verify integrity before instantiation
        const hash = await this.computeHash(buffer);
        if (hash !== expectedHash) {
            throw new Error(`WASM integrity check failed: expected ${expectedHash}, got ${hash}`);
        }

        // Step 3: Cache compiled module (avoid re-compilation from modified source)
        let module = this.moduleCache.get(expectedHash);
        if (!module) {
            module = await WebAssembly.compile(buffer);
            this.moduleCache.set(expectedHash, module);
        }

        // Step 4: Instantiate with controlled imports
        // WASM can ONLY call functions explicitly provided here
        const secureImports = this.createSecureImports(imports);
        return WebAssembly.instantiate(module, secureImports);
    }

    private createSecureImports(
        userImports: WebAssembly.Imports
    ): WebAssembly.Imports {
        // Wrap all imported functions to add logging and validation
        const secure: WebAssembly.Imports = {};

        for (const [namespace, funcs] of Object.entries(userImports)) {
            secure[namespace] = {};
            for (const [funcName, func] of Object.entries(funcs as object)) {
                if (typeof func === 'function') {
                    // Wrap with security controls
                    (secure[namespace] as Record<string, unknown>)[funcName] = (...args: unknown[]) => {
                        // Log all WASM→JS function calls
                        console.debug(`WASM calling: ${namespace}.${funcName}`, args);

                        // Validate arguments (WASM can pass integers, not objects)
                        for (const arg of args) {
                            if (typeof arg === 'object') {
                                throw new Error(`WASM passed object to ${funcName} — unexpected`);
                            }
                        }

                        return (func as Function)(...args);
                    };
                }
            }
        }

        return secure;
    }

    // WASM linear memory: validate all pointer operations
    safeReadString(memory: WebAssembly.Memory, ptr: number, maxLen: number = 1024): string {
        const bytes = new Uint8Array(memory.buffer, ptr);
        const len   = bytes.indexOf(0);  // Find null terminator

        if (len === -1 || len > maxLen) {
            throw new RangeError(`Invalid string pointer or length too large: ${len}`);
        }

        // Bounds check: ensure ptr + len doesn't exceed memory
        if (ptr < 0 || ptr + len > memory.buffer.byteLength) {
            throw new RangeError(`WASM memory access out of bounds: ptr=${ptr}, len=${len}`);
        }

        return new TextDecoder().decode(bytes.subarray(0, len));
    }

    safeWriteToMemory(
        memory: WebAssembly.Memory,
        ptr:    number,
        data:   Uint8Array,
        maxLen: number,
    ): void {
        // Validate bounds before write
        if (ptr < 0 || ptr + data.length > memory.buffer.byteLength) {
            throw new RangeError(`WASM write would exceed memory bounds`);
        }

        if (data.length > maxLen) {
            throw new RangeError(`WASM write data too large: ${data.length} > ${maxLen}`);
        }

        new Uint8Array(memory.buffer, ptr, data.length).set(data);
    }

    private async computeHash(buffer: ArrayBuffer): Promise<string> {
        const hashBuffer = await crypto.subtle.digest('SHA-256', buffer);
        return Array.from(new Uint8Array(hashBuffer))
            .map(b => b.toString(16).padStart(2, '0'))
            .join('');
    }
}

// Content Security Policy for WASM
// Required CSP directives for WASM:
// script-src: must include 'wasm-unsafe-eval' (or 'unsafe-eval' in older browsers)
// BUT prefer 'wasm-unsafe-eval' which is more restrictive

const WASM_CSP = [
    "default-src 'none'",
    "script-src 'self' 'wasm-unsafe-eval'",  // Only allow WASM eval, not JS eval
    "connect-src 'self'",
].join('; ');
```

---

## Chapter 101: The Master Security Implementation Reference

### Complete Vulnerability Quick-Fix Index

```
VULNERABILITY           PRIORITY  LANGUAGE-AGNOSTIC FIX              ESTIMATED TIME
═══════════════════════════════════════════════════════════════════════════════════════════
SQL Injection           CRITICAL  Parameterized queries + ORM         2-4 hours
Command Injection       CRITICAL  Argument list, no shell             1-2 hours
SSRF                    CRITICAL  IP allowlist + range check          4-8 hours
Path Traversal          CRITICAL  Path.resolve() + allowlist check    2-4 hours
XXE                     CRITICAL  Disable DOCTYPE in XML parser       1 hour
Insecure Deserialization CRITICAL Reject pickle/Java serial, use JSON 4-8 hours
SSTI                    CRITICAL  Never concat user input to template  2-4 hours
Hardcoded Secrets       CRITICAL  Move to Vault/Secrets Manager       1-2 days
RCE via eval()          CRITICAL  Remove eval(), use AST parsing      4 hours
JWT alg:none            CRITICAL  Whitelist algorithm in verifier     30 min
Missing AuthN           CRITICAL  Add authentication middleware       4-8 hours
Missing AuthZ           HIGH      Add ownership check to all queries  1-3 days
IDOR                    HIGH      Scope query to user context         1-2 days
Mass Assignment         HIGH      Explicit schema, extra="forbid"     2-4 hours
XSS (Stored)            HIGH      Output encoding + DOMPurify + CSP  4-8 hours
XSS (Reflected)         HIGH      Output encoding, CSP               2-4 hours
Prototype Pollution     HIGH      Schema validation, no direct merge  2-4 hours
CSRF                    HIGH      SameSite=Strict + CSRF token        4-8 hours
Open Redirect           MEDIUM    Allowlist redirect targets          1-2 hours
Clickjacking            MEDIUM    X-Frame-Options: DENY + CSP         30 min
Missing HSTS            MEDIUM    Add Strict-Transport-Security       30 min
Weak TLS                MEDIUM    Disable TLS 1.0/1.1 in config      1 hour
Insecure Cookies        MEDIUM    Add HttpOnly+Secure+SameSite        1 hour
Missing Rate Limiting   MEDIUM    Add rate limiter middleware         2-4 hours
Stack Trace Exposure    MEDIUM    Generic error messages in prod      1-2 hours
Verbose Error Messages  MEDIUM    Sanitize all error responses        2-4 hours
Missing SRI             LOW       Add integrity= to CDN resources     2 hours
Directory Listing       LOW       Disable in web server config        30 min
Server Version Expose   LOW       Remove Server header                30 min
```

### Security Testing Quick Reference

```
TESTING TYPE      TOOL                    WHEN                    TIME INVESTMENT
═══════════════════════════════════════════════════════════════════════════════════
SAST              Semgrep + CodeQL        Every PR               Automated (CI)
SCA               Trivy + Snyk            Every build            Automated (CI)
Secret scan       Gitleaks                Pre-commit + CI        Automated
Container scan    Trivy                   Every image build      Automated
DAST              OWASP ZAP               Pre-prod deploy        Automated (~30 min)
API fuzzing       Schemathesis/Burp       Monthly                4-8 hours
Pen test          Internal/external       Quarterly/Annually     1-5 days
Bug bounty        HackerOne/Bugcrowd      Continuous             Ongoing
Threat model      STRIDE workshop         Per major feature      4-8 hours
Red team          External team           Annually               1-2 weeks
Security chaos    Internal                Monthly                2-4 hours
```

### Final Security Architecture Decision Record

```
ARCHITECTURE DECISION: API Authentication

CONTEXT: Building a public-facing REST API with mobile and web clients.

OPTIONS EVALUATED:
  A. API Keys (static, long-lived)
     Pro: Simple to implement
     Con: No expiry, no user context, credential stuffing risk
     Verdict: REJECT for user auth; OK for server-to-server

  B. JWT Bearer tokens (short-lived, stateless)
     Pro: Horizontal scaling, no session store
     Con: Revocation requires blacklist or short TTL
     Verdict: ACCEPT with 15-minute TTL + refresh token rotation

  C. Session cookies (server-side, stateful)
     Pro: Instant revocation, simpler token handling
     Con: Requires session store, no horizontal scaling without Redis
     Verdict: ACCEPT for traditional web apps with Redis

  D. Passkeys/WebAuthn (FIDO2)
     Pro: Phishing-resistant, no passwords, excellent UX
     Con: Browser/device support needed, more complex implementation
     Verdict: ACCEPT as primary auth for new systems, JWT for API layer

  E. mTLS (mutual TLS)
     Pro: Strongest possible; certificate-based identity
     Con: Certificate management complexity
     Verdict: ACCEPT for service-to-service; not practical for user auth

DECISION: Passkeys for primary user authentication →
          JWT (15min TTL) for API access →
          Rotating refresh tokens (30 days) in HttpOnly cookie →
          mTLS for service-to-service

RATIONALE: Defense in depth at every layer. Passkeys eliminate phishing.
           Short-lived JWTs limit blast radius of theft. mTLS ensures
           internal services cannot be impersonated.
```

---

*This is Part 8 — the eighth and final volume of the Developer's Cybersecurity Mastery handbook.*

*Covered in this volume: Secure code review methodology (Python AST-based scanner, TypeScript/Java review checklists), Security fuzzing (hypothesis property-based testing, Go native fuzzing engine, Rust cargo-fuzz), Runtime Application Self-Protection (RASP) in Java and Python, Data Loss Prevention patterns (DLP middleware, regex scanning, response blocking), SIEM custom detection rules (Sigma format, ECS-compatible event emission, Elasticsearch queries), Secure stream processing (PySpark Structured Streaming with Kafka TLS, PII masking UDFs), Advanced Kubernetes security with Kyverno (enforce policies, image digest pinning, Cosign signature verification), Advanced SSRF bypass techniques catalog and complete defense implementation, WebAssembly security (integrity verification, import sandboxing, memory bounds checking, CSP for WASM), and the complete Master Security Reference tables (vulnerability quick-fix index, testing reference, architecture decision record template).*

*The complete 8-part series constitutes ~100,000 words across 101 chapters, 15,000+ lines of production-ready code in Java, Python, Go, Rust, TypeScript, C, SQL, HCL, YAML, and Rego, covering every major security domain from foundational secure coding through expert-level AI security, post-quantum cryptography, runtime protection, and organizational security leadership.*
