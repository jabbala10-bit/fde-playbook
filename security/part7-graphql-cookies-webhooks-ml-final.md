# Developer's Cybersecurity Mastery: The Complete Handbook
## Volume 49–58 | GraphQL · Cookies · Webhooks · Background Jobs · IMDSv2 · Circuit Breakers · Log Masking · ML Security · Final Reference

---

# PART 43 — GRAPHQL ADVANCED SECURITY

---

## Chapter 83: GraphQL Security — Beyond Introspection Disable

### 83.1 Persisted Queries — The Production Security Pattern

```typescript
// TypeScript — Persisted queries: pre-register all allowed queries
// Eliminates arbitrary query execution — only whitelisted queries run in production

import crypto from 'crypto';
import { ApolloServer } from '@apollo/server';

// Build-time: generate hash for each allowed query
function generateQueryHash(query: string): string {
    return crypto.createHash('sha256').update(query.trim()).digest('hex');
}

// Registry of allowed queries (built at compile time, not runtime)
const PERSISTED_QUERY_REGISTRY = new Map<string, string>([
    // hash → query
    [
        generateQueryHash('query GetUser($id: ID!) { user(id: $id) { id name email } }'),
        'query GetUser($id: ID!) { user(id: $id) { id name email } }',
    ],
    [
        generateQueryHash('query ListOrders { orders { id total status } }'),
        'query ListOrders { orders { id total status } }',
    ],
    // All other queries are REJECTED — no arbitrary execution
]);

class PersistedQueryPlugin {
    async requestDidStart() {
        return {
            async didResolveOperation({ request, document, operationName }) {
                const hash = request.extensions?.persistedQuery?.sha256Hash;

                if (!hash) {
                    // No hash provided: only allow in development
                    if (process.env.NODE_ENV === 'production') {
                        throw new Error('Persisted queries required in production');
                    }
                    return;
                }

                const allowedQuery = PERSISTED_QUERY_REGISTRY.get(hash);
                if (!allowedQuery) {
                    throw new Error(`Query not in registry: ${hash}`);
                }

                // Verify the query matches the hash (prevents hash collision attacks)
                const actualQuery = request.query;
                if (actualQuery) {
                    const actualHash = generateQueryHash(actualQuery);
                    if (actualHash !== hash) {
                        throw new Error('Query hash mismatch');
                    }
                }
            }
        };
    }
}

const server = new ApolloServer({
    typeDefs,
    resolvers,
    plugins: [new PersistedQueryPlugin()],
    introspection: process.env.NODE_ENV !== 'production',
});
```

### 83.2 Field-Level Authorization with DataLoader

```typescript
// TypeScript — Field-level authorization with efficient DataLoader batching

import DataLoader from 'dataloader';
import { GraphQLResolveInfo } from 'graphql';

interface AuthorizationContext {
    userId:    string;
    tenantId:  string;
    roles:     string[];
    scopes:    string[];
}

// Field-level permission decorator
function requirePermission(permission: string) {
    return function(
        _: unknown,
        args: unknown,
        context: { auth: AuthorizationContext },
        info: GraphQLResolveInfo
    ) {
        if (!context.auth.scopes.includes(permission)) {
            throw new Error(`Forbidden: requires scope '${permission}'`);
        }
    };
}

// DataLoader for batching authorization checks — prevents N+1 auth queries
function createAuthorizationLoader(context: AuthorizationContext) {
    return new DataLoader<string, boolean>(async (resourceIds) => {
        // Batch all permission checks into a single database query
        const permissions = await db.checkBatchPermissions(
            context.userId,
            context.tenantId,
            Array.from(resourceIds),
        );
        return resourceIds.map(id => permissions.get(id) ?? false);
    });
}

// Resolver with field-level authorization
const resolvers = {
    Query: {
        // Authorization at query level
        users: async (_: unknown, args: unknown, ctx: any) => {
            if (!ctx.auth.roles.includes('admin')) {
                throw new ForbiddenError('Admin role required');
            }
            return userService.list();
        },
    },

    User: {
        // Public fields — no authorization needed
        id:          (user: User) => user.id,
        displayName: (user: User) => user.displayName,

        // Sensitive fields — field-level authorization
        email: async (user: User, _: unknown, ctx: any) => {
            // Only the user themselves or admins can see email
            if (user.id !== ctx.auth.userId && !ctx.auth.roles.includes('admin')) {
                return null;  // Return null, not an error (don't reveal field existence)
            }
            return user.email;
        },

        ssn: async (user: User, _: unknown, ctx: any) => {
            // SSN requires specific scope AND admin role
            if (!ctx.auth.scopes.includes('pii:ssn:read') || !ctx.auth.roles.includes('admin')) {
                return null;
            }
            // Log access to highly sensitive field
            await auditLog.log('ssn_accessed', {
                accessor: ctx.auth.userId,
                subject:  user.id,
            });
            return user.ssnEncrypted ? decrypt(user.ssnEncrypted) : null;
        },

        // Nested resource with batched authorization
        orders: async (user: User, _: unknown, ctx: any) => {
            // Batch permission check via DataLoader
            const canViewOrders = await ctx.authLoader.load(`user:${user.id}:orders:read`);
            if (!canViewOrders) return [];
            return orderService.findByUserId(user.id);
        },
    },
};
```

### 83.3 Query Allow-Listing for Maximum Security

```python
# Python — GraphQL query allow-listing with hash validation
import hashlib
import json
from strawberry.types import Info

# Build-time generated registry (CI/CD generates this from source)
ALLOWED_QUERIES: dict[str, dict] = {
    "a1b2c3d4": {
        "name":     "GetUserProfile",
        "hash":     "a1b2c3d4e5f6...",
        "max_cost": 100,
    },
    "e5f6g7h8": {
        "name":     "ListOrders",
        "hash":     "e5f6g7h8i9j0...",
        "max_cost": 500,
    },
}

class QueryAllowListExtension:
    """Strawberry extension that enforces query allow-listing in production"""

    def resolve(self, _next, root, info: Info, **kwargs):
        request = info.context["request"]
        
        # Extract query hash from Apollo's persisted query extension
        extensions = request.json().get("extensions", {})
        pq = extensions.get("persistedQuery", {})
        query_hash = pq.get("sha256Hash")

        if not query_hash and os.getenv("ENV") == "production":
            raise Exception("Query hashing required in production")

        if query_hash:
            if query_hash not in ALLOWED_QUERIES:
                raise Exception(f"Query not registered: {query_hash[:8]}...")

        return _next(root, info, **kwargs)
```

---

# PART 44 — COOKIE SECURITY DEEP DIVE

---

## Chapter 84: Cookie Security — All Attributes Explained

### 84.1 Complete Cookie Security Reference

```python
# Python — Production cookie security configuration

from fastapi import Response
from datetime import datetime, timedelta, timezone

def set_secure_session_cookie(
    response: Response,
    session_id: str,
    environment: str = "production",
) -> None:
    """
    Set a session cookie with all security attributes correctly configured.
    """
    response.set_cookie(
        key="__Host-SessionId",
        # __Host- prefix requirements:
        # 1. Must have Secure attribute
        # 2. Must NOT have Domain attribute
        # 3. Must have Path=/
        # 4. Cannot be set from JavaScript (unlike __Secure- prefix)
        # Together: prevents cookie tossing attacks

        value=session_id,

        # SECURITY: Never allow JavaScript to read session cookie
        httponly=True,

        # SECURITY: Only transmit over HTTPS
        secure=True,

        # SECURITY: Prevent CSRF (strict: not sent for any cross-site requests)
        # 'lax' is acceptable if you need cookies on top-level navigation
        samesite="strict",

        # PATH: Must be "/" for __Host- prefix
        path="/",

        # DOMAIN: Must be absent for __Host- prefix
        # (absence = only exact host; Domain="example.com" = all subdomains)
        # domain=None,  # Don't set — __Host- requires this

        # LIFETIME: Use session cookies for auth (no max_age or expires)
        # The session timeout is enforced server-side, not by cookie expiry
        # max_age=None,  # Session cookie — expires when browser closes
        # OR for persistent login:
        max_age=86400 * 30,  # 30 days

        # PARTITIONED: Chrome's CHIPS (Cookies Having Independent Partitioned State)
        # Allows cookies in third-party context without tracking across sites
        # Relevant for embedded widgets/iframes that need state
        # samesite must be 'none' + secure=True for partitioned to apply
    )

def set_csrf_cookie(response: Response, csrf_token: str) -> None:
    """
    CSRF token must be readable by JavaScript (httponly=False)
    so it can be copied to the X-CSRF-Token header.
    """
    response.set_cookie(
        key="__Secure-CsrfToken",
        value=csrf_token,
        httponly=False,    # JavaScript MUST read this to copy to header
        secure=True,
        samesite="strict", # Prevents cross-origin reads anyway
        path="/",
        max_age=3600,
    )

def clear_session_on_logout(response: Response) -> None:
    """
    Properly clear cookies on logout.
    All attributes must EXACTLY match the original cookie or browser ignores delete.
    """
    response.set_cookie(
        key="__Host-SessionId",
        value="",
        httponly=True,
        secure=True,
        samesite="strict",
        path="/",
        max_age=0,       # Immediately expired
        expires=datetime(1970, 1, 1, tzinfo=timezone.utc),
    )
    # Also: Add Clear-Site-Data header for complete cleanup
    response.headers["Clear-Site-Data"] = '"cookies", "storage"'
```

### 84.2 Cookie Tossing Attack Prevention

```
COOKIE TOSSING ATTACK:
  If your app is at https://app.example.com and an attacker controls
  https://evil.example.com (a subdomain), they can set a cookie with
  domain=.example.com that overrides your legitimate session cookie.

  Attack steps:
  1. Attacker has XSS on evil.example.com
  2. Sets: document.cookie = "SessionId=ATTACKER_VALUE; Domain=.example.com; Path=/"
  3. Victim visits app.example.com — browser sends ATTACKER_VALUE as SessionId
  4. If app trusts this cookie, attacker has session fixation

MITIGATIONS:
  __Host- prefix: Browser REJECTS any cookie with __Host- prefix if:
  - It was set with a Domain attribute (prevents cross-subdomain toss)
  - It was NOT set from the exact host (prevents subdomain setting it)
  - It doesn't have Secure + Path=/

  This makes __Host- cookies immune to cookie tossing.
```

---

# PART 45 — WEBHOOK SECURITY

---

## Chapter 85: Webhook Signature Validation — All Major Providers

```python
# Python — Universal webhook signature validation

import hmac
import hashlib
import time
from typing import Optional
from fastapi import Request, HTTPException

class WebhookValidator:
    """Validate webhook signatures from major providers"""

    # ── Stripe ────────────────────────────────────────────────────────────────
    @staticmethod
    async def validate_stripe(
        request: Request,
        secret: str,
        tolerance_seconds: int = 300,
    ) -> dict:
        """
        Stripe uses HMAC-SHA256 with a timestamp to prevent replay attacks.
        Signature format: v1=HMAC(timestamp.payload)
        """
        sig_header = request.headers.get("stripe-signature")
        if not sig_header:
            raise HTTPException(400, "Missing Stripe-Signature header")

        # Parse the signature header: t=timestamp,v1=signature
        elements = dict(e.split("=", 1) for e in sig_header.split(","))
        timestamp = elements.get("t")
        signatures = [v for k, v in elements.items() if k.startswith("v")]

        if not timestamp or not signatures:
            raise HTTPException(400, "Invalid Stripe-Signature format")

        # Replay attack prevention: reject old events
        event_time = int(timestamp)
        if abs(time.time() - event_time) > tolerance_seconds:
            raise HTTPException(400, "Webhook timestamp too old")

        body = await request.body()
        signed_payload = f"{timestamp}.{body.decode()}"
        expected = hmac.new(
            secret.encode(),
            signed_payload.encode(),
            hashlib.sha256,
        ).hexdigest()

        # Check against all provided signatures (v1 can have multiple)
        if not any(hmac.compare_digest(expected, sig) for sig in signatures):
            raise HTTPException(400, "Invalid Stripe signature")

        import json
        return json.loads(body)

    # ── GitHub ────────────────────────────────────────────────────────────────
    @staticmethod
    async def validate_github(request: Request, secret: str) -> dict:
        """
        GitHub uses HMAC-SHA256.
        Header: X-Hub-Signature-256: sha256=SIGNATURE
        """
        sig_header = request.headers.get("x-hub-signature-256", "")
        if not sig_header.startswith("sha256="):
            raise HTTPException(400, "Missing or invalid X-Hub-Signature-256")

        provided_sig = sig_header[7:]  # Remove "sha256=" prefix
        body = await request.body()

        expected_sig = hmac.new(
            secret.encode(),
            body,
            hashlib.sha256,
        ).hexdigest()

        if not hmac.compare_digest(provided_sig, expected_sig):
            raise HTTPException(400, "Invalid GitHub signature")

        # Additional: validate event type is expected
        event_type = request.headers.get("x-github-event")
        if event_type not in {"push", "pull_request", "release"}:
            raise HTTPException(400, f"Unexpected event type: {event_type}")

        import json
        return json.loads(body)

    # ── Twilio ────────────────────────────────────────────────────────────────
    @staticmethod
    async def validate_twilio(
        request: Request,
        auth_token: str,
        url: str,
    ) -> dict:
        """
        Twilio uses HMAC-SHA1 over URL + sorted parameters.
        """
        from urllib.parse import urlencode, parse_qs

        provided_sig = request.headers.get("x-twilio-signature", "")
        body = await request.body()
        params = parse_qs(body.decode())

        # Sort params and append to URL
        sorted_params = urlencode(sorted(
            {k: v[0] for k, v in params.items()}.items()
        ))
        signed_payload = url + sorted_params

        expected_sig = hmac.new(
            auth_token.encode(),
            signed_payload.encode(),
            hashlib.sha1,
        ).digest()

        import base64
        expected_b64 = base64.b64encode(expected_sig).decode()

        if not hmac.compare_digest(provided_sig, expected_b64):
            raise HTTPException(400, "Invalid Twilio signature")

        return {k: v[0] for k, v in params.items()}

    # ── Shopify ───────────────────────────────────────────────────────────────
    @staticmethod
    async def validate_shopify(request: Request, secret: str) -> dict:
        """
        Shopify uses HMAC-SHA256, Base64-encoded.
        Header: X-Shopify-Hmac-Sha256
        """
        import base64

        provided_sig = request.headers.get("x-shopify-hmac-sha256", "")
        body = await request.body()

        expected_sig = base64.b64encode(
            hmac.new(secret.encode(), body, hashlib.sha256).digest()
        ).decode()

        if not hmac.compare_digest(provided_sig, expected_sig):
            raise HTTPException(400, "Invalid Shopify signature")

        import json
        return json.loads(body)

    # ── Generic HMAC webhook (for internal services) ──────────────────────────
    @staticmethod
    async def validate_generic(
        request: Request,
        secret: bytes,
        header_name: str = "X-Webhook-Signature",
        max_age_seconds: int = 300,
    ) -> dict:
        """Generic webhook validation with timestamp-based replay prevention"""
        sig_header     = request.headers.get(header_name, "")
        timestamp_header = request.headers.get("X-Webhook-Timestamp", "")

        if not sig_header or not timestamp_header:
            raise HTTPException(400, "Missing webhook security headers")

        # Replay attack prevention
        try:
            event_timestamp = float(timestamp_header)
        except ValueError:
            raise HTTPException(400, "Invalid timestamp")

        if abs(time.time() - event_timestamp) > max_age_seconds:
            raise HTTPException(400, "Webhook too old — possible replay attack")

        body = await request.body()
        signed_content = f"{timestamp_header}.{body.decode()}"
        expected = hmac.new(secret, signed_content.encode(), hashlib.sha256).hexdigest()

        if not hmac.compare_digest(sig_header, expected):
            raise HTTPException(400, "Invalid webhook signature")

        import json
        return json.loads(body)
```

---

# PART 46 — SECURITY FOR BACKGROUND JOBS

---

## Chapter 86: Securing Async Jobs and Task Queues

```python
# Python — Celery secure configuration with result signing

from celery import Celery
from celery.utils.log import get_task_logger
import hmac
import hashlib
import json
import os

logger = get_task_logger(__name__)

# ── Secure Celery configuration ───────────────────────────────────────────────
app = Celery("myapp")

app.config_from_object({
    # Transport: Use Redis over TLS
    "broker_url": os.environ["CELERY_BROKER_URL"],  # rediss://... (TLS)
    "result_backend": os.environ["CELERY_RESULT_URL"],

    # Security: Sign task messages
    "task_serializer":   "json",
    "result_serializer": "json",
    "accept_content":    ["json"],  # NEVER "pickle" — RCE risk

    # Security: Disable untrusted deserializers
    "task_reject_on_worker_lost": True,
    "task_acks_late":             True,   # Ack after completion, not on receive

    # Timeouts: prevent runaway tasks
    "task_soft_time_limit":  300,   # Soft limit: task raises SoftTimeLimitExceeded
    "task_time_limit":       360,   # Hard limit: worker kills task

    # Rate limits: prevent abuse
    "task_default_rate_limit": "100/m",

    # Security: Use Celery's built-in message signing
    # Requires: pip install celery[auth]
    "task_always_eager": False,
    "security_key":      os.environ["CELERY_SECURITY_KEY"],
    "security_certificate": "/certs/celery-cert.pem",
    "security_cert_store": "/certs/trusted-certs/",
})

# ── Secure task design patterns ───────────────────────────────────────────────

TASK_SIGNING_KEY = os.environ["TASK_SIGNING_KEY"].encode()

def sign_task_payload(payload: dict) -> str:
    """Sign task payload to prevent tampering in message queue"""
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hmac.new(TASK_SIGNING_KEY, canonical.encode(), hashlib.sha256).hexdigest()

def verify_task_payload(payload: dict, signature: str) -> bool:
    canonical  = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    expected   = hmac.new(TASK_SIGNING_KEY, canonical.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(signature, expected)

@app.task(
    name="send_email",
    max_retries=3,
    default_retry_delay=60,
    # Security: bind=True gives access to task instance (for retry, ID)
    bind=True,
    # Security: never store sensitive data in task result
    ignore_result=False,
    # Rate limiting per task type
    rate_limit="50/m",
)
def send_email_task(self, task_data: dict):
    """
    Secure background task design principles:
    1. Validate all inputs — task queue is an attack surface
    2. No sensitive data in task payload (use references, not values)
    3. Idempotent — safe to retry
    4. Limited permissions — task runs as least-privilege service account
    5. Audit log all significant actions
    """
    # Step 1: Verify task payload signature
    signature = task_data.pop("_sig", None)
    if not signature or not verify_task_payload(task_data, signature):
        logger.error("task_signature_invalid", task_id=self.request.id)
        # Don't retry — signature invalid = tampering
        raise ValueError("Task payload signature invalid")

    # Step 2: Validate task data (don't trust queue contents)
    from pydantic import BaseModel, validator

    class EmailTaskSchema(BaseModel):
        user_id:  str
        template: str
        locale:   str = "en"

        @validator("template")
        def allowed_template(cls, v):
            ALLOWED = {"welcome", "password_reset", "invoice", "alert"}
            if v not in ALLOWED:
                raise ValueError(f"Template not allowed: {v}")
            return v

    try:
        validated = EmailTaskSchema(**task_data)
    except Exception as e:
        logger.error("task_validation_failed", error=str(e), task_id=self.request.id)
        return  # Don't retry validation failures

    # Step 3: Load sensitive data from secure store, not from task payload
    # WRONG: task_data = {"user_email": "actual@email.com", "api_key": "secret"}
    # RIGHT: task_data = {"user_id": "uuid"} — look up email from DB
    from app.services import UserService
    user = UserService.get_by_id(validated.user_id)
    if not user:
        logger.warning("task_user_not_found", user_id=validated.user_id)
        return

    # Step 4: Execute with audit logging
    logger.info("task_sending_email",
        user_id=validated.user_id,
        template=validated.template,
        task_id=self.request.id,
    )

    try:
        email_service.send(
            to=user.email,
            template=validated.template,
            locale=validated.locale,
        )
    except Exception as e:
        logger.exception("task_email_failed", task_id=self.request.id)
        # Retry with exponential backoff
        raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))

# Dispatch task with signed payload
def dispatch_email_task(user_id: str, template: str):
    payload = {"user_id": user_id, "template": template}
    payload["_sig"] = sign_task_payload(payload)
    send_email_task.delay(payload)
```

---

# PART 47 — SENSITIVE DATA IN LOGS

---

## Chapter 87: Log Masking and Sensitive Data Prevention

```python
# Python — Comprehensive log masking for production systems

import re
import json
import structlog
from typing import Any

class SensitiveDataMasker:
    """
    Automatically masks sensitive data in log records.
    Applied as a structlog processor — runs on every log event.
    """

    # Patterns to detect and mask
    PATTERNS = [
        # Credit card numbers (various formats)
        (re.compile(r'\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13}|6(?:011|5[0-9]{2})[0-9]{12})\b'), "CARD_****"),

        # SSN
        (re.compile(r'\b\d{3}-\d{2}-\d{4}\b'), "SSN_****"),
        (re.compile(r'\b\d{9}\b'), "POSSIBLE_SSN_****"),  # 9-digit number

        # JWT tokens (preserve first 20 chars for debugging, mask rest)
        (re.compile(r'\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b'),
         lambda m: m.group()[:20] + "...[REDACTED]"),

        # Bearer tokens
        (re.compile(r'Bearer\s+[A-Za-z0-9_\-\.]{20,}', re.IGNORECASE),
         "Bearer [REDACTED]"),

        # API keys (various patterns)
        (re.compile(r'(?:api[_-]?key|apikey|api_token)\s*[=:]\s*["\']?([A-Za-z0-9_\-]{16,})["\']?', re.IGNORECASE),
         lambda m: m.group().split('=')[0] + "=[REDACTED]" if '=' in m.group()
                  else m.group().split(':')[0] + ":[REDACTED]"),

        # Email addresses (partial masking: j***@example.com)
        (re.compile(r'\b([a-zA-Z0-9._%+\-])[a-zA-Z0-9._%+\-]*@([a-zA-Z0-9.\-]+\.[a-zA-Z]{2,})\b'),
         lambda m: m.group(1) + "***@" + m.group(2)),

        # Passwords in query strings or JSON
        (re.compile(r'(?:password|passwd|pwd)\s*[=:]\s*["\']?[^\s"\'&,}]{4,}["\']?', re.IGNORECASE),
         "password=[REDACTED]"),

        # AWS credentials
        (re.compile(r'AKIA[0-9A-Z]{16}'), "[AWS_KEY_REDACTED]"),
        (re.compile(r'(?<=secret.access.key["\'\s=:]{1,10})[A-Za-z0-9/+]{40}', re.IGNORECASE),
         "[AWS_SECRET_REDACTED]"),
    ]

    # Field names that should always be masked
    SENSITIVE_FIELD_NAMES = frozenset([
        "password", "passwd", "pwd", "secret", "token", "api_key", "apikey",
        "private_key", "signing_key", "auth_token", "access_token",
        "refresh_token", "credit_card", "card_number", "cvv", "ssn",
        "social_security", "bank_account", "routing_number",
    ])

    def mask_string(self, value: str) -> str:
        """Apply all masking patterns to a string value"""
        result = value
        for pattern, replacement in self.PATTERNS:
            if callable(replacement):
                result = pattern.sub(replacement, result)
            else:
                result = pattern.sub(replacement, result)
        return result

    def mask_value(self, key: str, value: Any) -> Any:
        """Mask a value based on its key name and content"""
        # Check if field name itself indicates sensitivity
        key_lower = key.lower().replace("-", "_").replace(" ", "_")
        if any(sensitive in key_lower for sensitive in self.SENSITIVE_FIELD_NAMES):
            if isinstance(value, str):
                return "[REDACTED]"
            return "[REDACTED]"

        # Apply pattern matching to string values
        if isinstance(value, str):
            return self.mask_string(value)

        # Recurse into dicts and lists
        if isinstance(value, dict):
            return {k: self.mask_value(k, v) for k, v in value.items()}
        if isinstance(value, (list, tuple)):
            return [self.mask_value(key, item) for item in value]

        return value

    def __call__(self, logger, method, event_dict: dict) -> dict:
        """structlog processor interface"""
        for key, value in list(event_dict.items()):
            event_dict[key] = self.mask_value(key, value)
        return event_dict

# HTTP request/response logging with automatic masking
class SecureHTTPLogger:
    masker = SensitiveDataMasker()

    @classmethod
    def log_request(cls, method: str, url: str, headers: dict, body: bytes | None):
        # Always mask Authorization headers
        safe_headers = {
            k: "[REDACTED]" if k.lower() in {"authorization", "cookie", "set-cookie"}
               else v
            for k, v in headers.items()
        }

        # Mask body if it contains sensitive fields
        safe_body = None
        if body:
            try:
                parsed = json.loads(body)
                safe_body = {k: cls.masker.mask_value(k, v) for k, v in parsed.items()}
            except (json.JSONDecodeError, AttributeError):
                safe_body = "[NON-JSON BODY]"

        structlog.get_logger().info(
            "http.request",
            method=method,
            url=cls._mask_url(url),
            headers=safe_headers,
            body=safe_body,
        )

    @classmethod
    def _mask_url(cls, url: str) -> str:
        """Mask sensitive query parameters in URLs"""
        from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

        parsed = urlparse(url)
        params = parse_qs(parsed.query)

        SENSITIVE_PARAMS = {"token", "api_key", "password", "secret", "access_token"}
        masked_params = {
            k: ["[REDACTED]"] if k.lower() in SENSITIVE_PARAMS else v
            for k, v in params.items()
        }

        masked_query = urlencode({k: v[0] for k, v in masked_params.items()})
        return urlunparse(parsed._replace(query=masked_query))

# Configure structlog with masking
def configure_secure_logging():
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            SensitiveDataMasker(),           # Mask sensitive data
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
```

---

# PART 48 — CLOUD SECURITY ADVANCED PATTERNS

---

## Chapter 88: AWS IMDSv2 and EC2 Instance Security

```python
# Python — Enforcing IMDSv2 (Instance Metadata Service version 2)
# IMDSv1 vulnerable to SSRF → AWS credential theft
# IMDSv2 requires a session token → SSRF attack fails

import boto3
import requests

# IMDSv2: The correct way to access EC2 instance metadata
def get_instance_metadata_v2(metadata_path: str) -> str:
    """
    IMDSv2 requires a PUT to get a session token, then GET with the token.
    This defeats SSRF attacks because:
    1. SSRF attacks can only send GET requests (most of the time)
    2. Even if SSRF sends PUT, the redirect from SSRF does GET (no token)
    """
    # Step 1: Get session token (TTL: 6 hours max)
    token_response = requests.put(
        "http://169.254.169.254/latest/api/token",
        headers={"X-aws-ec2-metadata-token-ttl-seconds": "21600"},
        timeout=1,
    )
    token = token_response.text

    # Step 2: Use token to access metadata
    response = requests.get(
        f"http://169.254.169.254/latest/meta-data/{metadata_path}",
        headers={"X-aws-ec2-metadata-token": token},
        timeout=1,
    )
    return response.text

# NEVER use IMDSv1 (no token required):
# requests.get("http://169.254.169.254/latest/meta-data/iam/security-credentials/")
# An SSRF vulnerability = complete AWS credential compromise

# Terraform: Enforce IMDSv2 on all EC2 instances
ec2_imdsv2_terraform = """
resource "aws_instance" "app" {
  ami           = data.aws_ami.app.id
  instance_type = "t3.medium"

  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"  # IMDSv2 REQUIRED — IMDSv1 rejected
    http_put_response_hop_limit = 1            # Prevents SSRF via container escape
    # hop_limit=1: metadata only accessible from EC2 itself (not from containers within)
  }

  # Require all new instances to use IMDSv2 account-wide:
  # aws ec2 modify-instance-metadata-defaults --http-tokens required
}
"""
```

### 88.2 VPC Endpoints — Prevent Data Exfiltration via AWS APIs

```hcl
# Terraform — VPC Endpoints to keep AWS API traffic within your network
# Without VPC endpoints: traffic to S3/STS/Secrets Manager goes over internet
# With VPC endpoints: traffic stays within AWS backbone

# S3 Gateway Endpoint (free, routes through VPC)
resource "aws_vpc_endpoint" "s3" {
  vpc_id            = aws_vpc.main.id
  service_name      = "com.amazonaws.${var.region}.s3"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = [aws_route_table.private.id]

  # S3 endpoint policy: restrict to your buckets only
  # This prevents exfiltration to attacker-controlled S3 buckets
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect    = "Allow"
        Principal = "*"
        Action    = ["s3:GetObject", "s3:PutObject", "s3:ListBucket"]
        Resource  = [
          "arn:aws:s3:::${var.app_bucket}",
          "arn:aws:s3:::${var.app_bucket}/*",
          # Allow AWS-managed buckets for SSM, EC2, etc.
          "arn:aws:s3:::aws-ssm-*",
          "arn:aws:s3:::amazon-ssm-*",
        ]
      },
      {
        # DENY: Prevent exfiltration to external S3 buckets
        Effect    = "Deny"
        Principal = "*"
        Action    = "s3:*"
        Resource  = "*"
        Condition = {
          StringNotLike = {
            "s3:DataAccessPointArn" = "arn:aws:s3:::${var.app_bucket}*"
          }
          ArnNotLike = {
            "aws:PrincipalArn" = [
              "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"
            ]
          }
        }
      }
    ]
  })
}

# Secrets Manager Interface Endpoint
resource "aws_vpc_endpoint" "secretsmanager" {
  vpc_id              = aws_vpc.main.id
  service_name        = "com.amazonaws.${var.region}.secretsmanager"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = aws_subnet.private[*].id
  security_group_ids  = [aws_security_group.vpc_endpoint.id]
  private_dns_enabled = true  # Enables private DNS — secretsmanager.us-east-1.amazonaws.com resolves to VPC IP
}

# STS Interface Endpoint (for assuming roles without internet)
resource "aws_vpc_endpoint" "sts" {
  vpc_id              = aws_vpc.main.id
  service_name        = "com.amazonaws.${var.region}.sts"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = aws_subnet.private[*].id
  security_group_ids  = [aws_security_group.vpc_endpoint.id]
  private_dns_enabled = true
}
```

---

# PART 49 — SECURITY FOR ML PIPELINES

---

## Chapter 89: Securing the ML Model Lifecycle

```python
# Python — Secure ML pipeline with model signing and supply chain integrity

import hashlib
import json
import os
from pathlib import Path
from datetime import datetime, timezone
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, padding
from cryptography.hazmat.backends import default_backend

class MLModelSigner:
    """
    Signs ML models and training artifacts to ensure:
    1. Provenance: who trained this model?
    2. Integrity: has the model been tampered with?
    3. Lineage: what data and code produced this model?
    """

    def __init__(self, private_key_path: str):
        with open(private_key_path, "rb") as f:
            self.private_key = serialization.load_pem_private_key(
                f.read(),
                password=os.environ.get("MODEL_SIGNING_KEY_PASSWORD", "").encode() or None,
                backend=default_backend(),
            )

    def compute_model_hash(self, model_path: str) -> str:
        """SHA-256 hash of the model artifact"""
        sha256 = hashlib.sha256()
        with open(model_path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                sha256.update(chunk)
        return sha256.hexdigest()

    def sign_model(
        self,
        model_path: str,
        training_metadata: dict,
    ) -> dict:
        """
        Create a signed provenance record for an ML model.
        Includes: model hash, training data hash, code version, trainer identity.
        """
        model_hash       = self.compute_model_hash(model_path)
        training_dataset = training_metadata.get("dataset_path")
        data_hash        = self.compute_model_hash(training_dataset) if training_dataset else None

        provenance = {
            "model_file":    Path(model_path).name,
            "model_sha256":  model_hash,
            "model_size":    Path(model_path).stat().st_size,
            "training_data": {
                "path":   training_dataset,
                "sha256": data_hash,
            },
            "training_code": {
                "git_commit": training_metadata.get("git_commit"),
                "git_repo":   training_metadata.get("git_repo"),
                "git_dirty":  training_metadata.get("git_dirty", True),
            },
            "environment": {
                "python_version": training_metadata.get("python_version"),
                "framework":      training_metadata.get("framework"),
                "framework_version": training_metadata.get("framework_version"),
            },
            "trainer": {
                "user":        training_metadata.get("trained_by"),
                "machine":     training_metadata.get("machine"),
                "ci_pipeline": training_metadata.get("ci_run_id"),
            },
            "signed_at": datetime.now(timezone.utc).isoformat(),
        }

        # Sign the provenance record
        canonical = json.dumps(provenance, sort_keys=True, separators=(",", ":")).encode()

        if isinstance(self.private_key, ec.EllipticCurvePrivateKey):
            signature = self.private_key.sign(canonical, ec.ECDSA(hashes.SHA256()))
        else:
            # RSA
            signature = self.private_key.sign(canonical, padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH,
            ), hashes.SHA256())

        import base64
        provenance["signature"] = base64.b64encode(signature).decode()

        # Write provenance alongside model
        provenance_path = model_path + ".provenance.json"
        with open(provenance_path, "w") as f:
            json.dump(provenance, f, indent=2)

        return provenance

class MLModelVerifier:
    """Verify model integrity and provenance before deployment"""

    TRUSTED_SIGNERS = {
        "training_pipeline": "PUBLIC_KEY_PEM_HERE",
        "approved_researcher": "PUBLIC_KEY_PEM_HERE",
    }

    def verify_before_deployment(self, model_path: str, provenance_path: str) -> bool:
        """
        Complete pre-deployment verification:
        1. Provenance file exists and is valid JSON
        2. Signature is valid from a trusted signer
        3. Model hash matches provenance
        4. Training code was from approved git repository
        5. Model was not trained on dirty (modified) code
        """
        with open(provenance_path) as f:
            provenance = json.load(f)

        # Step 1: Verify signature
        sig_b64   = provenance.pop("signature")
        canonical = json.dumps(provenance, sort_keys=True, separators=(",", ":")).encode()

        import base64
        signature = base64.b64decode(sig_b64)

        verified = False
        for signer_name, pubkey_pem in self.TRUSTED_SIGNERS.items():
            try:
                from cryptography.hazmat.primitives.serialization import load_pem_public_key
                pub_key = load_pem_public_key(pubkey_pem.encode())
                pub_key.verify(signature, canonical, ec.ECDSA(hashes.SHA256()))
                print(f"✓ Signature verified: signed by {signer_name}")
                verified = True
                break
            except Exception:
                continue

        if not verified:
            raise SecurityError("Model provenance signature invalid or from unknown signer")

        # Step 2: Verify model hash
        actual_hash = hashlib.sha256(open(model_path, "rb").read()).hexdigest()
        if actual_hash != provenance["model_sha256"]:
            raise SecurityError(f"Model hash mismatch! Model has been tampered with.")

        # Step 3: Reject models trained on dirty (uncommitted) code
        if provenance["training_code"].get("git_dirty"):
            raise SecurityError("Model trained on uncommitted code changes — not deployable")

        # Step 4: Verify training repo is approved
        APPROVED_REPOS = {"github.com/yourorg/ml-training"}
        repo = provenance["training_code"].get("git_repo", "")
        if not any(approved in repo for approved in APPROVED_REPOS):
            raise SecurityError(f"Model trained from unapproved repository: {repo}")

        print("✓ All model verification checks passed")
        return True
```

---

# PART 50 — CIRCUIT BREAKERS AND RESILIENCE SECURITY

---

## Chapter 90: Security-Aware Circuit Breakers

```python
# Python — Circuit breaker pattern for security-sensitive operations
from enum import Enum
from dataclasses import dataclass, field
import time
import threading

class CircuitState(Enum):
    CLOSED   = "closed"    # Normal operation
    OPEN     = "open"      # Failing — reject requests
    HALF_OPEN = "half_open"  # Testing recovery

@dataclass
class CircuitBreaker:
    """
    Circuit breaker for security-sensitive external dependencies.
    Prevents cascading failures and protects against:
    - Dependent service unavailability
    - Credential verification service failures
    - Denial of service through slow external calls
    """

    name:              str
    failure_threshold: int    = 5      # Open after N failures in window
    recovery_timeout:  float  = 60.0   # Seconds before trying again
    window_seconds:    float  = 60.0   # Failure counting window

    _state:      CircuitState = field(default=CircuitState.CLOSED, init=False)
    _failures:   list[float]  = field(default_factory=list, init=False)
    _last_open:  float        = field(default=0.0, init=False)
    _lock:       threading.Lock = field(default_factory=threading.Lock, init=False)

    @property
    def state(self) -> CircuitState:
        with self._lock:
            return self._get_state()

    def _get_state(self) -> CircuitState:
        if self._state == CircuitState.OPEN:
            if time.time() - self._last_open > self.recovery_timeout:
                self._state = CircuitState.HALF_OPEN
        return self._state

    def call(self, func: callable, *args, fallback=None, **kwargs):
        """Execute function with circuit breaker protection"""
        with self._lock:
            state = self._get_state()

            if state == CircuitState.OPEN:
                if fallback is not None:
                    return fallback
                raise CircuitOpenError(
                    f"Circuit '{self.name}' is OPEN — dependency unavailable"
                )

        # Attempt the call
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            if fallback is not None:
                return fallback
            raise

    def _on_success(self):
        with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                # Recovery confirmed
                self._state    = CircuitState.CLOSED
                self._failures = []
            # Clear old failures outside the window
            self._failures = [t for t in self._failures if time.time() - t < self.window_seconds]

    def _on_failure(self):
        with self._lock:
            self._failures.append(time.time())
            # Remove old failures
            self._failures = [t for t in self._failures if time.time() - t < self.window_seconds]

            if len(self._failures) >= self.failure_threshold:
                if self._state != CircuitState.OPEN:
                    self._state    = CircuitState.OPEN
                    self._last_open = time.time()
                    # Alert: a critical dependency is failing
                    import structlog
                    structlog.get_logger().error(
                        "circuit_breaker_opened",
                        circuit=self.name,
                        failures=len(self._failures),
                    )

# Security-specific circuit breaker applications
class SecurityCircuitBreakers:
    """
    Circuit breakers for security-critical operations.
    When these open, we fail securely (deny access) not fail open.
    """

    # If the MFA verification service is down, DENY access (fail closed)
    mfa_verifier = CircuitBreaker(
        name="mfa_verification",
        failure_threshold=3,   # Open faster for auth services
        recovery_timeout=30,
    )

    # If the certificate revocation check fails, DENY connection
    ocsp_checker = CircuitBreaker(
        name="ocsp_check",
        failure_threshold=5,
        recovery_timeout=60,
    )

    # If the rate limiter (Redis) is down, use in-memory fallback (not open)
    rate_limiter_redis = CircuitBreaker(
        name="rate_limiter_redis",
        failure_threshold=3,
        recovery_timeout=30,
    )

def verify_mfa_with_circuit_breaker(code: str, user_id: str) -> bool:
    try:
        return SecurityCircuitBreakers.mfa_verifier.call(
            external_mfa_service.verify,
            code=code,
            user_id=user_id,
            # CRITICAL: No fallback — if MFA service is down, deny access
            # fallback=None means CircuitOpenError is raised = 503 to user
        )
    except CircuitOpenError:
        # Fail securely: deny access when we can't verify MFA
        raise ServiceUnavailableError(
            "Authentication service temporarily unavailable. Please try again."
        )

class CircuitOpenError(Exception):
    pass
```

---

# FINAL CHAPTER — THE DEVELOPER SECURITY MASTERY LEARNING PATH

---

## Chapter 91: Your Security Skill Development Roadmap

### The Four Stages of Security Mastery

```
STAGE 1: SECURE CODING (Months 1-3)
Target: Write code that doesn't introduce vulnerabilities
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
□ Complete OWASP Top 10 — understand each, write tests for each
□ Master input validation with schema libraries (Pydantic/Zod)
□ Implement authentication from scratch (JWT, sessions, passwords)
□ Understand cryptography fundamentals (when, what, why)
□ Write parameterized queries for all database access
□ Set up security headers on a production service
□ Add secrets to Vault/Secrets Manager, zero hardcoded secrets
□ Write security tests for every trust boundary
□ Pass: Build a CRUD API that passes all OWASP tests

STAGE 2: SECURITY ARCHITECTURE (Months 4-6)
Target: Design systems that are secure by default
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
□ Conduct a threat model (STRIDE) for a system you work on
□ Implement OAuth 2.0 + PKCE authorization flow
□ Set up mTLS between two microservices
□ Design a multi-tenant authorization model with RLS
□ Implement GDPR compliance for a data model
□ Build a DevSecOps pipeline with SAST + SCA + container scanning
□ Deploy an application to Kubernetes with pod security standards
□ Implement zero-trust network policies
□ Pass: Threat model a real system and fix the top 3 findings

STAGE 3: SECURITY OPERATIONS (Months 7-9)
Target: Detect, respond to, and recover from incidents
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
□ Set up structured audit logging with SIEM integration
□ Write Falco rules for your production environment
□ Run a tabletop incident response exercise
□ Execute a credential compromise playbook end-to-end
□ Run security chaos experiments (credential rotation, secret rotation)
□ Instrument distributed tracing with security context
□ Build automated security response for brute force detection
□ Complete a SOC 2 evidence collection exercise
□ Pass: Simulate a breach and execute complete incident response

STAGE 4: SECURITY LEADERSHIP (Months 10-12)
Target: Elevate security across your organization
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
□ Launch a Security Champions program for your team
□ Conduct security code review for a major feature
□ Design a bug bounty program
□ Build a Security Maturity assessment for your org
□ Implement post-quantum cryptography hybrid patterns
□ Lead a red team / blue team exercise
□ Build security metrics dashboard and OKRs
□ Mentor two junior engineers on security practices
□ Pass: Team improves on all security KPIs for one quarter
```

### Quick Reference: What to Use When

```
TASK                              USE
─────────────────────────────────────────────────────────────────────────────────────────
Encrypt data at rest              AES-256-GCM with KMS envelope encryption
Encrypt small data (key wrap)     RSA-OAEP-SHA256 or ECDH X25519 + HKDF
Sign JWT tokens                   HS256 (shared secret) or RS256/ES256 (keypair)
Hash passwords                    Argon2id (preferred), bcrypt (compatible), scrypt
Hash for integrity check          SHA-256 or SHA-384
Compare secrets/tokens            hmac.compare_digest() / crypto.timingSafeEqual()
Generate random tokens            crypto.randomBytes() / secrets.token_urlsafe()
Generate random keys              crypto.subtle.generateKey() / os.urandom(32)
Store secrets                     HashiCorp Vault / AWS Secrets Manager / Azure Key Vault
Authenticate users                Passkeys (WebAuthn) + TOTP backup
Service-to-service auth           mTLS + SPIFFE/SPIRE, or JWT with client credentials
Authorize resource access         RBAC + ownership check + DB-level RLS
Validate input                    Pydantic / Zod / Bean Validation (never regex alone)
Prevent SQL injection             Parameterized queries / ORM (always)
Prevent XSS                       Auto-escaping templates + CSP + DOMPurify for HTML
Prevent CSRF                      SameSite=Strict cookies + Double-submit token
Prevent SSRF                      Allowlist + IP range check after DNS resolution
Prevent path traversal            Path.resolve() + allowlist check
Prevent clickjacking              X-Frame-Options: DENY + CSP frame-ancestors
Sign container images             Cosign + Sigstore (keyless)
Scan for vulnerabilities          Trivy (OS + libraries) + Semgrep (code)
Monitor runtime security          Falco + eBPF
Detect credential leaks           Gitleaks + TruffleHog (pre-commit + CI)
Test security                     OWASP ZAP (DAST) + security unit tests + pen test
Comply with GDPR                  Data register + consent management + deletion API
Comply with PCI DSS               Tokenize cards + TLS + WAF + annual pen test
Comply with HIPAA                 Field-level PHI encryption + minimum necessary + audit log
Comply with SOC 2                 Automated evidence + access controls + incident response
Post-quantum cryptography         ML-KEM (key exchange) + ML-DSA (signatures) + hybrid
AI/LLM security                   Input classification + output schema + guard model
```

### Security Principles — The Master List

```
THE 20 PRINCIPLES OF SECURE ENGINEERING

1.  ALL USER INPUT IS ADVERSARIAL
    Validate, type-check, constrain, encode, whitelist. Always.

2.  AUTHENTICATION IS NOT AUTHORIZATION
    Who you are ≠ what you can do. Check both. Test both. Test the boundary.

3.  LEAST PRIVILEGE IS NOT OPTIONAL
    Grant the minimum permissions required. Never grant "for now, until we fix it."

4.  SECRETS HAVE A LIFECYCLE
    Generate → protect → rotate → audit → expire. Never hardcode.

5.  ENCRYPTION WITHOUT KEY MANAGEMENT IS SECURITY THEATER
    The strength of AES-256 is irrelevant if the key is in the config file.

6.  EVERY DEPENDENCY IS YOUR CODE
    A CVE in your dependency is your vulnerability. Audit. Pin. Monitor.

7.  THE NETWORK IS NOT TRUSTED (ZERO TRUST)
    Internal traffic is not safe. Authenticate and authorize every call.

8.  FAIL CLOSED, NOT OPEN
    When security controls fail, deny access. Never default to permissive.

9.  DEFENSE IN DEPTH IS REQUIRED
    No single control is sufficient. Every control can and will fail.

10. SECURITY TESTS ARE FIRST-CLASS TESTS
    An untested security control is an imaginary security control.

11. AUDIT LOGS ARE EVIDENCE
    Design them to answer: who did what to what when from where and why.
    Never log sensitive data. Never delete logs.

12. THE ADVERSARY ADAPTS
    Fraud detection, AI systems, and spam filters all face adversaries who learn.
    Static controls degrade. Build ongoing adversarial evaluation.

13. SUPPLY CHAIN IS ATTACK SURFACE
    Your build system, your dependencies, your CI runners — all are targets.
    Sign. Verify. SBOM. Reproducible builds.

14. TIMING LEAKS INFORMATION
    Compare secrets with constant-time functions. Every time. Without exception.

15. PRIVACY IS A SECURITY PROPERTY
    Unnecessary data collection is a security liability. Minimize. Pseudonymize. Delete.

16. COMPLIANCE IS THE FLOOR
    SOC 2, PCI DSS, HIPAA are minimums. Meeting them doesn't mean you're secure.
    Treat them as a starting point, not a destination.

17. SECURITY DEBT COMPOUNDS
    A skipped security control generates more risk over time than a skipped feature.
    Measure, track, and pay down security debt like financial debt.

18. HUMANS ARE PART OF THE SYSTEM
    Phishing, social engineering, and insider threats are security problems.
    Design workflows that resist human error and manipulation.

19. POST-QUANTUM THREATS ARE REAL AND TIMED
    RSA, ECDH, ECDSA are broken by quantum computers.
    Migrate long-lived data NOW. Plan key exchange migration.

20. SECURITY IS A PROPERTY OF THE WHOLE SYSTEM
    Not a product. Not a team. Not a phase.
    It emerges from every decision made by every engineer on every day.
    Make it a professional identity, not a compliance checkbox.
```

---

## Complete Guide Statistics

```
HANDBOOK COVERAGE SUMMARY
═══════════════════════════════════════════════════════════════════════════════

VOLUMES:        7 parts × 8–10 chapters = 91 chapters total
LINES OF CODE:  ~12,000 lines across all examples
LANGUAGES:      Java · Python · Go · Rust · TypeScript · C · SQL · HCL · YAML
PLATFORMS:      Web · Mobile (iOS/Android) · Desktop · IoT · Serverless · Container
ATTACK TYPES:   45+ distinct attack categories with exploits and defenses
FRAMEWORKS:     OWASP Top 10 · MITRE ATT&CK · STRIDE · LINDDUN · PASTA
                NIST CSF · SLSA · SPIFFE · GDPR · HIPAA · PCI DSS · SOC 2 · ISO 27001
COMPLIANCE:     GDPR engineering implementation (not legal) · HIPAA PHI handling
                PCI DSS tokenization · SOC 2 evidence automation
                ISO 27001 controls · NIST CSF mapping

PART 1:  Foundations, Threat Modeling, Cryptography, Auth, OWASP Top 10, Secure Coding
PART 2:  API Security, Cloud, Containers, DevSecOps, AI, Zero Trust, Database
PART 3:  Mobile, IoT, Identity, Network, SOC 2, HIPAA, Advanced Patterns
PART 4:  Passkeys, Advanced AI/MCP, Microservices, PKI, Chaos, PenTest, PQ Crypto
PART 5:  SSTI, XXE, Prototype Pollution, Serverless, Kafka, NoSQL/LDAP, Falco, Incident Response
PART 6:  OAuth Attacks, DPoP, CSP, CORS, Vault, Events, eBPF, GDPR Erasure, Security Automation
PART 7:  GraphQL, Cookies, Webhooks, Background Jobs, IMDSv2, ML Security, Log Masking, Circuit Breakers

═══════════════════════════════════════════════════════════════════════════════
```

---

*This is Part 7 — the final volume of the Developer's Cybersecurity Mastery handbook.*

*Covered in this volume: GraphQL advanced security (persisted queries with hash validation, field-level authorization with DataLoader batching, query allow-listing), Cookie security deep dive (__Host- and __Secure- prefixes, SameSite, cookie tossing prevention), Webhook signature validation for Stripe, GitHub, Twilio, Shopify with replay prevention, Secure background jobs (Celery with HMAC-signed task payloads, idempotency, no sensitive data in queue), Sensitive data log masking (regex patterns, field-name detection, URL masking, structlog integration), AWS IMDSv2 enforcement, VPC endpoints for exfiltration prevention, ML model signing and provenance verification with ECDSA, Security-aware circuit breakers (fail-closed pattern for auth dependencies), and the complete Developer Security Mastery Learning Path with four stages, quick reference tables, and the 20 Principles of Secure Engineering.*

*The complete 7-part series constitutes a comprehensive developer security curriculum spanning secure coding fundamentals through expert-level architecture, compliance engineering, AI security, and organizational security leadership. Every chapter contains production-ready code examples in Java, Python, Go, Rust, and TypeScript.*
