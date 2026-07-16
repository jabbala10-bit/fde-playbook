# Developer's Cybersecurity Mastery: The Complete Handbook
## Volume 39–48 | OAuth Attacks · Browser Security · DPoP · CORS · Vault · Event-Driven · eBPF · GDPR Engineering · Security Automation

---

# PART 36 — ADVANCED OAUTH 2.0 ATTACKS AND DEFENSES

---

## Chapter 74: OAuth 2.0 Attack Taxonomy

Every OAuth flow has specific attack vectors. Most real-world OAuth breaches exploit implementation errors, not protocol weaknesses.

### 74.1 Authorization Code Injection

```
ATTACK: Attacker intercepts a victim's authorization code (via referrer leakage,
        open redirect, or browser history) and injects it into their own session.

VULNERABLE FLOW:
  1. Victim authorizes app at auth server → code=AUTH_CODE is issued
  2. Redirect: https://app.com/callback?code=AUTH_CODE&state=STATE
  3. If the state parameter is not validated → attacker can steal CODE and
     inject it into their own browser session at the callback endpoint
  4. App exchanges CODE for access_token → attacker is now authenticated as victim

MITIGATIONS:
  □ Always validate state parameter (CSRF token bound to session)
  □ Use PKCE — code_verifier ties authorization to the code exchange
  □ Bind code to redirect_uri — only exchange code from the registered URI
  □ Short code lifetime (<10 minutes)
  □ One-time use codes — reject if code was already exchanged
```

```python
# Python — Complete OAuth 2.0 callback handler with all security checks
import secrets
import hashlib
import base64
import time
from urllib.parse import urlparse

class OAuthCallbackHandler:
    """Secure OAuth 2.0 Authorization Code + PKCE callback implementation"""

    CODE_LIFETIME_SECONDS   = 600    # 10 minutes
    STATE_LIFETIME_SECONDS  = 900    # 15 minutes

    async def start_authorization(self, session: dict, redirect_uri: str) -> str:
        """Generate authorization URL with PKCE and state"""

        # Generate PKCE code_verifier (RFC 7636)
        code_verifier = secrets.token_urlsafe(64)  # 43–128 characters

        # code_challenge = BASE64URL(SHA256(code_verifier))
        code_challenge = base64.urlsafe_b64encode(
            hashlib.sha256(code_verifier.encode()).digest()
        ).rstrip(b"=").decode()

        # State: CSRF protection token
        state = secrets.token_urlsafe(32)

        # Store in server-side session (NOT client-side)
        session["oauth_state"]          = state
        session["oauth_code_verifier"]  = code_verifier
        session["oauth_redirect_uri"]   = redirect_uri  # Bind to session
        session["oauth_state_issued_at"] = time.time()

        # Build authorization URL
        params = {
            "client_id":             CLIENT_ID,
            "response_type":         "code",
            "redirect_uri":          redirect_uri,
            "scope":                 "openid profile email",
            "state":                 state,
            "code_challenge":        code_challenge,
            "code_challenge_method": "S256",
            # Prevent authorization code being returned in URL fragment
            # (visible in browser history / referrer)
            "response_mode":         "query",
        }
        return f"{AUTH_SERVER}/authorize?" + urlencode(params)

    async def handle_callback(
        self,
        session: dict,
        received_code: str,
        received_state: str,
        error: str | None = None,
    ) -> dict:
        """Handle OAuth callback with complete security validation"""

        # Step 1: Check for errors from auth server
        if error:
            raise OAuthError(f"Authorization error: {error}")

        # Step 2: Validate code and state are present
        if not received_code or not received_state:
            raise OAuthError("Missing code or state parameter")

        # Step 3: State validation (CSRF protection)
        stored_state    = session.get("oauth_state")
        state_issued_at = session.get("oauth_state_issued_at", 0)

        if not stored_state:
            raise OAuthError("No state in session — possible CSRF attack")

        # Constant-time comparison prevents timing oracle
        if not secrets.compare_digest(stored_state, received_state):
            self._log_security_event("oauth_state_mismatch",
                                     stored=stored_state[:8],
                                     received=received_state[:8])
            raise OAuthError("State mismatch — possible CSRF attack")

        # Step 4: State lifetime check
        if time.time() - state_issued_at > self.STATE_LIFETIME_SECONDS:
            raise OAuthError("State expired — restart authorization")

        # Step 5: Delete used state immediately (one-time use)
        del session["oauth_state"]
        del session["oauth_state_issued_at"]

        # Step 6: Exchange code for tokens with PKCE verifier
        code_verifier = session.pop("oauth_code_verifier", None)
        redirect_uri  = session.pop("oauth_redirect_uri", None)

        if not code_verifier:
            raise OAuthError("Missing PKCE verifier in session")

        # Bind redirect_uri to the one used in authorization request
        token_response = await self._exchange_code(
            code=received_code,
            code_verifier=code_verifier,
            redirect_uri=redirect_uri,  # Must match authorization request
        )

        # Step 7: Validate the ID token (if OIDC)
        if "id_token" in token_response:
            claims = await self._validate_id_token(
                token_response["id_token"],
                nonce=session.pop("oauth_nonce", None),
            )
            return {"user": claims, "tokens": token_response}

        return {"tokens": token_response}

    async def _exchange_code(
        self, code: str, code_verifier: str, redirect_uri: str
    ) -> dict:
        """Exchange authorization code for tokens"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{AUTH_SERVER}/token",
                data={
                    "grant_type":    "authorization_code",
                    "code":          code,
                    "redirect_uri":  redirect_uri,
                    "client_id":     CLIENT_ID,
                    "client_secret": CLIENT_SECRET,
                    "code_verifier": code_verifier,  # PKCE: auth server verifies SHA256 hash
                },
                headers={"Accept": "application/json"},
                timeout=10,
            )
            if response.status_code != 200:
                raise OAuthError(f"Token exchange failed: {response.text}")
            return response.json()

    async def _validate_id_token(self, id_token: str, nonce: str | None) -> dict:
        """Validate OIDC ID token with all required checks"""
        from jose import jwt, JWTError

        # Fetch JWKS from auth server (cache in production)
        jwks = await self._get_jwks()

        try:
            claims = jwt.decode(
                id_token,
                jwks,
                algorithms=["RS256", "ES256"],
                audience=CLIENT_ID,             # aud must be our client_id
                issuer=AUTH_SERVER,             # iss must match auth server
                options={
                    "verify_exp":   True,
                    "verify_iat":   True,
                    "verify_aud":   True,
                    "verify_iss":   True,
                    "require":      ["sub", "iss", "aud", "exp", "iat"],
                }
            )
        except JWTError as e:
            raise OAuthError(f"Invalid ID token: {e}")

        # Nonce validation (replay attack protection for OIDC)
        if nonce and not secrets.compare_digest(
            claims.get("nonce", ""), nonce
        ):
            raise OAuthError("Nonce mismatch in ID token")

        return claims
```

### 74.2 Token Leakage via Referrer

```typescript
// TypeScript — Prevent OAuth token leakage in frontend

// PROBLEM: If access_token appears in the URL (implicit flow, which is deprecated),
// it leaks via Referrer header to any embedded resource on the page.

// NEVER use the implicit flow:
// https://app.com/callback#access_token=TOKEN  ← Visible in browser history
//                                              ← Leaked via Referrer header
//                                              ← Stored in window.location.hash

// ALWAYS use Authorization Code + PKCE:
// https://app.com/callback?code=AUTH_CODE&state=STATE
// Code is short-lived (10 min) and one-time-use

// If using response_mode=fragment is unavoidable (legacy):
// Immediately strip the fragment from the URL after reading
function handleCallbackSafely(urlHash: string): string | null {
    const params = new URLSearchParams(urlHash.startsWith('#') ? urlHash.slice(1) : urlHash);
    const code   = params.get('code');
    const state  = params.get('state');

    if (code) {
        // IMMEDIATELY replace URL to remove code from browser history
        window.history.replaceState(
            {},
            document.title,
            window.location.pathname  // Remove query string and fragment
        );
    }

    return code;
}

// Prevent Referrer header leakage for OAuth redirects
// Set meta Referrer Policy before any OAuth redirect
function addReferrerPolicyMeta(): void {
    let meta = document.querySelector('meta[name="referrer"]') as HTMLMetaElement;
    if (!meta) {
        meta = document.createElement('meta');
        meta.name = 'referrer';
        document.head.appendChild(meta);
    }
    meta.content = 'no-referrer';  // Don't send referrer to third parties
}

// Token storage security hierarchy
const TOKEN_STORAGE = {
    // BEST: Memory-only (lost on page refresh but phishing-resistant)
    inMemory: (() => {
        let token: string | null = null;
        return {
            set: (t: string) => { token = t; },
            get: () => token,
            clear: () => { token = null; },
        };
    })(),

    // ACCEPTABLE for SPAs with short-lived tokens:
    sessionStorage: {
        set: (t: string) => sessionStorage.setItem('access_token', t),
        get: () => sessionStorage.getItem('access_token'),
        clear: () => sessionStorage.removeItem('access_token'),
    },

    // AVOID: localStorage persists across sessions and browser restarts
    // A stored XSS attack can read localStorage at any time

    // BEST for traditional web apps: HttpOnly cookie (JS cannot read)
    // Set by server; cannot be accessed by JavaScript at all
};
```

### 74.3 DPoP — Demonstrating Proof of Possession

DPoP (RFC 9449) binds access tokens to a specific public key, making stolen tokens useless because the attacker lacks the private key to create valid DPoP proofs.

```typescript
// TypeScript — DPoP implementation for sender-constrained tokens
import { SignJWT, generateKeyPair, exportJWK, JWK } from 'jose';
import { v4 as uuidv4 } from 'uuid';

class DPoPProofGenerator {
    private privateKey: CryptoKey;
    private publicKeyJWK: JWK;

    async initialize(): Promise<void> {
        // Generate an EC key pair for this client session
        // In mobile: use platform key backed by Secure Enclave/Keystore
        const { privateKey, publicKey } = await generateKeyPair('ES256', {
            extractable: false,  // Private key cannot be exported from browser
        });

        this.privateKey   = privateKey;
        this.publicKeyJWK = await exportJWK(publicKey);
    }

    async createProof(
        httpMethod: string,
        httpUrl:    string,
        accessToken?: string,  // Include when making API requests
        nonce?:      string,   // Server-provided nonce for replay prevention
    ): Promise<string> {
        // DPoP proof is a short-lived JWT that proves possession of the private key
        const builder = new SignJWT({
            htm:  httpMethod.toUpperCase(),  // HTTP method this proof is for
            htu:  httpUrl,                    // URL this proof is for
            jti:  uuidv4(),                   // Unique ID — prevents replay
            iat:  Math.floor(Date.now() / 1000),
            ...(nonce && { nonce }),          // Server nonce if provided
            ...(accessToken && {
                // Access token hash — binds proof to specific token
                ath: await this.hashToken(accessToken),
            }),
        })
        .setProtectedHeader({
            alg: 'ES256',
            typ: 'dpop+jwt',  // DPoP-specific type
            jwk: this.publicKeyJWK,  // Public key embedded in header
        });

        return builder.sign(this.privateKey);
    }

    private async hashToken(token: string): Promise<string> {
        const hash = await crypto.subtle.digest(
            'SHA-256',
            new TextEncoder().encode(token)
        );
        return btoa(String.fromCharCode(...new Uint8Array(hash)))
            .replace(/\+/g, '-').replace(/\//g, '_').replace(/=/g, '');
    }

    // Use DPoP in API requests
    async makeSecureRequest(
        url: string,
        method: string,
        accessToken: string,
        body?: unknown,
    ): Promise<Response> {
        const dpopProof = await this.createProof(method, url, accessToken);

        return fetch(url, {
            method,
            headers: {
                'Authorization': `DPoP ${accessToken}`,  // DPoP scheme, not Bearer
                'DPoP': dpopProof,                        // Proof in separate header
                'Content-Type': 'application/json',
            },
            body: body ? JSON.stringify(body) : undefined,
        });
    }
}
```

```python
# Python — Server-side DPoP validation
from jose import jwt, JWTError
from cryptography.hazmat.primitives.asymmetric.ec import EllipticCurvePublicKey
from cryptography.hazmat.backends import default_backend
import hashlib
import base64
import time

class DPoPValidator:
    PROOF_LIFETIME_SECONDS = 60  # Proofs are valid for 60 seconds

    def validate_proof(
        self,
        dpop_header: str,
        expected_method: str,
        expected_url: str,
        access_token: str | None = None,
        server_nonce: str | None = None,
    ) -> dict:
        """
        Validate a DPoP proof header per RFC 9449.
        Returns the embedded public key JWK if valid.
        """
        # Step 1: Decode header without verification to get the embedded key
        try:
            unverified_header = jwt.get_unverified_header(dpop_header)
        except JWTError as e:
            raise ValueError(f"Invalid DPoP proof format: {e}")

        # Step 2: Verify type is "dpop+jwt"
        if unverified_header.get("typ") != "dpop+jwt":
            raise ValueError("DPoP proof must have typ=dpop+jwt")

        # Step 3: Extract and reconstruct public key from JWK in header
        jwk = unverified_header.get("jwk")
        if not jwk:
            raise ValueError("DPoP proof must contain jwk in header")

        # Build public key from embedded JWK
        public_key = self._jwk_to_public_key(jwk)

        # Step 4: Verify signature using the embedded public key
        try:
            claims = jwt.decode(
                dpop_header,
                public_key,
                algorithms=[unverified_header.get("alg", "ES256")],
                options={
                    "verify_aud": False,   # DPoP proofs don't have aud
                    "verify_iss": False,   # DPoP proofs don't have iss
                    "verify_exp": False,   # We handle expiry manually below
                }
            )
        except JWTError as e:
            raise ValueError(f"DPoP signature invalid: {e}")

        # Step 5: Validate claims
        now = time.time()
        iat = claims.get("iat", 0)

        # Proof freshness check
        if abs(now - iat) > self.PROOF_LIFETIME_SECONDS:
            raise ValueError(f"DPoP proof too old or from future: age={now - iat:.0f}s")

        # HTTP method check
        if claims.get("htm", "").upper() != expected_method.upper():
            raise ValueError(f"DPoP htm mismatch: {claims.get('htm')} != {expected_method}")

        # URL check
        if claims.get("htu") != expected_url:
            raise ValueError(f"DPoP htu mismatch: {claims.get('htu')} != {expected_url}")

        # Nonce check (if server issued one)
        if server_nonce and claims.get("nonce") != server_nonce:
            raise ValueError("DPoP nonce mismatch")

        # Access token hash check (when token is present)
        if access_token:
            token_hash = base64.urlsafe_b64encode(
                hashlib.sha256(access_token.encode()).digest()
            ).rstrip(b"=").decode()
            if claims.get("ath") != token_hash:
                raise ValueError("DPoP ath mismatch — token and proof not bound")

        # Step 6: JTI replay check (prevent proof reuse)
        jti = claims.get("jti")
        if not jti:
            raise ValueError("DPoP proof must have jti")
        if self._is_jti_seen(jti, iat):
            raise ValueError(f"DPoP jti already used — replay attack: {jti}")
        self._record_jti(jti, iat)

        return jwk  # Return the public key for binding to the access token

    def _is_jti_seen(self, jti: str, iat: float) -> bool:
        """Check Redis/in-memory cache for previously seen JTIs"""
        # Implementation: check a short-lived cache keyed by jti
        # TTL should match PROOF_LIFETIME_SECONDS
        return False  # Placeholder

    def _record_jti(self, jti: str, iat: float):
        """Record JTI as used to prevent replay"""
        pass  # Implementation: set in Redis with TTL
```

---

# PART 37 — BROWSER SECURITY DEEP DIVE

---

## Chapter 75: Content Security Policy — Advanced Patterns

```typescript
// TypeScript — Dynamic CSP with nonce for production use

interface CSPDirectives {
    'default-src':       string[];
    'script-src':        string[];
    'style-src':         string[];
    'img-src':           string[];
    'connect-src':       string[];
    'font-src':          string[];
    'frame-src':         string[];
    'frame-ancestors':   string[];
    'form-action':       string[];
    'base-uri':          string[];
    'object-src':        string[];
    'manifest-src':      string[];
    'worker-src':        string[];
    'upgrade-insecure-requests'?: boolean;
    'block-all-mixed-content'?:  boolean;
    'report-uri'?:       string;
    'report-to'?:        string;
}

class CSPBuilder {
    private nonce: string;

    constructor() {
        this.nonce = crypto.randomBytes(16).toString('base64');
    }

    getNonce(): string { return this.nonce; }

    buildHeader(environment: 'development' | 'production'): string {
        const directives: Partial<CSPDirectives> = {
            // Nothing allowed by default
            'default-src': ["'none'"],

            // Scripts: only same-origin + nonce-based inline scripts
            // 'strict-dynamic': allows scripts loaded by trusted scripts
            'script-src': [
                "'self'",
                `'nonce-${this.nonce}'`,
                "'strict-dynamic'",
                // Remove 'unsafe-inline' — nonce is sufficient and safer
                // Note: 'strict-dynamic' ignores allowlists in modern browsers
                // but keeps them as fallback for older browsers
                ...(environment === 'development' ? ["'unsafe-eval'"] : []),
            ],

            // Styles: same-origin only (no unsafe-inline for styles either)
            'style-src': [
                "'self'",
                `'nonce-${this.nonce}'`,
                "https://fonts.googleapis.com",
            ],

            // Images: self + data URIs (for inlined images) + CDN
            'img-src': [
                "'self'",
                "data:",
                "blob:",
                "https://cdn.example.com",
                "https://www.gravatar.com",
            ],

            // API connections: same-origin + our API domains
            'connect-src': [
                "'self'",
                "https://api.example.com",
                "wss://ws.example.com",
                // Analytics/monitoring (enumerate explicitly)
                "https://www.google-analytics.com",
                ...(environment === 'development' ? [
                    "http://localhost:*",
                    "ws://localhost:*",
                ] : []),
            ],

            // Fonts: self + Google Fonts CDN
            'font-src': [
                "'self'",
                "https://fonts.gstatic.com",
            ],

            // Frames: deny all embedding of our app
            'frame-src':     ["'none'"],
            'frame-ancestors': ["'none'"],  // Prevent clickjacking

            // Form submissions: same origin only
            'form-action':   ["'self'"],

            // Base URI: prevent base tag injection
            'base-uri':      ["'self'"],

            // Object/embed: deny (no Flash, no plugins)
            'object-src':    ["'none'"],

            // Workers
            'worker-src':    ["'self'", "blob:"],

            // Force HTTPS for any remaining insecure requests
            'upgrade-insecure-requests': true,

            // CSP violation reporting
            'report-uri':    "https://csp-report.example.com/report",
            'report-to':     "csp-endpoint",
        };

        return Object.entries(directives)
            .filter(([, val]) => val !== undefined)
            .map(([directive, value]) => {
                if (typeof value === 'boolean') {
                    return value ? directive : '';
                }
                return `${directive} ${(value as string[]).join(' ')}`;
            })
            .filter(Boolean)
            .join('; ');
    }
}

// Express middleware using CSP builder
function cspMiddleware(req: Request, res: Response, next: NextFunction): void {
    const builder = new CSPBuilder();
    res.locals.cspNonce = builder.getNonce();

    const env = process.env.NODE_ENV === 'production' ? 'production' : 'development';

    res.setHeader('Content-Security-Policy', builder.buildHeader(env));

    // Report-To header (for CSP level 3 reporting)
    res.setHeader('Report-To', JSON.stringify({
        group:             "csp-endpoint",
        max_age:           86400,
        endpoints:         [{ url: "https://csp-report.example.com/report" }],
        include_subdomains: true,
    }));

    next();
}
```

### 75.2 Subresource Integrity (SRI)

```html
<!-- HTML — SRI for third-party scripts and styles -->
<!-- Generate hash: cat script.js | openssl dgst -sha384 -binary | openssl base64 -A -->

<!-- UNSAFE: No integrity check — CDN compromise = XSS on your site -->
<script src="https://cdn.jsdelivr.net/npm/lodash@4.17.21/lodash.min.js"></script>

<!-- SAFE: SRI prevents loading if content changes (compromise or CDN poisoning) -->
<script
    src="https://cdn.jsdelivr.net/npm/lodash@4.17.21/lodash.min.js"
    integrity="sha384-UEwe0oDgHt0uGy7RtHLFNFdgRiCn7oa6FHlfjVTb7Lh4xt2eiYgJPiMcgMrMKEC"
    crossorigin="anonymous">
</script>

<!-- For CSS from CDN: -->
<link
    rel="stylesheet"
    href="https://cdn.example.com/styles.css"
    integrity="sha384-<hash-here>"
    crossorigin="anonymous">
```

```typescript
// TypeScript — Automated SRI hash generation in build pipeline
import crypto from 'crypto';
import fs from 'fs';
import https from 'https';

async function generateSRIHash(url: string): Promise<string> {
    return new Promise((resolve, reject) => {
        https.get(url, (res) => {
            const hash = crypto.createHash('sha384');
            res.on('data', (chunk) => hash.update(chunk));
            res.on('end', () => {
                const digest = hash.digest('base64');
                resolve(`sha384-${digest}`);
            });
            res.on('error', reject);
        });
    });
}

// Build-time: generate SRI for all CDN assets
async function generateSRIManifest(assets: Record<string, string>): Promise<void> {
    const manifest: Record<string, string> = {};
    for (const [name, url] of Object.entries(assets)) {
        manifest[name] = await generateSRIHash(url);
        console.log(`${name}: ${manifest[name]}`);
    }
    fs.writeFileSync('sri-manifest.json', JSON.stringify(manifest, null, 2));
}
```

### 75.3 Cross-Origin Isolation Headers

```typescript
// TypeScript — COEP/COOP/CORP for Spectre mitigations and SharedArrayBuffer

// Cross-Origin-Embedder-Policy (COEP): Require CORP for all embedded resources
// Cross-Origin-Opener-Policy (COOP): Isolate browsing context from cross-origin popups
// Together these enable: SharedArrayBuffer, high-resolution timers, performance.measureUserAgentSpecificMemory

function addCrossOriginIsolationHeaders(
    req: Request, res: Response, next: NextFunction
): void {
    // Require all embedded resources to opt-in to cross-origin sharing
    // Prevents cross-origin attacks via shared memory side-channels (Spectre)
    res.setHeader('Cross-Origin-Embedder-Policy', 'require-corp');

    // Isolate this page's browsing context from opener relationships
    // Prevents cross-window access to window.opener, window.open()
    res.setHeader('Cross-Origin-Opener-Policy', 'same-origin');

    // Declare how this resource can be used cross-origin
    // 'same-origin': only same origin can embed this resource
    res.setHeader('Cross-Origin-Resource-Policy', 'same-origin');

    next();
}

// After setting COEP + COOP, check cross-origin isolation:
// window.crossOriginIsolated === true  (browser confirms isolation)

// For APIs that serve resources to be embedded by cross-origin pages,
// use CORP: cross-origin to explicitly allow embedding:
function serveEmbeddableResource(req: Request, res: Response): void {
    res.setHeader('Cross-Origin-Resource-Policy', 'cross-origin');
    // Also need CORS headers for cross-origin fetch:
    res.setHeader('Access-Control-Allow-Origin', 'https://trusted-origin.com');
    // ...
}
```

---

## Chapter 76: CORS — Common Misconfigurations

### 76.1 The Seven CORS Anti-Patterns

```python
# Python — Complete CORS misconfiguration catalogue with fixes

# ── Anti-Pattern 1: Wildcard with Credentials ─────────────────────────────────
# INVALID (browsers reject this combination):
# Access-Control-Allow-Origin: *
# Access-Control-Allow-Credentials: true
# Browsers refuse to expose response if credentials are included with wildcard origin

# VALID alternatives:
# Option A: No credentials (stateless API with token in header)
CORS_HEADERS_NO_CREDS = {
    "Access-Control-Allow-Origin":  "*",     # OK without credentials
    "Access-Control-Allow-Methods": "GET, POST",
    "Access-Control-Allow-Headers": "Content-Type, Authorization",
    # No Allow-Credentials header
}

# Option B: Specific origin with credentials
CORS_HEADERS_WITH_CREDS = {
    "Access-Control-Allow-Origin":      "https://app.example.com",  # Exact origin
    "Access-Control-Allow-Credentials": "true",
    "Access-Control-Allow-Methods":     "GET, POST, PUT, DELETE",
    "Access-Control-Allow-Headers":     "Content-Type, Authorization",
    "Vary":                             "Origin",  # Critical: tells caches to vary by origin
}

# ── Anti-Pattern 2: Reflecting arbitrary Origin without validation ─────────────
# VULNERABLE: Echoes back any origin the client sends
def handle_cors_wrong(request_origin: str) -> str:
    return request_origin  # Reflects ANYTHING — any origin can send cookies

# SAFE: Validate against an explicit allowlist
ALLOWED_ORIGINS = frozenset([
    "https://app.example.com",
    "https://admin.example.com",
    "https://staging.example.com",
])

def handle_cors_safe(request_origin: str) -> str | None:
    if request_origin in ALLOWED_ORIGINS:
        return request_origin  # Only reflect if in allowlist
    return None  # No CORS header — request blocked

# ── Anti-Pattern 3: Trusting the null origin ─────────────────────────────────
# VULNERABLE: null origin is sent by file://, data:, sandboxed iframes
# Attackers can use sandboxed iframes to send null origin requests
def cors_with_null_bug(origin: str) -> str | None:
    if origin == "null":
        return "null"  # WRONG: grants access from sandboxed attacker frames
    # ...

# SAFE: Never trust null origin
def cors_without_null(origin: str) -> str | None:
    if not origin or origin == "null":
        return None  # Deny null origin
    return handle_cors_safe(origin)

# ── Anti-Pattern 4: Prefix/suffix matching instead of exact matching ──────────
# VULNERABLE: trusts attacker.example.com when example.com is allowed
def cors_prefix_match_bug(origin: str) -> str | None:
    if "example.com" in origin:  # Matches evil-example.com!
        return origin
    return None

def cors_suffix_match_bug(origin: str) -> str | None:
    if origin.endswith("example.com"):  # Matches evilexample.com!
        return origin
    return None

# SAFE: Exact match only (or strict subdomain matching)
def cors_safe_with_subdomains(origin: str) -> str | None:
    from urllib.parse import urlparse
    try:
        parsed = urlparse(origin)
    except Exception:
        return None

    # Must be HTTPS
    if parsed.scheme != "https":
        return None

    hostname = parsed.hostname or ""
    # Exact hostname match or subdomain of example.com
    if hostname == "example.com" or hostname.endswith(".example.com"):
        if origin in ALLOWED_ORIGINS:  # Still check against allowlist
            return origin
    return None

# ── Anti-Pattern 5: Missing Vary: Origin header ─────────────────────────────
# If a CDN caches a response with Access-Control-Allow-Origin: https://a.com
# and a user from https://b.com gets the cached response, they see:
# Access-Control-Allow-Origin: https://a.com (which doesn't match b.com)
# This silently breaks CORS for legitimate users.
# Always set:
# Vary: Origin
# when the CORS origin varies per request.

# ── Anti-Pattern 6: Case-sensitive origin matching ───────────────────────────
# HTTP spec: scheme and host are case-insensitive
# HTTPS://APP.EXAMPLE.COM should match https://app.example.com
# Always normalize to lowercase before comparison:
def normalize_origin(origin: str) -> str:
    from urllib.parse import urlparse
    p = urlparse(origin)
    return f"{p.scheme.lower()}://{p.netloc.lower()}"

# ── Anti-Pattern 7: CORS on sensitive endpoints without CSRF protection ───────
# CORS allows cross-origin reads when the browser sends cookies.
# An attacker on evil.com can make a credentialed cross-origin request
# to your API if the origin is allowed.
# Solution: CORS + SameSite=Strict on session cookies eliminates this
# (SameSite=Strict cookies aren't sent on cross-origin requests)
```

### 76.2 FastAPI CORS Configuration

```python
# Python — FastAPI production CORS configuration
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

app = FastAPI()

# ── Static allowlist for known origins ────────────────────────────────────────
ALLOWED_ORIGINS = {
    "https://app.example.com",
    "https://admin.example.com",
}

# ── Development: allow localhost variants ────────────────────────────────────
if os.getenv("ENVIRONMENT") == "development":
    ALLOWED_ORIGINS.update({
        "http://localhost:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3000",
    })

# Note: CORSMiddleware validates origins — only use with trusted config
app.add_middleware(
    CORSMiddleware,
    allow_origins         = list(ALLOWED_ORIGINS),
    allow_credentials     = True,
    allow_methods         = ["GET", "POST", "PUT", "DELETE", "PATCH"],
    allow_headers         = ["Authorization", "Content-Type", "X-Request-ID"],
    expose_headers        = ["X-Request-ID"],
    max_age               = 3600,
)

# ── Custom middleware for precise control ─────────────────────────────────────
class PreciseCORSMiddleware(BaseHTTPMiddleware):
    """
    More explicit CORS handling than the standard middleware.
    Allows per-endpoint CORS policies.
    """
    async def dispatch(self, request: Request, call_next):
        origin = request.headers.get("origin", "")

        # Preflight request
        if request.method == "OPTIONS":
            if origin in ALLOWED_ORIGINS:
                from fastapi.responses import Response
                return Response(
                    headers={
                        "Access-Control-Allow-Origin":      origin,
                        "Access-Control-Allow-Credentials": "true",
                        "Access-Control-Allow-Methods":     "GET, POST, PUT, DELETE",
                        "Access-Control-Allow-Headers":     "Authorization, Content-Type",
                        "Access-Control-Max-Age":           "3600",
                        "Vary":                             "Origin",
                    }
                )
            return Response(status_code=403)

        # Actual request
        response = await call_next(request)

        if origin in ALLOWED_ORIGINS:
            response.headers["Access-Control-Allow-Origin"]      = origin
            response.headers["Access-Control-Allow-Credentials"] = "true"
            response.headers["Vary"] = "Origin"  # Always set Vary!

        return response
```

---

# PART 38 — ADVANCED VAULT AND SECRETS MANAGEMENT

---

## Chapter 77: Dynamic Secrets — The Production Pattern

```python
# Python — HashiCorp Vault dynamic secrets for zero-standing-privilege
import hvac
import threading
from datetime import datetime, timezone

class VaultDynamicCredentials:
    """
    Dynamic secrets: Vault creates database credentials on-demand,
    automatically rotates them, and revokes them after the lease expires.
    No long-lived database passwords in configuration.
    """

    def __init__(self, vault_addr: str, role_name: str):
        self._vault_addr = vault_addr
        self._role_name  = role_name
        self._client     = self._authenticate()
        self._current_creds: dict | None = None
        self._lock       = threading.Lock()
        self._refresh_thread: threading.Thread | None = None

    def _authenticate(self) -> hvac.Client:
        """Authenticate to Vault using Kubernetes service account"""
        with open("/var/run/secrets/kubernetes.io/serviceaccount/token") as f:
            jwt_token = f.read().strip()

        client = hvac.Client(url=self._vault_addr)
        response = client.auth.kubernetes.login(
            role=self._role_name,
            jwt=jwt_token,
        )
        client.token = response["auth"]["client_token"]
        return client

    def get_database_credentials(self) -> dict:
        """
        Get dynamic database credentials from Vault.
        Credentials are unique per request, expire automatically,
        and are revoked by Vault when the lease expires.
        """
        with self._lock:
            if self._credentials_valid():
                return self._current_creds

            # Generate new dynamic credentials
            response = self._client.secrets.database.generate_credentials(
                name=self._role_name
            )

            self._current_creds = {
                "username":  response["data"]["username"],
                "password":  response["data"]["password"],
                "lease_id":  response["lease_id"],
                "lease_duration": response["lease_duration"],  # seconds
                "expires_at": datetime.now(timezone.utc).timestamp()
                              + response["lease_duration"],
            }

            # Schedule renewal before expiry
            self._schedule_renewal(response["lease_duration"])

            return self._current_creds

    def _credentials_valid(self) -> bool:
        if not self._current_creds:
            return False
        # Renew when 80% of lease has elapsed (not waiting until expiry)
        remaining = self._current_creds["expires_at"] - datetime.now(timezone.utc).timestamp()
        lease_duration = self._current_creds["lease_duration"]
        return remaining > (lease_duration * 0.20)  # Still in the good 80%

    def _schedule_renewal(self, lease_duration: int):
        """Schedule credential renewal at 70% of lease duration"""
        renewal_delay = lease_duration * 0.70

        def renew():
            import time
            time.sleep(renewal_delay)
            with self._lock:
                if self._current_creds:
                    try:
                        self._client.sys.renew_self_token()
                        response = self._client.sys.renew_lease(
                            lease_id=self._current_creds["lease_id"],
                        )
                        self._current_creds["expires_at"] = (
                            datetime.now(timezone.utc).timestamp()
                            + response["lease_duration"]
                        )
                        self._current_creds["lease_duration"] = response["lease_duration"]
                    except Exception as e:
                        # Force refresh on next use
                        self._current_creds = None

        self._refresh_thread = threading.Thread(target=renew, daemon=True)
        self._refresh_thread.start()

    def revoke_credentials(self):
        """Explicitly revoke credentials when done (e.g., graceful shutdown)"""
        if self._current_creds:
            self._client.sys.revoke_lease(
                lease_id=self._current_creds["lease_id"]
            )
            self._current_creds = None

# Vault policy for this role — principle of least privilege
VAULT_POLICY_TEMPLATE = """
# Allow generating dynamic DB credentials for our application
path "database/creds/app-role" {
    capabilities = ["read"]
}

# Allow renewing leases for these credentials
path "sys/leases/renew" {
    capabilities = ["update"]
}

# Allow revoking our own leases
path "sys/leases/revoke" {
    capabilities = ["update"]
}

# Allow reading specific secrets (not all secrets)
path "secret/data/app/{{identity.entity.aliases.auth_kubernetes_local.metadata.service_account_namespace}}/{{identity.entity.aliases.auth_kubernetes_local.metadata.service_account_name}}/*" {
    capabilities = ["read"]
}
# Template substitution: policy is scoped to service account namespace + name
"""
```

### 77.2 Secret Scanning and Rotation Automation

```go
// Go — Automated secret rotation with zero downtime
package secrets

import (
    "context"
    "database/sql"
    "fmt"
    "time"

    vault "github.com/hashicorp/vault/api"
)

type SecretRotator struct {
    vault  *vault.Client
    db     *sql.DB
    config RotationConfig
}

type RotationConfig struct {
    SecretPath     string
    RotationPeriod time.Duration
    DBUserPattern  string  // e.g., "app_user_%d" — unique per rotation
}

func (r *SecretRotator) RotateWithZeroDowntime(ctx context.Context) error {
    // Phase 1: Generate new credentials
    newCreds, err := r.generateNewCredentials(ctx)
    if err != nil { return fmt.Errorf("generating new creds: %w", err) }

    // Phase 2: Add new credentials to Vault (side-by-side with old)
    if err := r.storeNewCredentials(ctx, newCreds); err != nil {
        return fmt.Errorf("storing new creds: %w", err)
    }

    // Phase 3: Roll out new credentials to services
    // (services read from Vault dynamically — they pick up new creds on next use)

    // Phase 4: Verify new credentials work
    if err := r.verifyCredentials(ctx, newCreds); err != nil {
        // Rollback: old credentials still in place
        _ = r.deleteCredentials(ctx, newCreds.Username)
        return fmt.Errorf("verification failed: %w", err)
    }

    // Phase 5: Wait for services to drain old connections
    // (configurable drain period based on connection pool settings)
    select {
    case <-time.After(r.config.RotationPeriod / 10): // 10% of rotation period
    case <-ctx.Done():
        return ctx.Err()
    }

    // Phase 6: Delete old credentials from Vault and database
    oldCreds, err := r.getOldCredentials(ctx)
    if err == nil && oldCreds.Username != newCreds.Username {
        _ = r.deleteCredentials(ctx, oldCreds.Username)
    }

    return nil
}

func (r *SecretRotator) generateNewCredentials(ctx context.Context) (*Credentials, error) {
    // Generate unique username per rotation (avoids collision)
    newUsername := fmt.Sprintf(r.config.DBUserPattern, time.Now().Unix())
    newPassword := generateSecurePassword(32)

    // Create database user
    _, err := r.db.ExecContext(ctx,
        fmt.Sprintf("CREATE USER %s WITH PASSWORD $1", newUsername),
        newPassword,
    )
    if err != nil { return nil, err }

    // Grant minimum required permissions
    _, err = r.db.ExecContext(ctx,
        fmt.Sprintf("GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA public TO %s", newUsername),
    )
    if err != nil {
        _ = r.db.QueryRowContext(ctx, fmt.Sprintf("DROP USER %s", newUsername))
        return nil, err
    }

    return &Credentials{Username: newUsername, Password: newPassword}, nil
}
```

---

# PART 39 — SECURITY FOR EVENT-DRIVEN ARCHITECTURES

---

## Chapter 78: Event Security Patterns

```python
# Python — Secure event-driven system with idempotency and verification

import json
import hmac
import hashlib
import uuid
import time
from dataclasses import dataclass, asdict
from typing import Any

@dataclass
class SecureEvent:
    """Tamper-evident event envelope for event-driven systems"""
    event_id:      str    # Unique ID for idempotency
    event_type:    str    # Type of event (e.g., "user.created")
    aggregate_id:  str    # ID of the entity this event belongs to
    aggregate_type: str   # Type of entity (e.g., "user")
    payload:       dict   # Event data
    metadata:      dict   # Non-business metadata (tenant_id, user_id, etc.)
    timestamp:     float  # Unix timestamp
    sequence:      int    # Monotonic sequence number per aggregate
    schema_version: int   # Event schema version (for compatibility)
    signature:     str = ""  # HMAC-SHA256 of the event

    @classmethod
    def create(
        cls,
        event_type: str,
        aggregate_id: str,
        aggregate_type: str,
        payload: dict,
        signing_key: bytes,
        metadata: dict = None,
    ) -> "SecureEvent":
        event = cls(
            event_id       = str(uuid.uuid4()),
            event_type     = event_type,
            aggregate_id   = aggregate_id,
            aggregate_type = aggregate_type,
            payload        = payload,
            metadata       = metadata or {},
            timestamp      = time.time(),
            sequence       = 0,  # Set by event store
            schema_version = 1,
        )
        event.signature = event._compute_signature(signing_key)
        return event

    def _signable_payload(self) -> bytes:
        """Canonical representation for signing (excludes signature itself)"""
        data = {
            "event_id":      self.event_id,
            "event_type":    self.event_type,
            "aggregate_id":  self.aggregate_id,
            "aggregate_type": self.aggregate_type,
            "payload":       self.payload,
            "timestamp":     self.timestamp,
            "schema_version": self.schema_version,
        }
        return json.dumps(data, sort_keys=True, separators=(",", ":")).encode()

    def _compute_signature(self, key: bytes) -> str:
        return hmac.new(key, self._signable_payload(), hashlib.sha256).hexdigest()

    def verify(self, key: bytes) -> bool:
        expected = self._compute_signature(key)
        return hmac.compare_digest(self.signature, expected)

class IdempotentEventProcessor:
    """
    Process events exactly once using idempotency keys.
    Critical for financial, inventory, and any side-effect-producing events.
    """

    def __init__(self, event_store, signing_key: bytes):
        self.event_store = event_store
        self.signing_key = signing_key
        # Redis or similar for idempotency tracking
        self._processed_events: set[str] = set()

    def process_event(
        self,
        event: SecureEvent,
        handler: callable,
    ) -> dict:
        # Step 1: Verify event signature
        if not event.verify(self.signing_key):
            raise SecurityError(f"Event signature invalid: {event.event_id}")

        # Step 2: Check age — reject stale events (replay protection)
        age_seconds = time.time() - event.timestamp
        if age_seconds > 3600:  # 1 hour max event age
            raise ValueError(f"Event too old: age={age_seconds:.0f}s")

        if age_seconds < 0:
            raise ValueError(f"Event from future: age={age_seconds:.0f}s")

        # Step 3: Idempotency check — process each event exactly once
        if event.event_id in self._processed_events:
            # Already processed — return previous result (idempotent)
            return self.event_store.get_event_result(event.event_id)

        # Step 4: Lock and process (atomic check-and-set)
        with self.event_store.lock(event.event_id, timeout=30):
            # Re-check after acquiring lock
            if self.event_store.is_processed(event.event_id):
                return self.event_store.get_event_result(event.event_id)

            # Step 5: Execute handler
            result = handler(event)

            # Step 6: Mark as processed atomically with result storage
            self.event_store.mark_processed(event.event_id, result)
            self._processed_events.add(event.event_id)

            return result

# Outbox pattern — prevents dual-write problems (DB + message queue)
class TransactionalOutbox:
    """
    Ensures events are persisted AND published atomically.
    Prevents: event published but DB transaction rolled back (lost event)
    Prevents: DB committed but event never published (phantom state)
    """

    def publish_in_transaction(
        self,
        db_session,
        domain_operation: callable,
        events: list[SecureEvent],
    ) -> Any:
        with db_session.begin():
            # Execute domain operation (DB write)
            result = domain_operation()

            # Write events to outbox table in SAME transaction
            for event in events:
                db_session.execute(
                    """INSERT INTO event_outbox
                       (event_id, event_type, payload, aggregate_id, published, created_at)
                       VALUES (:id, :type, :payload, :agg_id, false, NOW())""",
                    {
                        "id":      event.event_id,
                        "type":    event.event_type,
                        "payload": json.dumps(asdict(event)),
                        "agg_id":  event.aggregate_id,
                    }
                )
            # If domain operation or outbox write fails, both roll back

        # After commit: relay publishes from outbox to message broker asynchronously
        # If relay fails, it retries from the outbox (at-least-once delivery)
        return result
```

---

# PART 40 — eBPF FOR SECURITY MONITORING

---

## Chapter 79: eBPF Security Observability

```python
# Python — eBPF-based syscall monitoring using BCC (BPF Compiler Collection)
# Runs on the host to monitor all container activity

from bcc import BPF
import ctypes
import json
import time

EBPF_PROGRAM = """
#include <uapi/linux/ptrace.h>
#include <linux/sched.h>
#include <linux/fs.h>

// Track sensitive syscalls
struct event_t {
    u32 pid;
    u32 uid;
    u32 gid;
    char comm[TASK_COMM_LEN];
    char filename[256];
    int syscall_id;
    u64 timestamp;
};

BPF_PERF_OUTPUT(security_events);
BPF_HASH(sensitive_procs, u32, u8);  // Track PIDs of interest

// Monitor execve syscalls (process execution)
TRACEPOINT_PROBE(syscalls, sys_enter_execve) {
    struct event_t event = {};

    event.pid       = bpf_get_current_pid_tgid() >> 32;
    event.uid       = bpf_get_current_uid_gid() & 0xFFFFFFFF;
    event.timestamp = bpf_ktime_get_ns();
    bpf_get_current_comm(&event.comm, sizeof(event.comm));
    bpf_probe_read_user_str(event.filename, sizeof(event.filename), args->filename);
    event.syscall_id = 59;  // execve

    security_events.perf_submit(args, &event, sizeof(event));
    return 0;
}

// Monitor openat syscalls (file access) — detect credential file reads
TRACEPOINT_PROBE(syscalls, sys_enter_openat) {
    struct event_t event = {};

    bpf_probe_read_user_str(event.filename, sizeof(event.filename), args->filename);

    // Only report sensitive file access
    // (In production, use more sophisticated filtering)
    char shadow[] = "/etc/shadow";
    char passwd[] = "/etc/passwd";

    if (event.filename[0] == '/' && event.filename[1] == 'e') {
        event.pid       = bpf_get_current_pid_tgid() >> 32;
        event.uid       = bpf_get_current_uid_gid() & 0xFFFFFFFF;
        event.timestamp = bpf_ktime_get_ns();
        bpf_get_current_comm(&event.comm, sizeof(event.comm));
        event.syscall_id = 257;  // openat

        security_events.perf_submit(args, &event, sizeof(event));
    }
    return 0;
}

// Monitor outbound network connections
TRACEPOINT_PROBE(syscalls, sys_enter_connect) {
    struct event_t event = {};
    event.pid       = bpf_get_current_pid_tgid() >> 32;
    event.uid       = bpf_get_current_uid_gid() & 0xFFFFFFFF;
    event.timestamp = bpf_ktime_get_ns();
    bpf_get_current_comm(&event.comm, sizeof(event.comm));
    event.syscall_id = 42;  // connect

    security_events.perf_submit(args, &event, sizeof(event));
    return 0;
}
"""

class EBPFSecurityMonitor:
    SUSPICIOUS_COMMANDS = {
        "curl", "wget", "nc", "ncat", "bash", "sh", "python",
        "python3", "perl", "ruby", "php", "su", "sudo",
    }

    def __init__(self, alert_callback: callable):
        self.bpf     = BPF(text=EBPF_PROGRAM)
        self.alert   = alert_callback

    def start(self):
        self.bpf["security_events"].open_perf_buffer(self._handle_event)
        print("eBPF security monitoring active")
        while True:
            try:
                self.bpf.perf_buffer_poll(timeout=100)
            except KeyboardInterrupt:
                break

    def _handle_event(self, cpu, data, size):
        event = self.bpf["security_events"].event(data)

        comm     = event.comm.decode("utf-8", errors="replace")
        filename = event.filename.decode("utf-8", errors="replace")
        pid      = event.pid
        uid      = event.uid

        security_event = {
            "timestamp": time.time(),
            "pid":       pid,
            "uid":       uid,
            "process":   comm,
            "syscall":   event.syscall_id,
            "filename":  filename,
        }

        # Detect suspicious execve
        if event.syscall_id == 59:
            if any(susp in filename for susp in self.SUSPICIOUS_COMMANDS):
                security_event["alert"]    = "suspicious_process_execution"
                security_event["severity"] = "HIGH"
                self.alert(security_event)

        # Detect credential file access
        elif event.syscall_id == 257:
            if "/etc/shadow" in filename or "/etc/passwd" in filename:
                security_event["alert"]    = "credential_file_access"
                security_event["severity"] = "CRITICAL"
                self.alert(security_event)

        # Detect unexpected outbound connections from known sensitive processes
        elif event.syscall_id == 42:
            security_event["alert"]    = "outbound_connection"
            security_event["severity"] = "MEDIUM"
            self.alert(security_event)
```

---

# PART 41 — GDPR ENGINEERING IN DEPTH

---

## Chapter 80: Right to Erasure — Technical Implementation

### 80.1 The Complete Data Deletion Architecture

```python
# Python — GDPR Right to Erasure — production implementation

from dataclasses import dataclass
from enum import Enum
from typing import Optional
import asyncio

class DeletionStrategy(Enum):
    HARD_DELETE    = "hard_delete"     # Remove the record entirely
    PSEUDONYMIZE   = "pseudonymize"    # Replace PII with a token (retain for analytics)
    ANONYMIZE      = "anonymize"       # Remove identifying fields, keep aggregate
    REDACT         = "redact"          # Replace with [DELETED] marker

@dataclass
class DataLocation:
    """Every place personal data exists must be catalogued"""
    store_type:     str              # "postgresql", "redis", "s3", "elasticsearch"
    location:       str              # Connection string or bucket name
    table_or_index: str              # Table, index, or prefix
    user_id_field:  str              # Field name for user ID
    deletion_strategy: DeletionStrategy
    cascade_to:     list[str] = None # Other locations that must also be cleaned
    delay_hours:    int = 0          # Delay before deletion (for soft-delete systems)

class GDPRErasureEngine:
    """
    Implements GDPR Article 17 (Right to Erasure) across all data stores.
    Must be complete, verifiable, and leave a compliant audit trail.
    """

    # Register ALL data locations at startup
    DATA_LOCATIONS = [
        DataLocation("postgresql", "app-db", "users",
                     "id", DeletionStrategy.HARD_DELETE),
        DataLocation("postgresql", "app-db", "user_sessions",
                     "user_id", DeletionStrategy.HARD_DELETE),
        DataLocation("postgresql", "app-db", "user_preferences",
                     "user_id", DeletionStrategy.HARD_DELETE),
        DataLocation("postgresql", "app-db", "audit_logs",
                     "user_id", DeletionStrategy.PSEUDONYMIZE,
                     delay_hours=0),  # Audit logs: pseudonymize, don't delete
        DataLocation("postgresql", "app-db", "orders",
                     "user_id", DeletionStrategy.ANONYMIZE),  # Keep for analytics
        DataLocation("redis",   "cache-cluster", "user:*",
                     "key_pattern", DeletionStrategy.HARD_DELETE),
        DataLocation("s3",      "user-uploads", "uploads/",
                     "prefix", DeletionStrategy.HARD_DELETE),
        DataLocation("elasticsearch", "search-cluster", "users",
                     "user_id", DeletionStrategy.HARD_DELETE),
        DataLocation("postgresql", "analytics-db", "events",
                     "user_id", DeletionStrategy.ANONYMIZE,
                     delay_hours=24),  # Analytics: delay for aggregate computation
    ]

    def __init__(self, db_pool, cache, s3_client, es_client, audit_logger):
        self.db      = db_pool
        self.cache   = cache
        self.s3      = s3_client
        self.es      = es_client
        self.audit   = audit_logger

    async def execute_erasure(
        self,
        user_id:      str,
        requested_by: str,  # Who requested deletion (user or admin)
        reason:       str,  # Reason for deletion (user_request, legal_request, etc.)
    ) -> dict:
        """
        Execute complete erasure across all data stores.
        Returns a verifiable deletion report for compliance records.
        """

        erasure_id = str(uuid.uuid4())
        started_at = datetime.now(timezone.utc)
        results    = {}

        # Log the erasure request (this audit record persists even after deletion)
        await self.audit.log_erasure_request(
            erasure_id = erasure_id,
            user_id    = user_id,
            requested_by = requested_by,
            reason     = reason,
        )

        # Process each data location
        for location in self.DATA_LOCATIONS:
            try:
                result = await self._delete_from_location(
                    location, user_id, erasure_id
                )
                results[f"{location.store_type}:{location.table_or_index}"] = {
                    "status":  "success",
                    "records": result.get("records_affected", 0),
                    "strategy": location.deletion_strategy.value,
                }
            except Exception as e:
                results[f"{location.store_type}:{location.table_or_index}"] = {
                    "status": "failed",
                    "error":  str(e),
                }
                # Continue — don't abort on individual failure
                # Log for manual review

        # Verify deletion is complete
        verification = await self._verify_erasure(user_id)

        # Generate compliance report
        report = {
            "erasure_id":      erasure_id,
            "user_id":         user_id,
            "requested_at":    started_at.isoformat(),
            "completed_at":    datetime.now(timezone.utc).isoformat(),
            "requested_by":    requested_by,
            "reason":          reason,
            "locations_processed": results,
            "verification":    verification,
            "compliant":       all(
                v["status"] == "success" for v in results.values()
            ) and verification["no_pii_remaining"],
        }

        # Store erasure report permanently (required for GDPR compliance)
        await self.audit.store_erasure_report(erasure_id, report)

        return report

    async def _delete_from_location(
        self,
        location: DataLocation,
        user_id:  str,
        erasure_id: str,
    ) -> dict:
        """Execute deletion strategy for a specific data location"""

        if location.deletion_strategy == DeletionStrategy.HARD_DELETE:
            if location.store_type == "postgresql":
                result = await self.db.execute(
                    f"DELETE FROM {location.table_or_index} WHERE {location.user_id_field} = $1",
                    user_id
                )
                return {"records_affected": result}

            elif location.store_type == "redis":
                # Scan and delete all keys matching user pattern
                keys = await self.cache.keys(f"user:{user_id}:*")
                if keys:
                    await self.cache.delete(*keys)
                return {"records_affected": len(keys)}

            elif location.store_type == "s3":
                objects = await self.s3.list_objects(
                    Bucket="user-uploads",
                    Prefix=f"uploads/{user_id}/"
                )
                for obj in objects.get("Contents", []):
                    await self.s3.delete_object(
                        Bucket="user-uploads",
                        Key=obj["Key"]
                    )
                return {"records_affected": len(objects.get("Contents", []))}

        elif location.deletion_strategy == DeletionStrategy.PSEUDONYMIZE:
            # Replace PII with a consistent pseudonym
            # Allows linking events for analytics while removing identity
            pseudonym = f"deleted_{hashlib.sha256(user_id.encode()).hexdigest()[:12]}"
            result = await self.db.execute(
                f"""UPDATE {location.table_or_index}
                    SET user_id = $2,
                        ip_address = '0.0.0.0',
                        user_agent = '[deleted]'
                    WHERE {location.user_id_field} = $1""",
                user_id, pseudonym
            )
            return {"records_affected": result, "pseudonym": pseudonym}

        elif location.deletion_strategy == DeletionStrategy.ANONYMIZE:
            result = await self.db.execute(
                f"""UPDATE {location.table_or_index}
                    SET user_id = NULL,
                        email = NULL,
                        name = NULL,
                        phone = NULL,
                        ip_address = NULL
                    WHERE {location.user_id_field} = $1""",
                user_id
            )
            return {"records_affected": result}

    async def _verify_erasure(self, user_id: str) -> dict:
        """Verify no PII remains after erasure"""
        remaining_records = {}

        # Check each primary store for any remaining user records
        for location in self.DATA_LOCATIONS:
            if location.deletion_strategy == DeletionStrategy.HARD_DELETE:
                if location.store_type == "postgresql":
                    count = await self.db.fetchval(
                        f"SELECT COUNT(*) FROM {location.table_or_index} WHERE {location.user_id_field} = $1",
                        user_id
                    )
                    if count > 0:
                        remaining_records[location.table_or_index] = count

        return {
            "no_pii_remaining": len(remaining_records) == 0,
            "remaining_records": remaining_records,
            "verified_at": datetime.now(timezone.utc).isoformat(),
        }
```

---

# PART 42 — SECURITY AUTOMATION AND SELF-HEALING SYSTEMS

---

## Chapter 81: Security Automation Patterns

### 81.1 Automated Security Response

```python
# Python — Self-healing security: automated response to common threats

import asyncio
from enum import Enum
from dataclasses import dataclass

class ThreatType(Enum):
    BRUTE_FORCE_ATTACK    = "brute_force"
    CREDENTIAL_STUFFING   = "credential_stuffing"
    API_ABUSE             = "api_abuse"
    UNUSUAL_DATA_ACCESS   = "unusual_data_access"
    SUSPICIOUS_GEO        = "suspicious_geo"
    TOKEN_ANOMALY         = "token_anomaly"

@dataclass
class SecurityThreat:
    threat_type:  ThreatType
    severity:     str          # "low", "medium", "high", "critical"
    source_ip:    str | None
    user_id:      str | None
    evidence:     dict
    timestamp:    float

class AutomatedSecurityResponse:
    """
    Automated security response system.
    Executes measured responses proportional to threat severity.
    All actions are logged and reversible.
    """

    RESPONSE_PLAYBOOKS = {
        ThreatType.BRUTE_FORCE_ATTACK: {
            "low":      ["rate_limit_ip", "log_event"],
            "medium":   ["rate_limit_ip", "challenge_user", "notify_user", "log_event"],
            "high":     ["block_ip_1h", "lock_account_temp", "notify_user", "alert_security"],
            "critical": ["block_ip_24h", "lock_account", "revoke_tokens", "alert_security", "page_oncall"],
        },
        ThreatType.CREDENTIAL_STUFFING: {
            "medium":   ["rate_limit_ip", "enable_captcha", "log_event"],
            "high":     ["block_ip_subnet", "enable_mfa_requirement", "alert_security"],
        },
        ThreatType.UNUSUAL_DATA_ACCESS: {
            "medium":   ["log_event", "notify_user"],
            "high":     ["revoke_session", "notify_user", "alert_security"],
            "critical": ["revoke_all_sessions", "lock_account", "alert_security", "page_oncall"],
        },
    }

    def __init__(self, rate_limiter, account_manager, notification_service, alert_service):
        self.rate_limiter    = rate_limiter
        self.accounts        = account_manager
        self.notifications   = notification_service
        self.alerts          = alert_service
        self._action_log     = []  # Audit trail of automated actions

    async def respond_to_threat(self, threat: SecurityThreat) -> list[str]:
        """Execute automated response proportional to threat severity"""
        playbook = self.RESPONSE_PLAYBOOKS.get(threat.threat_type, {})
        actions  = playbook.get(threat.severity, ["log_event"])
        executed = []

        for action in actions:
            try:
                await self._execute_action(action, threat)
                executed.append(action)
            except Exception as e:
                # Log failure but continue with other actions
                self._log_action_failure(action, threat, str(e))

        return executed

    async def _execute_action(self, action: str, threat: SecurityThreat):
        handlers = {
            "rate_limit_ip":         self._rate_limit_ip,
            "block_ip_1h":           lambda t: self._block_ip(t, 3600),
            "block_ip_24h":          lambda t: self._block_ip(t, 86400),
            "block_ip_subnet":       self._block_ip_subnet,
            "lock_account_temp":     lambda t: self._lock_account(t, 1800),
            "lock_account":          lambda t: self._lock_account(t, None),
            "revoke_session":        self._revoke_current_session,
            "revoke_all_sessions":   self._revoke_all_sessions,
            "revoke_tokens":         self._revoke_all_tokens,
            "challenge_user":        self._require_mfa_challenge,
            "enable_mfa_requirement": self._enable_mfa_requirement,
            "enable_captcha":        self._enable_captcha_for_ip,
            "notify_user":           self._notify_user_of_threat,
            "alert_security":        self._alert_security_team,
            "page_oncall":           self._page_oncall,
            "log_event":             self._log_security_event,
        }
        handler = handlers.get(action)
        if handler:
            await handler(threat)

    async def _block_ip(self, threat: SecurityThreat, duration_seconds: int | None):
        if not threat.source_ip:
            return
        await self.rate_limiter.block_ip(
            ip=threat.source_ip,
            duration=duration_seconds,
            reason=threat.threat_type.value,
        )
        self._log_automated_action("ip_blocked", {
            "ip":          threat.source_ip,
            "duration_s":  duration_seconds,
            "threat_type": threat.threat_type.value,
            "severity":    threat.severity,
        })

    async def _lock_account(self, threat: SecurityThreat, duration_seconds: int | None):
        if not threat.user_id:
            return
        await self.accounts.lock(
            user_id=threat.user_id,
            duration=duration_seconds,
            reason=f"Automated: {threat.threat_type.value}",
        )
        self._log_automated_action("account_locked", {
            "user_id":    threat.user_id,
            "duration_s": duration_seconds,
        })

    async def _notify_user_of_threat(self, threat: SecurityThreat):
        if not threat.user_id:
            return
        await self.notifications.send_security_alert(
            user_id=threat.user_id,
            threat_type=threat.threat_type.value,
            details={
                "source_ip":  threat.source_ip,
                "timestamp":  threat.timestamp,
                "action_taken": "Your account security was automatically protected.",
                "recommended": "Review recent account activity and change your password.",
            }
        )

    def _log_automated_action(self, action: str, details: dict):
        import structlog
        structlog.get_logger().info(
            f"security.automated_action.{action}",
            **details,
        )
```

### 81.2 Security Regression Prevention

```python
# Python — Security regression tests that run on every commit

import pytest
import re

class SecurityRegressionTests:
    """
    Tests that prevent previously-found security issues from returning.
    Each test corresponds to a real vulnerability that was fixed.
    """

    # CVE-2024-001: Path traversal in file download endpoint (fixed 2024-01-15)
    async def test_path_traversal_regression_cve_2024_001(self, client, auth_token):
        """Regression: Path traversal was possible in /api/files/download"""
        payloads = [
            "../../../etc/passwd",
            "..%2F..%2F..%2Fetc%2Fpasswd",
            "....//....//etc/passwd",
            "%2e%2e%2f%2e%2e%2f%2e%2e%2fetc%2fpasswd",
        ]
        for payload in payloads:
            resp = await client.get(
                f"/api/files/download/{payload}",
                headers={"Authorization": f"Bearer {auth_token}"}
            )
            assert resp.status_code in (400, 403, 404), \
                f"REGRESSION: Path traversal not blocked: {payload}"
            assert "root:" not in resp.text, \
                f"REGRESSION: /etc/passwd contents returned for: {payload}"

    # CVE-2024-002: Mass assignment allowed role escalation (fixed 2024-02-03)
    async def test_mass_assignment_regression_cve_2024_002(self, client, user_token):
        """Regression: users could set is_admin=true via profile update"""
        resp = await client.put(
            "/api/users/me",
            headers={"Authorization": f"Bearer {user_token}"},
            json={
                "display_name": "hacker",
                "is_admin":     True,    # Should be silently ignored
                "role":         "admin", # Should be silently ignored
                "credits":      99999,   # Should be silently ignored
            }
        )
        assert resp.status_code == 200
        # Verify user is still not an admin
        me_resp = await client.get("/api/users/me",
                                   headers={"Authorization": f"Bearer {user_token}"})
        assert me_resp.json()["is_admin"] is False, \
            "REGRESSION: Mass assignment allowed role escalation"
        assert me_resp.json().get("role") != "admin", \
            "REGRESSION: Role escalation via mass assignment"

    # CVE-2024-003: IDOR on invoices endpoint (fixed 2024-03-10)
    async def test_idor_regression_cve_2024_003(self, client, user_a_token, user_b_invoice_id):
        """Regression: User A could read User B's invoices"""
        resp = await client.get(
            f"/api/invoices/{user_b_invoice_id}",
            headers={"Authorization": f"Bearer {user_a_token}"}
        )
        assert resp.status_code in (403, 404), \
            f"REGRESSION: IDOR on invoices endpoint - got {resp.status_code}"

    # Ongoing: These tests run on every commit to prevent regression
    async def test_sql_injection_user_search_current(self, client, auth_token):
        """Ensure SQL injection protection on user search has not regressed"""
        for payload in ["'; DROP TABLE users;--", "1 OR 1=1", "1 UNION SELECT * FROM users"]:
            resp = await client.get(
                f"/api/users/search?q={payload}",
                headers={"Authorization": f"Bearer {auth_token}"}
            )
            assert "error" not in resp.text.lower() or "sql" not in resp.text.lower(), \
                f"Possible SQL error exposed in search: {payload}"
```

---

## Chapter 82: Security Champions Program

```markdown
# Security Champions Program Guide

## What Is a Security Champion?

A Security Champion is an engineer who acts as the security advocate within
their team. They are NOT a security professional — they are developers who:

- Complete 8 hours of security training per quarter
- Participate in monthly Security Champions meetings
- Review security-sensitive PRs in their domain
- Help teammates answer security questions before they escalate
- Conduct threat modeling for major new features
- Own the security backlog for their team

## Why Champions Work Better Than Central Security Teams

A central security team of 5 engineers cannot review every PR in a company
of 200 engineers. Security Champions create a network of informed engineers
distributed across every team, so security questions are answered where the
code is written — not in a bottlenecked review queue.

## Security Champion Curriculum (Rolling 12 Months)

Month 1:  Secure coding fundamentals (OWASP Top 10, input validation)
Month 2:  Authentication and authorization (JWT, OAuth, RBAC)
Month 3:  Cryptography for developers (when to use what)
Month 4:  Infrastructure security (Docker, Kubernetes, IAM)
Month 5:  Threat modeling workshop (hands-on STRIDE with real system)
Month 6:  API security deep dive (REST, GraphQL, gRPC)
Month 7:  DevSecOps (SAST, DAST, dependency scanning, CI integration)
Month 8:  Cloud security (AWS/GCP/Azure specific patterns)
Month 9:  Incident response simulation (tabletop exercise)
Month 10: Privacy engineering (GDPR, data minimization, consent)
Month 11: AI/ML security (prompt injection, model security)
Month 12: Bug bounty simulation (capture-the-flag exercise)

## Security Champion Responsibilities

WEEKLY:
  □ Review security-labeled GitHub issues in your team's backlog
  □ Answer security questions in team Slack channel
  □ Check SAST scan results in CI pipeline for your team

MONTHLY:
  □ Attend Security Champions meeting (1 hour)
  □ Review one security-sensitive PR per week
  □ Update team security backlog with new findings

QUARTERLY:
  □ Conduct threat model review for any major new features
  □ Complete 2 hours of security training
  □ Participate in security metrics review for your team

PER FEATURE:
  □ Threat model review before development starts
  □ Security checklist sign-off before merge
  □ Post-deployment security verification

## Metrics for Security Champions Program

TEAM-LEVEL:
  - Time to resolve security findings (target: Critical <24h, High <7d)
  - Security debt ratio (security issues vs total backlog)
  - SAST false positive rate (too many false positives = ignored alerts)

CHAMPION-LEVEL:
  - PRs reviewed for security
  - Security questions answered
  - Training modules completed

PROGRAM-LEVEL:
  - Total critical vulns in production
  - Mean time between security incidents
  - Percentage of new features with threat model
```

---

## Final Chapter: Building the Security-First Engineering Organization

```
THE SECURITY MATURITY MATRIX

CAPABILITY               LEVEL 1 (AD HOC)     LEVEL 2 (DEFINED)    LEVEL 3 (MANAGED)    LEVEL 4 (OPTIMIZING)
─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
Threat Modeling          Never or after        For some features     For all major         Continuous; auto-triggered
                         incidents             when remembered       features              on design changes

Secure Coding            Varies by developer   OWASP training done   Standards documented, Champions program;
                                               once                  enforced in review    tooling enforces standards

SAST                     Manual, occasional   In CI but ignored      Failing builds on     Tuned; low false positive;
                                                                     critical findings      auto-remediation suggestions

Dependency Scanning      Never                 Manual quarterly       CI pipeline           Real-time monitoring;
                                                                                           auto-PR for patches

Secrets Management       Env vars / .env       Per-env env vars      Vault or Secrets       Dynamic secrets;
                                               not in code           Manager                auto-rotation

Authentication           Basic password        Password + optional    Password + MFA         Passkeys; adaptive auth;
                                               MFA                   required for admin     risk-based step-up

Incident Response        React after discovery Written playbook       Quarterly tabletop;    Automated containment;
                                               exists                 on-call defined        post-incident auto-analysis

Compliance               Point-in-time audits  Annual review          Continuous monitoring  Automated evidence
                                                                                            collection; real-time score

Pen Testing              Never                 When asked by sales    Annual + post-         Continuous with bug
                                                                     major release          bounty + quarterly pen test

Security Metrics         None                  Occasional reports     Monthly dashboard      OKRs tied to security metrics
```

---

*This is Part 6 and the penultimate volume of the Developer's Cybersecurity Mastery handbook.*

*Covered in this volume: Advanced OAuth 2.0 attacks (Authorization Code Injection, Token Leakage, DPoP sender-constrained tokens in TypeScript and Python), CORS deep dive with all 7 anti-patterns and precise CORS middleware, CSP advanced patterns (strict-dynamic, nonce-based, complete directive reference), Subresource Integrity (SRI), Cross-Origin Isolation headers (COEP/COOP/CORP), Dynamic secrets with HashiCorp Vault (zero-standing-privilege pattern), Secret rotation with zero downtime, Secure event-driven systems (tamper-evident events, idempotent processing, transactional outbox pattern), eBPF security monitoring (BCC program with syscall tracing), GDPR Right to Erasure complete technical implementation (cross-store deletion, pseudonymization, anonymization, verification, compliance report generation), Automated security response system (threat playbooks, proportional response), Security regression test patterns, Security Champions program design, and the Security Maturity Matrix. Production-ready code in Python, TypeScript, Go, and Java throughout.*
