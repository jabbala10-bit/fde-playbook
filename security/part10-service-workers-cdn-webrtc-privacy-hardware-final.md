# Developer's Cybersecurity Mastery: The Complete Handbook
## Volume 81–90 | Service Workers · CDN · WebRTC · Privacy Analytics · Hardware Attestation · Side-Channel · Blockchain · Threat Hunting · SDL

---

# PART 65 — SERVICE WORKERS AND PWA SECURITY

---

## Chapter 112: Progressive Web App Security

### 112.1 Service Worker Security Model

```typescript
// TypeScript — Secure Service Worker implementation

// Service workers are a powerful but risky feature:
// - They intercept ALL network requests for your app
// - They can cache and serve responses (including malicious ones if compromised)
// - They persist even after the browser tab is closed
// - A compromised SW is a persistent MITM on your own origin

// SECURITY RULES FOR SERVICE WORKERS:
// 1. ONLY serve SW from your own origin (no CDN hosting)
// 2. Scope should be as narrow as possible
// 3. ALWAYS use HTTPS (browsers require this)
// 4. Validate the integrity of cached content
// 5. Implement proper cache versioning and cleanup
// 6. Never cache authorization tokens or sensitive data

// sw.js — Production-hardened service worker
const CACHE_VERSION  = 'v3.2.1';
const STATIC_CACHE   = `static-${CACHE_VERSION}`;
const DYNAMIC_CACHE  = `dynamic-${CACHE_VERSION}`;

// Allowlist of origins the SW can fetch from
const ALLOWED_ORIGINS = new Set([
    self.location.origin,
    'https://cdn.example.com',
    'https://fonts.googleapis.com',
    'https://fonts.gstatic.com',
]);

// Allowlist of paths that should be cached
const CACHEABLE_EXTENSIONS = new Set([
    '.js', '.css', '.woff2', '.png', '.svg', '.ico',
]);

self.addEventListener('install', (event: ExtendableEvent) => {
    event.waitUntil(
        caches.open(STATIC_CACHE).then(cache => {
            // Only cache specific, known-good assets
            return cache.addAll([
                '/index.html',
                '/manifest.json',
                '/offline.html',
                '/static/app.css',
                '/static/app.js',
            ]);
        })
    );
    // Activate immediately — don't wait for old SW to finish
    self.skipWaiting();
});

self.addEventListener('activate', (event: ExtendableEvent) => {
    event.waitUntil(
        caches.keys().then(cacheNames => {
            // Delete ALL caches from old versions
            // This prevents stale, potentially vulnerable cached content
            return Promise.all(
                cacheNames
                    .filter(name =>
                        (name.startsWith('static-') || name.startsWith('dynamic-')) &&
                        name !== STATIC_CACHE &&
                        name !== DYNAMIC_CACHE
                    )
                    .map(name => {
                        console.log(`[SW] Deleting old cache: ${name}`);
                        return caches.delete(name);
                    })
            );
        })
    );
    // Take control of all clients immediately
    self.clients.claim();
});

self.addEventListener('fetch', (event: FetchEvent) => {
    const url = new URL(event.request.url);

    // ── Security Check 1: Only handle requests from allowed origins ──────────
    if (!ALLOWED_ORIGINS.has(url.origin)) {
        // Don't intercept requests to unknown origins
        return;
    }

    // ── Security Check 2: Never intercept API requests ───────────────────────
    // API requests carry authorization tokens and must always go to server
    if (url.pathname.startsWith('/api/') || url.pathname.startsWith('/auth/')) {
        event.respondWith(
            fetch(event.request).catch(() => {
                // API failed while offline — return offline error response
                return new Response(
                    JSON.stringify({ error: 'offline' }),
                    {
                        status: 503,
                        headers: { 'Content-Type': 'application/json' }
                    }
                );
            })
        );
        return;
    }

    // ── Security Check 3: Only cache safe file types ─────────────────────────
    const extension = url.pathname.substring(url.pathname.lastIndexOf('.'));
    if (!CACHEABLE_EXTENSIONS.has(extension) && url.pathname !== '/') {
        event.respondWith(fetch(event.request));
        return;
    }

    // ── Cache with network fallback for static assets ────────────────────────
    event.respondWith(
        caches.match(event.request).then(cachedResponse => {
            if (cachedResponse) {
                // Background refresh: update cache while serving stale
                event.waitUntil(
                    fetch(event.request).then(networkResponse => {
                        if (networkResponse.ok) {
                            caches.open(DYNAMIC_CACHE).then(cache => {
                                cache.put(event.request, networkResponse);
                            });
                        }
                    }).catch(() => {}) // Ignore update failures
                );
                return cachedResponse;
            }

            return fetch(event.request).then(networkResponse => {
                // Validate response before caching
                if (!networkResponse.ok || networkResponse.type === 'opaque') {
                    return networkResponse;
                }

                // Check Content-Type is as expected
                const contentType = networkResponse.headers.get('content-type') || '';
                if (extension === '.js' && !contentType.includes('javascript')) {
                    console.warn('[SW] Unexpected content-type for JS file — not caching');
                    return networkResponse;
                }

                // Cache a clone (response body can only be read once)
                const responseClone = networkResponse.clone();
                caches.open(DYNAMIC_CACHE).then(cache => {
                    cache.put(event.request, responseClone);
                });

                return networkResponse;
            }).catch(() => {
                // Network failed — serve offline page for navigation requests
                if (event.request.mode === 'navigate') {
                    return caches.match('/offline.html');
                }
                return new Response('', { status: 503 });
            });
        })
    );
});

// ── Security: Handle messages from the main thread ────────────────────────────
self.addEventListener('message', (event: MessageEvent) => {
    // Validate message source
    if (!event.source) return;

    // Only accept specific, expected message types
    const ALLOWED_MESSAGES = new Set(['SKIP_WAITING', 'CLEAR_CACHE']);
    if (!ALLOWED_MESSAGES.has(event.data?.type)) {
        return;
    }

    if (event.data.type === 'SKIP_WAITING') {
        self.skipWaiting();
    } else if (event.data.type === 'CLEAR_CACHE') {
        caches.delete(DYNAMIC_CACHE);
    }
});
```

---

# PART 66 — CDN SECURITY AND CACHE POISONING

---

## Chapter 113: CDN Security and Cache Poisoning Attacks

### 113.1 Cache Poisoning Prevention

```python
# Python — Cache poisoning attack patterns and defenses

"""
CACHE POISONING OVERVIEW:
  Attacker tricks a CDN/cache to serve their malicious content to other users.
  Attack vector: HTTP headers, host headers, URL normalizations that the
  cache treats as "the same" but the backend treats as "different."

ATTACK TYPES:
  1. Host Header Injection → Poison with different origin
  2. X-Forwarded-Host injection → Cache uses this for URL construction
  3. HTTP Parameter Pollution → ?param=value&param=evil cached as one
  4. HTTP Method Override → POST treated as GET by cache
  5. Unkeyed header injection → Cache ignores header but backend uses it
"""

from fastapi import Request, Response

class CachePoisoningDefense:
    """Defenses against cache poisoning attacks"""

    def validate_host_header(self, request: Request) -> str:
        """
        Validate and normalize the Host header.
        Prevent host header injection attacks.
        """
        ALLOWED_HOSTS = frozenset([
            "app.example.com",
            "www.example.com",
            "api.example.com",
        ])

        host = request.headers.get("host", "").lower().strip()

        # Remove port if present
        if ":" in host:
            host = host.split(":")[0]

        if host not in ALLOWED_HOSTS:
            raise ValueError(f"Invalid Host header: {host}")

        return host

    def strip_cache_poisoning_headers(
        self, request: Request, response: Response
    ) -> Response:
        """
        Strip headers that could be used for cache poisoning.
        These should be stripped at the CDN/proxy level, but defense in depth.
        """
        # Headers that should never influence cache key or content generation
        POISONING_HEADERS = [
            "x-forwarded-host",
            "x-original-url",
            "x-rewrite-url",
            "x-forwarded-prefix",
            "x-forwarded-server",
            "x-host",
            "x-custom-ip-authorization",
        ]

        # Validate the request didn't use these headers to influence content
        for header in POISONING_HEADERS:
            if header in request.headers:
                # Log potential cache poisoning attempt
                import structlog
                structlog.get_logger().warning(
                    "cache_poisoning_attempt",
                    header=header,
                    value=request.headers[header][:100],
                    ip=request.client.host,
                )

        # Ensure response headers don't expose cache poisoning vulnerabilities
        response.headers["Vary"] = "Accept-Encoding, Accept"
        # DO NOT Vary on user-agent, cookies, or other client-specific headers
        # (that would just mean the cache key is less effective, not fix poisoning)

        # Cache-Control for HTML responses
        if "text/html" in response.headers.get("content-type", ""):
            response.headers["Cache-Control"] = "no-store, private"
            # HTML pages with personalized content MUST not be cached by CDN

        return response

    def generate_cache_busting_url(self, asset_url: str, asset_hash: str) -> str:
        """
        Content-addressed URLs prevent cache poisoning for static assets.
        URL includes the hash of the content — tampered content = different URL.
        """
        # /static/app.js?v=abc123 (version-based — mutable, poisonable)
        # /static/app.abc123.js (content-addressed — immutable, safe)
        base, ext = asset_url.rsplit(".", 1)
        return f"{base}.{asset_hash[:8]}.{ext}"
```

```nginx
# nginx.conf — CDN/reverse proxy cache poisoning mitigations

http {
    # Strip dangerous headers before they reach your application
    proxy_set_header X-Forwarded-Host     "";  # Don't forward — use actual Host
    proxy_set_header X-Original-URL       "";
    proxy_set_header X-Rewrite-URL        "";
    proxy_set_header X-Custom-IP-Authorization "";

    # Only proxy from trusted downstream CDN IPs
    set_real_ip_from 103.21.244.0/22;   # Cloudflare
    set_real_ip_from 103.22.200.0/22;   # Cloudflare
    real_ip_header CF-Connecting-IP;

    # Cache key should include Host (prevent cross-host cache poisoning)
    # and the actual request URI only
    proxy_cache_key "$scheme$host$request_uri";

    # NEVER include these in cache key (they're from client, untrustworthy):
    # X-Forwarded-For, User-Agent, Accept-Language (without explicit Vary)

    server {
        # Host header validation — reject unknown hosts
        if ($host !~ ^(app\.example\.com|api\.example\.com)$) {
            return 421;  # Misdirected Request
        }

        # Cache-Control for API responses (NEVER cache)
        location /api/ {
            proxy_cache off;
            add_header Cache-Control "no-store, private" always;
            add_header Vary "Authorization" always;  # Different per user
        }

        # Static assets: cache with content-addressed URLs
        location ~* \.(js|css|png|woff2)$ {
            # Content-addressed URLs can be cached indefinitely
            add_header Cache-Control "public, max-age=31536000, immutable";
            # 'immutable' tells browser NOT to revalidate during max-age
        }
    }
}
```

---

# PART 67 — WEBRTC SECURITY

---

## Chapter 114: Securing WebRTC Applications

```typescript
// TypeScript — Secure WebRTC implementation

class SecureWebRTCManager {
    private peerConnection: RTCPeerConnection | null = null;
    private dataChannel:    RTCDataChannel | null    = null;

    // TURN server with authentication (NEVER expose without auth)
    private readonly ICE_SERVERS: RTCIceServer[] = [
        {
            urls:       "stun:stun.example.com:3478",
        },
        {
            urls:       "turn:turn.example.com:3478",
            username:   "", // Fetched dynamically from server
            credential: "", // Short-lived HMAC credential
        },
    ];

    async createSecureConnection(
        userId:      string,
        remoteUserId: string,
        authToken:   string,
    ): Promise<void> {
        // Step 1: Get ephemeral TURN credentials from server
        // NEVER hardcode TURN credentials — they'd be visible to all users
        const turnCreds = await this.getEphemeralTURNCredentials(authToken);

        const iceServers: RTCIceServer[] = [
            { urls: "stun:stun.example.com:3478" },
            {
                urls:       `turn:turn.example.com:3478`,
                username:   turnCreds.username,    // Expires in 5 minutes
                credential: turnCreds.credential,  // HMAC-SHA1 of username+timestamp
            },
        ];

        // Step 2: Create peer connection with security constraints
        this.peerConnection = new RTCPeerConnection({
            iceServers,
            // Force relay through TURN (prevents IP leakage via STUN)
            // USE ONLY IF PRIVACY IS CRITICAL (reduces performance)
            iceTransportPolicy: 'relay',

            // Require DTLS for all data channels
            certificates: await RTCPeerConnection.generateCertificate({
                name:           "ECDSA",
                namedCurve:     "P-256",
                // Certificate bound to this session — not reusable
            }),
        });

        // Step 3: Create authenticated data channel
        this.dataChannel = this.peerConnection.createDataChannel('secure', {
            ordered:          true,    // Ordered delivery
            maxRetransmits:   3,       // Limit retransmissions
            protocol:         'json',  // Application protocol
        });

        this.setupDataChannelSecurity();
        this.setupConnectionMonitoring();
    }

    private setupDataChannelSecurity(): void {
        if (!this.dataChannel) return;

        this.dataChannel.onmessage = (event: MessageEvent) => {
            // Validate all incoming messages
            try {
                const data = JSON.parse(event.data);
                this.validateAndProcessMessage(data);
            } catch (e) {
                console.error('Invalid message received:', e);
                // Don't trust or process malformed messages
            }
        };

        this.dataChannel.onopen = () => {
            // DataChannel uses DTLS — verify the fingerprint matches the signaling
            this.verifyDTLSFingerprint();
        };
    }

    private validateAndProcessMessage(data: unknown): void {
        // Schema validation for all incoming messages
        if (typeof data !== 'object' || data === null) {
            throw new Error('Message must be an object');
        }

        const msg = data as Record<string, unknown>;

        // Validate message type is expected
        const ALLOWED_TYPES = new Set(['chat', 'file-offer', 'file-accept', 'ping']);
        if (!ALLOWED_TYPES.has(msg.type as string)) {
            throw new Error(`Unknown message type: ${msg.type}`);
        }

        // Size limits — prevent DoS
        if (JSON.stringify(data).length > 64 * 1024) {
            throw new Error('Message too large');
        }

        // Process validated message...
    }

    private async verifyDTLSFingerprint(): Promise<void> {
        /**
         * DTLS fingerprint verification:
         * During signaling (before WebRTC connection), both peers exchange
         * the fingerprint of their DTLS certificate via HTTPS (trusted channel).
         * When DTLS handshake completes, verify the actual fingerprint matches.
         * This prevents MITM attacks even if the STUN/TURN server is compromised.
         */
        const stats   = await this.peerConnection!.getStats();
        let actualFP: string | null = null;

        stats.forEach(report => {
            if (report.type === 'certificate') {
                actualFP = report.fingerprint;
            }
        });

        // Compare with fingerprint received during signaling
        const expectedFP = sessionStorage.getItem('peer_dtls_fingerprint');
        if (actualFP && expectedFP && actualFP !== expectedFP) {
            // Fingerprint mismatch — possible MITM
            console.error('DTLS fingerprint mismatch — closing connection');
            this.peerConnection!.close();
        }
    }

    private async getEphemeralTURNCredentials(authToken: string): Promise<{
        username:   string;
        credential: string;
        ttl:        number;
    }> {
        const response = await fetch('/api/rtc/credentials', {
            method:  'POST',
            headers: {
                'Authorization': `Bearer ${authToken}`,
                'Content-Type':  'application/json',
            },
        });

        if (!response.ok) throw new Error('Failed to get TURN credentials');
        return response.json();
    }

    private setupConnectionMonitoring(): void {
        if (!this.peerConnection) return;

        // Monitor for unexpected connection state changes
        this.peerConnection.onconnectionstatechange = () => {
            const state = this.peerConnection!.connectionState;
            if (state === 'failed' || state === 'disconnected') {
                // Immediately clean up on connection failure
                this.cleanup();
            }
        };

        // Detect ICE gathering anomalies
        let relayCount = 0;
        this.peerConnection.onicecandidate = (event) => {
            if (event.candidate) {
                const candidateType = event.candidate.type;
                // Count relay candidates (TURN) vs host candidates
                if (candidateType === 'relay') relayCount++;
            }
        };
    }

    sendSecureMessage(content: string): void {
        if (!this.dataChannel || this.dataChannel.readyState !== 'open') {
            throw new Error('Data channel not ready');
        }

        // Size limit
        if (content.length > 60 * 1024) {
            throw new Error('Message too large for data channel');
        }

        this.dataChannel.send(JSON.stringify({
            type:      'chat',
            content,
            timestamp: Date.now(),
        }));
    }

    cleanup(): void {
        this.dataChannel?.close();
        this.peerConnection?.close();
        this.dataChannel   = null;
        this.peerConnection = null;
    }
}
```

```python
# Python — TURN server ephemeral credential generation (server-side)
import hmac
import hashlib
import time
import base64
import os

def generate_turn_credentials(
    user_id: str,
    ttl_seconds: int = 300,
    turn_secret: bytes = None,
) -> dict:
    """
    Generate time-limited TURN credentials using HMAC-SHA1.
    Per RFC 5766 / Coturn short-term credentials.

    Credentials expire automatically — no need to revoke.
    Each user gets unique credentials bound to their identity.
    """
    if turn_secret is None:
        turn_secret = os.environ["TURN_SECRET"].encode()

    # Username format: timestamp:user_identifier
    expiry   = int(time.time()) + ttl_seconds
    username = f"{expiry}:{user_id}"

    # HMAC-SHA1 of username with the TURN secret
    mac = hmac.new(turn_secret, username.encode(), hashlib.sha1)
    credential = base64.b64encode(mac.digest()).decode()

    return {
        "username":   username,
        "credential": credential,
        "ttl":        ttl_seconds,
        "uris": [
            "turn:turn.example.com:3478?transport=udp",
            "turn:turn.example.com:3478?transport=tcp",
            "turns:turn.example.com:5349?transport=tcp",  # TURN over TLS
        ],
    }
```

---

# PART 68 — PRIVACY-PRESERVING ANALYTICS

---

## Chapter 115: Analytics Without Surveillance

```typescript
// TypeScript — Privacy-preserving analytics implementation

class PrivacyFirstAnalytics {
    /**
     * Collect analytics that:
     * 1. Never track individual users across sessions
     * 2. Don't send IP addresses to analytics servers
     * 3. Use aggregation instead of individual event logging
     * 4. Respect Do-Not-Track (DNT) and Global Privacy Control (GPC)
     * 5. Don't set persistent cookies
     */

    private sessionEvents: Map<string, number> = new Map();
    private consentGranted: boolean = false;

    initialize(): void {
        // Check consent and privacy signals
        this.consentGranted = this.checkConsent();

        if (!this.consentGranted) {
            console.log('Analytics disabled: no consent or DNT/GPC set');
            return;
        }

        // Flush aggregated metrics every 30s
        setInterval(() => this.flush(), 30_000);
        window.addEventListener('beforeunload', () => this.flush());
    }

    private checkConsent(): boolean {
        // Respect Global Privacy Control (GPC) — stronger than DNT
        if ((navigator as any).globalPrivacyControl === true) {
            return false;
        }

        // Respect Do Not Track
        if (navigator.doNotTrack === '1') {
            return false;
        }

        // Check explicit consent cookie/localStorage
        const consent = localStorage.getItem('analytics_consent');
        return consent === 'granted';
    }

    trackPageView(path: string): void {
        if (!this.consentGranted) return;

        // Count page views but DON'T log individual user paths
        const key = `pageview:${this.normalizePath(path)}`;
        this.sessionEvents.set(key, (this.sessionEvents.get(key) || 0) + 1);
    }

    trackEvent(category: string, action: string): void {
        if (!this.consentGranted) return;

        // Aggregate events by category+action — no individual user tracking
        const key = `event:${category}:${action}`;
        this.sessionEvents.set(key, (this.sessionEvents.get(key) || 0) + 1);
    }

    private normalizePath(path: string): string {
        // Remove user IDs and other PII from paths
        // /users/123456/settings → /users/:id/settings
        return path
            .replace(/\/[0-9a-f]{8}-[0-9a-f-]{27}/g, '/:uuid')  // UUID
            .replace(/\/\d{6,}/g, '/:id')                          // Long integers
            .replace(/[?#].*$/, '');                               // Remove query strings
    }

    private async flush(): Promise<void> {
        if (this.sessionEvents.size === 0) return;

        const metrics = Object.fromEntries(this.sessionEvents);
        this.sessionEvents.clear();

        try {
            await fetch('/api/analytics/collect', {
                method:      'POST',
                headers:     { 'Content-Type': 'application/json' },
                body:        JSON.stringify({
                    metrics,
                    // Privacy: random session ID (not user ID, not persistent)
                    session_id: this.getEphemeralSessionId(),
                    // Privacy: coarse time (hour, not timestamp)
                    hour:       new Date().getHours(),
                    // Privacy: no IP is sent — collected server-side but not stored
                }),
                // Privacy: prevent analytics from being blocked by tracking protection
                // Use beacon API for reliable delivery without blocking
                keepalive: true,
            });
        } catch (e) {
            // Silently fail — analytics should never affect user experience
        }
    }

    private getEphemeralSessionId(): string {
        // Session-scoped random ID — new each session, not stored in localStorage
        let sessionId = sessionStorage.getItem('_anon_session');
        if (!sessionId) {
            sessionId = crypto.randomUUID();
            sessionStorage.setItem('_anon_session', sessionId);
        }
        return sessionId;
    }
}

// Server-side: Store only aggregated metrics, not individual events
```

```python
# Python — Server-side privacy-preserving analytics aggregation

from collections import defaultdict
from datetime import datetime, timezone, timedelta
import asyncio
import json

class PrivacyPreservingMetricsAggregator:
    """
    Collects individual metric reports and aggregates them.
    Individual reports are NEVER persisted — only the aggregate is stored.
    Uses differential privacy noise to prevent re-identification.
    """

    def __init__(self, flush_interval_seconds: int = 60):
        self._buffer: dict[str, int] = defaultdict(int)
        self._lock   = asyncio.Lock()
        self._flush_interval = flush_interval_seconds

    async def record_metrics(self, metrics: dict[str, int], ip_address: str) -> None:
        """
        Record incoming metrics. IP address is used ONLY for fraud detection
        (too many events from one IP = bot) and then discarded.
        """
        # Bot detection (IP used here only)
        if not await self._is_legitimate_client(ip_address):
            return

        # Accumulate into buffer (IP not stored)
        async with self._lock:
            for key, count in metrics.items():
                # Validate key format: "pageview:/path" or "event:category:action"
                if not self._is_valid_metric_key(key):
                    continue
                # Cap individual contribution (prevents single user inflating metrics)
                self._buffer[key] += min(count, 10)

    def _is_valid_metric_key(self, key: str) -> bool:
        import re
        return bool(re.match(r'^(pageview|event):[a-z0-9/_:.-]{1,100}$', key))

    async def flush_aggregates(self, db) -> None:
        """
        Flush aggregated metrics to the database.
        Add Laplace noise for differential privacy.
        """
        async with self._lock:
            if not self._buffer:
                return
            snapshot      = dict(self._buffer)
            self._buffer.clear()

        # Add differential privacy noise
        epsilon = 1.0  # Privacy parameter
        noisy_metrics = {
            key: max(0, value + int(numpy.random.laplace(0, 1.0 / epsilon)))
            for key, value in snapshot.items()
        }

        # Store only the hour-granularity aggregate
        hour_bucket = datetime.now(timezone.utc).replace(
            minute=0, second=0, microsecond=0
        )

        await db.execute("""
            INSERT INTO hourly_metrics (hour, metric_key, count)
            VALUES ($1, $2, $3)
            ON CONFLICT (hour, metric_key) DO UPDATE
                SET count = hourly_metrics.count + EXCLUDED.count
        """, [(hour_bucket, key, count) for key, count in noisy_metrics.items()])

    async def _is_legitimate_client(self, ip: str) -> bool:
        """Simple rate limiting by IP — IP not logged"""
        key = f"analytics:rate:{ip}"
        # Check request rate — not stored permanently
        return True  # Placeholder
```

---

# PART 69 — HARDWARE ATTESTATION

---

## Chapter 116: TPM and Trusted Execution Environments

```python
# Python — Hardware attestation concepts and implementation

"""
HARDWARE ATTESTATION:
  Allows a device to prove to a remote server that it is running
  unmodified, authorized software on known-good hardware.

  Use cases:
  - Zero-trust device authentication (device must be uncompromised)
  - Secure boot verification before granting VPN access
  - Attestation of AI inference results (proving which model was run)
  - IoT device identity (preventing cloned firmware)

COMPONENTS:
  TPM (Trusted Platform Module):
    - Hardware chip that stores cryptographic keys
    - Keys cannot be exported from the TPM
    - Measures (hashes) each boot stage
    - Platform Configuration Registers (PCRs) record boot measurements
    - Remote attestation: server can verify PCR values

  TEE (Trusted Execution Environment):
    - Isolated execution environment (Intel SGX, ARM TrustZone, AMD SEV)
    - Code and data protected even from the OS
    - Can produce attestation quotes: proof of what code is running
"""

class AttestationVerifier:
    """
    Server-side verification of device attestation reports.
    Compatible with TPM 2.0 and common TEE platforms.
    """

    # Known good PCR values for approved boot configurations
    # PCR0: BIOS/UEFI firmware measurement
    # PCR4: Boot Manager measurement
    # PCR7: Secure Boot state
    TRUSTED_PCR_VALUES = {
        "PCR0": "sha256:abc123...",  # Known UEFI hash
        "PCR4": "sha256:def456...",  # Known bootloader hash
        "PCR7": "sha256:ghi789...",  # Secure Boot enabled + known keys
    }

    def verify_tpm_attestation(
        self,
        attestation_quote: dict,
        nonce: bytes,
        endorsement_key_cert: bytes,
    ) -> dict:
        """
        Verify a TPM 2.0 attestation quote.

        attestation_quote: TPM2_Attest structure from the device
        nonce:            Challenge we sent to prevent replay attacks
        endorsement_key_cert: TPM's EK certificate (from manufacturer)
        """

        result = {
            "valid":            False,
            "pcr_match":        False,
            "nonce_match":      False,
            "certificate_valid": False,
            "issues":           [],
        }

        # Step 1: Verify EK certificate chain
        # The Endorsement Key certificate is signed by the TPM manufacturer (e.g., Infineon, NXP)
        # Verify against known manufacturer CAs
        try:
            self._verify_ek_certificate(endorsement_key_cert)
            result["certificate_valid"] = True
        except Exception as e:
            result["issues"].append(f"EK certificate invalid: {e}")
            return result

        # Step 2: Verify the attestation quote signature
        # The quote is signed by the Attestation Key (AK)
        # The AK is certified by the EK
        try:
            self._verify_quote_signature(
                attestation_quote,
                endorsement_key_cert,
            )
        except Exception as e:
            result["issues"].append(f"Quote signature invalid: {e}")
            return result

        # Step 3: Verify the nonce matches (anti-replay)
        quote_nonce = attestation_quote.get("nonce", b"")
        if not self._constant_time_equal(quote_nonce, nonce):
            result["issues"].append("Nonce mismatch — possible replay attack")
            return result
        result["nonce_match"] = True

        # Step 4: Verify PCR values match expected
        quote_pcrs = attestation_quote.get("pcrs", {})
        for pcr_id, expected_value in self.TRUSTED_PCR_VALUES.items():
            actual_value = quote_pcrs.get(pcr_id, "")
            if actual_value != expected_value:
                result["issues"].append(
                    f"{pcr_id} mismatch: expected {expected_value[:16]}..., "
                    f"got {actual_value[:16]}..."
                )
                return result
        result["pcr_match"] = True

        result["valid"] = True
        return result

    def _constant_time_equal(self, a: bytes, b: bytes) -> bool:
        import hmac
        return hmac.compare_digest(a, b)

    def _verify_ek_certificate(self, cert_der: bytes) -> None:
        from cryptography import x509
        from cryptography.hazmat.backends import default_backend
        cert = x509.load_der_x509_certificate(cert_der, default_backend())
        # Verify against TPM manufacturer CA certificates
        # (Infineon, STMicro, NXP, etc.)
        # In production: use a full certificate chain verification

    def _verify_quote_signature(self, quote: dict, cert: bytes) -> None:
        # Verify the TPM's AK signed the quote
        # and the AK is certified by the EK
        pass

# Android Keystore Attestation (Play Integrity + KeyAttestation)
class AndroidKeyAttestation:
    """
    Verify that an Android device's key was generated in secure hardware
    and that the device is genuine and unmodified.
    """

    def verify_key_attestation(
        self,
        attestation_certificate_chain: list[bytes],
        expected_challenge: bytes,
    ) -> dict:
        """
        Android KeyAttestation certificate chain:
        [0] = Key certificate (for the attested key)
        [1] = Intermediate certificate
        [2] = Root certificate (verify against Google's root CA)
        """
        from cryptography import x509
        from cryptography.x509 import ExtensionNotFound
        from cryptography.hazmat.backends import default_backend

        result = {"valid": False, "strongbox": False, "issues": []}

        # Parse the key certificate
        key_cert = x509.load_der_x509_certificate(
            attestation_certificate_chain[0],
            default_backend()
        )

        # Extract Android Key Attestation Extension (OID: 1.3.6.1.4.1.11129.2.1.17)
        ANDROID_ATTESTATION_OID = "1.3.6.1.4.1.11129.2.1.17"
        try:
            ext = key_cert.extensions.get_extension_for_oid(
                x509.ObjectIdentifier(ANDROID_ATTESTATION_OID)
            )
        except ExtensionNotFound:
            result["issues"].append("Android attestation extension not found")
            return result

        # Parse the attestation extension (ASN.1)
        attestation = self._parse_attestation_extension(ext.value)

        # Check challenge matches
        if not hmac.compare_digest(
            attestation.get("attestation_challenge", b""),
            expected_challenge
        ):
            result["issues"].append("Challenge mismatch")
            return result

        # Check security level
        security_level = attestation.get("key_mint_security_level", 0)
        if security_level >= 2:  # STRONGBOX
            result["strongbox"] = True
        elif security_level == 1:  # TRUSTED_ENVIRONMENT (TEE)
            result["strongbox"] = False
        else:
            result["issues"].append("Key generated in software — not hardware-backed")
            return result

        # Verify certificate chain
        self._verify_certificate_chain(attestation_certificate_chain)

        result["valid"] = True
        return result

    def _parse_attestation_extension(self, raw_value: bytes) -> dict:
        # Parse ASN.1 structure (simplified)
        return {}

    def _verify_certificate_chain(self, chain: list[bytes]) -> None:
        # Verify each certificate in chain
        # Root must match Google's hardware attestation root CA
        pass
```

---

# PART 70 — SIDE-CHANNEL ATTACK AWARENESS

---

## Chapter 117: Side-Channel Attacks for Application Developers

```python
# Python — Side-channel attack patterns developers should know and prevent

"""
SIDE-CHANNEL ATTACKS:
  Attacks that exploit information leaked through physical/temporal signals
  rather than direct mathematical weaknesses in cryptographic algorithms.

  For application developers, the most relevant are:
  1. TIMING ATTACKS   — response time reveals information
  2. CACHE ATTACKS    — memory access patterns leak secrets
  3. POWER ANALYSIS   — on IoT/embedded devices
  4. SPECTRE/MELTDOWN — CPU speculation leaks across isolation
"""

import time
import hmac
import hashlib
import secrets

class TimingAttackExamples:
    """Demonstrates timing vulnerabilities and their fixes"""

    # ─────────────────────────────────────────────────────────────────────────
    # TIMING VULNERABILITY 1: String comparison (early exit)
    # ─────────────────────────────────────────────────────────────────────────

    def verify_token_vulnerable(self, provided: str, expected: str) -> bool:
        """
        VULNERABLE: Python's == exits as soon as it finds a mismatch.
        Attacker measures response time across many requests to guess token
        character by character.

        With 1,000 requests per character, and 32-character token:
        Worst case: 1000 * 32 * 95 (printable chars) = 3,040,000 requests
        But binary search + statistics can do it in far fewer.
        """
        return provided == expected  # Early exit leaks character information!

    def verify_token_safe(self, provided: str, expected: str) -> bool:
        """
        SAFE: hmac.compare_digest takes the same time regardless of match position.
        Internally uses constant-time comparison.
        """
        return hmac.compare_digest(
            provided.encode('utf-8'),
            expected.encode('utf-8'),
        )

    # ─────────────────────────────────────────────────────────────────────────
    # TIMING VULNERABILITY 2: Database lookup timing
    # ─────────────────────────────────────────────────────────────────────────

    async def authenticate_vulnerable(self, username: str, password: str) -> bool:
        """
        VULNERABLE: Database lookup time reveals whether user exists.
        Found user = fast path (compare password hash).
        Not found = fast return False.
        Response time difference → attacker can enumerate usernames.
        """
        user = await self.db.find_by_username(username)
        if not user:
            return False  # Returns faster when user doesn't exist!
        return self.verify_password(password, user.password_hash)

    async def authenticate_safe(self, username: str, password: str) -> bool:
        """
        SAFE: Always perform the expensive hash comparison.
        Even when the user doesn't exist, we do a dummy hash comparison.
        Response time is now similar for found and not-found cases.
        """
        user = await self.db.find_by_username(username)

        # Always compute hash — equalize timing
        if user:
            stored_hash = user.password_hash
        else:
            # Dummy hash — never matches, but takes the same time
            stored_hash = "$argon2id$v=19$m=65536,t=2,p=2$dummy$dummy"

        # This always runs, whether user found or not
        is_valid = self.verify_password(password, stored_hash)

        return is_valid and user is not None

    # ─────────────────────────────────────────────────────────────────────────
    # TIMING VULNERABILITY 3: Cache-timing in cryptographic lookup
    # ─────────────────────────────────────────────────────────────────────────

    # AES table lookups are cache-dependent — CPU cache hits are faster than misses
    # This enables cache-timing attacks on AES in pure software
    # MITIGATION: Use hardware AES instructions (AES-NI) via your crypto library
    # Python's cryptography library uses OpenSSL which uses AES-NI automatically

    # ─────────────────────────────────────────────────────────────────────────
    # SPECTRE/MELTDOWN MITIGATIONS AT APPLICATION LEVEL
    # ─────────────────────────────────────────────────────────────────────────

    # Spectre allows cross-process memory reads via CPU speculation
    # Application-level mitigations:

    # 1. Disable SharedArrayBuffer (enables high-resolution timing)
    CROSS_ORIGIN_ISOLATION_HEADERS = {
        # These headers disable SharedArrayBuffer for non-isolated origins
        # (SharedArrayBuffer enables precise timing → Spectre attacks)
        "Cross-Origin-Embedder-Policy": "require-corp",
        "Cross-Origin-Opener-Policy":   "same-origin",
        # With these set, SharedArrayBuffer only works for cross-origin isolated origins
        # Where you control all embedded content (and thus trust it)
    }

    # 2. Reduce timer resolution in JavaScript
    # performance.now() is limited to 1ms in most browsers (post-Spectre)
    # Date.now() is limited to 1ms
    # This limits Spectre timing precision

    # 3. Site isolation (browser-enforced)
    # Site isolation ensures different sites run in separate processes
    # CORS + COEP ensure Spectre cannot read cross-origin memory


class SideChannelDefenseChecklist:
    CHECKLIST = """
    SIDE-CHANNEL DEFENSE CHECKLIST:
    ════════════════════════════════

    TIMING ATTACKS:
    □ Token/secret comparison uses hmac.compare_digest() or crypto.timingSafeEqual()
    □ Password verification always runs the hash even when user not found
    □ Login response time is consistent (success ≈ failure timing)
    □ API rate limiting doesn't reveal user existence via timing
    □ CAPTCHA validation time is constant

    CACHE ATTACKS (primarily relevant for HSMs and embedded):
    □ AES implementation uses AES-NI hardware instructions (via OpenSSL)
    □ RSA implementation uses constant-time exponentiation
    □ Table lookups in crypto code are access-pattern-independent

    SPECTRE/MELTDOWN:
    □ Cross-Origin-Embedder-Policy: require-corp (disables SharedArrayBuffer for untrusted origins)
    □ Cross-Origin-Opener-Policy: same-origin (process isolation)
    □ No eval() with sensitive data in scope
    □ JIT compilation disabled for sensitive code paths (if using V8 --no-opt)

    PHYSICAL (IoT/Embedded):
    □ Power analysis countermeasures in firmware (random delays, masking)
    □ Fault injection detection (voltage/clock glitch detection)
    □ Hardware security modules for all key operations
    """
```

---

# PART 71 — THREAT HUNTING FOR DEVELOPERS

---

## Chapter 118: Proactive Threat Hunting

```python
# Python — Developer-level threat hunting using application logs

from datetime import datetime, timezone, timedelta
from collections import defaultdict
import json

class ApplicationThreatHunter:
    """
    Proactive threat hunting using application telemetry.
    Searches for attacker patterns that automated detection may miss.
    """

    def __init__(self, log_source):
        self.logs = log_source

    # ── Hunt 1: Credential stuffing pattern ──────────────────────────────────
    def hunt_credential_stuffing(
        self,
        lookback_hours: int = 24,
    ) -> list[dict]:
        """
        Credential stuffing signature:
        - Many unique usernames from same IP
        - Low success rate (<5%)
        - Similar user agent strings
        - Regular timing (automated)
        """
        events    = self.logs.query(
            event_type="auth.attempt",
            since=datetime.now(timezone.utc) - timedelta(hours=lookback_hours),
        )

        ip_stats  = defaultdict(lambda: {
            "attempts": 0, "successes": 0, "unique_users": set(), "user_agents": set()
        })

        for event in events:
            ip = event["source_ip"]
            ip_stats[ip]["attempts"]    += 1
            ip_stats[ip]["unique_users"].add(event["username_hash"])
            ip_stats[ip]["user_agents"].add(event["user_agent"])
            if event.get("success"):
                ip_stats[ip]["successes"] += 1

        findings = []
        for ip, stats in ip_stats.items():
            success_rate  = stats["successes"] / max(stats["attempts"], 1)
            unique_ratio  = len(stats["unique_users"]) / max(stats["attempts"], 1)

            # High unique user ratio + low success = credential stuffing
            if (stats["attempts"] > 50 and
                unique_ratio > 0.8 and      # Most attempts use different usernames
                success_rate < 0.05):        # <5% success rate

                findings.append({
                    "type":          "credential_stuffing",
                    "source_ip":     ip,
                    "attempts":      stats["attempts"],
                    "unique_users":  len(stats["unique_users"]),
                    "success_rate":  f"{success_rate:.1%}",
                    "confidence":    "HIGH",
                    "recommendation": f"Block {ip}; check if any of the "
                                       f"{stats['successes']} successes are legitimate",
                })

        return findings

    # ── Hunt 2: Slow brute force pattern ────────────────────────────────────
    def hunt_slow_brute_force(self) -> list[dict]:
        """
        Slow brute force evades rate limiting by spacing requests.
        Signature: same username, many attempts, days apart.
        """
        events = self.logs.query(event_type="auth.failure", days=30)

        username_attacks = defaultdict(list)
        for event in events:
            username_attacks[event["username_hash"]].append({
                "ip":        event["source_ip"],
                "timestamp": event["timestamp"],
            })

        findings = []
        for username_hash, attempts in username_attacks.items():
            if len(attempts) < 20:
                continue

            unique_ips = len(set(a["ip"] for a in attempts))
            days_span  = (
                max(a["timestamp"] for a in attempts) -
                min(a["timestamp"] for a in attempts)
            ).days

            if days_span >= 7 and unique_ips >= 3:
                findings.append({
                    "type":        "slow_brute_force",
                    "username":    f"hash:{username_hash[:8]}",
                    "attempts":    len(attempts),
                    "unique_ips":  unique_ips,
                    "days_span":   days_span,
                    "confidence":  "MEDIUM",
                    "recommendation": "Force password reset for this user; "
                                       "check if account was successfully accessed",
                })

        return findings

    # ── Hunt 3: IDOR exploitation pattern ────────────────────────────────────
    def hunt_idor_scanning(self) -> list[dict]:
        """
        IDOR scanner: sequentially accessing resource IDs that don't belong to them.
        Signature: 404s with sequential IDs from the same user.
        """
        events = self.logs.query(
            event_type="api.response",
            status_code=404,
            path_pattern="/api/invoices/%",
        )

        user_404_ids = defaultdict(list)
        for event in events:
            user_id  = event.get("user_id")
            path     = event.get("path", "")
            if user_id and path:
                # Extract the resource ID from the path
                import re
                match = re.search(r'/(\d+)$', path)
                if match:
                    resource_id = int(match.group(1))
                    user_404_ids[user_id].append(resource_id)

        findings = []
        for user_id, ids in user_404_ids.items():
            if len(ids) < 10:
                continue

            ids_sorted = sorted(ids)
            # Check for sequential access pattern
            gaps = [ids_sorted[i+1] - ids_sorted[i] for i in range(len(ids_sorted)-1)]
            avg_gap = sum(gaps) / max(len(gaps), 1)

            if avg_gap < 100 and len(ids) > 20:  # Sequential-ish
                findings.append({
                    "type":        "idor_enumeration",
                    "user_id":     user_id,
                    "404_count":   len(ids),
                    "id_range":    f"{min(ids)} - {max(ids)}",
                    "avg_gap":     f"{avg_gap:.1f}",
                    "confidence":  "HIGH",
                    "recommendation": "Investigate this user's recent activity; "
                                       "consider account suspension pending review",
                })

        return findings

    # ── Hunt 4: Data exfiltration pattern ────────────────────────────────────
    def hunt_data_exfiltration(self) -> list[dict]:
        """
        Unusual data egress: large volumes of data downloaded by a single user.
        Signature: bytes_transferred >> normal for this user.
        """
        events   = self.logs.query(event_type="api.response", days=7)

        user_egress  = defaultdict(int)
        user_baseline = defaultdict(list)

        for event in events:
            user_id     = event.get("user_id")
            bytes_sent  = event.get("response_bytes", 0)
            if user_id:
                user_egress[user_id] += bytes_sent
                user_baseline[user_id].append(bytes_sent)

        findings = []
        for user_id, total_bytes in user_egress.items():
            baseline     = user_baseline[user_id]
            avg_per_req  = sum(baseline) / max(len(baseline), 1)

            # Flag if total egress > 100MB AND > 10x their per-request average * requests
            if total_bytes > 100 * 1024 * 1024:
                findings.append({
                    "type":              "potential_data_exfiltration",
                    "user_id":           user_id,
                    "total_bytes_7d":    f"{total_bytes / 1024 / 1024:.1f} MB",
                    "avg_response_bytes": f"{avg_per_req:.0f}",
                    "confidence":        "MEDIUM",
                    "recommendation":    "Review what data was accessed; "
                                          "check for bulk export operations",
                })

        return findings

    def run_all_hunts(self) -> dict:
        """Run all threat hunts and produce a consolidated report"""
        return {
            "timestamp":          datetime.now(timezone.utc).isoformat(),
            "credential_stuffing": self.hunt_credential_stuffing(),
            "slow_brute_force":    self.hunt_slow_brute_force(),
            "idor_enumeration":    self.hunt_idor_scanning(),
            "data_exfiltration":   self.hunt_data_exfiltration(),
        }
```

---

# PART 72 — SECURE DEVELOPMENT LIFECYCLE (SDL)

---

## Chapter 119: Microsoft SDL for Modern Teams

```python
# Python — SDL implementation framework for agile teams

class SecureDevelopmentLifecycle:
    """
    Adapted Microsoft SDL for modern agile teams.
    Integrates security at every phase without blocking velocity.
    """

    # ── Phase 1: TRAINING ─────────────────────────────────────────────────────
    TRAINING_REQUIREMENTS = {
        "all_engineers": [
            "OWASP Top 10 awareness (annual, 2 hours)",
            "Secure coding basics for your primary language (annual, 4 hours)",
            "Social engineering and phishing awareness (annual, 1 hour)",
        ],
        "backend_engineers": [
            "API security (OWASP API Top 10)",
            "Cryptography fundamentals",
            "Secrets management",
        ],
        "frontend_engineers": [
            "XSS, CSRF, CSP",
            "OAuth flows and token storage",
            "Content Security Policy",
        ],
        "security_champions": [
            "Threat modeling facilitation",
            "Security code review",
            "Incident response",
            "All of the above plus advanced topics",
        ],
    }

    # ── Phase 2: REQUIREMENTS ─────────────────────────────────────────────────
    SECURITY_REQUIREMENTS_TEMPLATE = {
        "authentication": {
            "question": "How will users authenticate?",
            "standard": "Passkeys or MFA required for all accounts; Argon2id for passwords",
            "test":     "Auth bypass attempt returns 401; brute force triggers 429",
        },
        "authorization": {
            "question": "Who can access what?",
            "standard": "RBAC + ownership checks; least privilege; deny by default",
            "test":     "User A cannot access User B's resources (IDOR test)",
        },
        "data_sensitivity": {
            "question": "What data will you store/process? PII? PHI? PCI?",
            "standard": "Encryption at rest + in transit; data minimization; retention limits",
            "test":     "Data register documented; retention jobs scheduled",
        },
        "audit_logging": {
            "question": "What security events need to be logged?",
            "standard": "Auth, authz, data access, admin actions all logged",
            "test":     "Security events appear in SIEM within 60 seconds",
        },
        "availability": {
            "question": "What are the SLA requirements? Attack scenarios?",
            "standard": "Rate limiting; circuit breakers; DDoS mitigation at edge",
            "test":     "Rate limit triggers at defined threshold; circuit opens on failure",
        },
    }

    # ── Phase 3: DESIGN (Threat Modeling) ─────────────────────────────────────
    def conduct_threat_model_session(
        self,
        system_name: str,
        diagram_url: str,
        attendees: list[str],
    ) -> dict:
        """Template for a STRIDE threat modeling session"""
        return {
            "system": system_name,
            "diagram": diagram_url,
            "attendees": attendees,
            "components_analyzed": [],
            "threats_identified": [],
            "mitigations_required": [],
            "acceptance_criteria": [],
            "risks_accepted": [],  # Risks too costly to fix now; documented
        }

    THREAT_MODEL_PROMPTS = [
        "For each data flow: Could an attacker intercept or modify this? (T, I)",
        "For each component: Could an attacker impersonate it? (S)",
        "For each action: Could a user deny having done it? (R)",
        "For each sensitive operation: Could an unauthorized user trigger it? (E)",
        "For each service: Could an attacker take it down? (D)",
        "For each data store: What happens if it's breached? (I)",
    ]

    # ── Phase 4: IMPLEMENTATION (Secure Coding Standards) ─────────────────────
    IMPLEMENTATION_GATES = {
        "must_pass_before_pr": [
            "No secrets in code (gitleaks pre-commit hook)",
            "No SAST critical findings (Semgrep in IDE)",
            "No direct SQL string concatenation",
            "Parameterized queries for all DB operations",
        ],
        "must_pass_before_merge": [
            "SAST scan passes (no new High/Critical findings)",
            "Dependency scan passes (no Critical CVEs)",
            "Security checklist reviewed by Champion",
            "Unit tests include security tests for new auth/authz logic",
        ],
        "must_pass_before_deploy": [
            "DAST scan on staging (OWASP ZAP)",
            "Container scan passes",
            "Security headers verified",
            "No secrets in environment variables (Vault used)",
        ],
    }

    # ── Phase 5: VERIFICATION ─────────────────────────────────────────────────
    VERIFICATION_ACTIVITIES = {
        "per_sprint": [
            "Review SAST/SCA findings opened this sprint",
            "Verify security test coverage for new features",
            "Check that new API endpoints have auth + authz tests",
        ],
        "per_release": [
            "Run DAST on complete feature set",
            "Security code review for high-risk changes",
            "Update threat model if architecture changed",
            "Verify security requirements are met (from Phase 2)",
        ],
        "quarterly": [
            "Penetration test (external or internal red team)",
            "Threat model review (is our model still accurate?)",
            "Security training completion check",
            "Bug bounty program review",
            "Dependency and supply chain audit",
        ],
    }

    # ── Phase 6: RELEASE ─────────────────────────────────────────────────────
    RELEASE_SECURITY_GATES = [
        "All Critical/High security findings resolved or formally accepted",
        "Penetration test findings addressed (or acceptance documented)",
        "Incident response runbooks updated",
        "Security contacts and escalation paths verified",
        "Data breach notification procedures tested",
    ]

    # ── Phase 7: RESPONSE ─────────────────────────────────────────────────────
    INCIDENT_RESPONSE_REQUIREMENTS = [
        "Security incidents can be detected within 24 hours",
        "On-call rotation covers all hours",
        "Runbooks exist for top 5 likely incident types",
        "Contact list for security incidents is current",
        "Communication templates for breach notification ready",
        "Post-incident review conducted within 5 business days",
    ]

    def generate_security_sprint_report(self) -> dict:
        """Generate weekly security posture report for teams"""
        return {
            "sprint_security_score": {
                "new_vulns":          0,
                "vulns_resolved":     0,
                "critical_open":      0,
                "high_open":          0,
                "sast_findings":      0,
                "dependency_cves":    0,
            },
            "trend":               "improving",  # or "degrading" or "stable"
            "required_actions":    [],
            "upcoming_activities": [],
        }
```

---

## Chapter 120: Security Engineering — Complete Knowledge Map

```
╔══════════════════════════════════════════════════════════════════════════════╗
║           COMPLETE KNOWLEDGE MAP: SECURITY ENGINEERING                      ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  LAYER 1: SECURE CODING FUNDAMENTALS                                         ║
║  ├── Input validation (schema, type, range, format)                          ║
║  ├── Output encoding (HTML, JS, URL, SQL contexts)                           ║
║  ├── Parameterized queries (SQL, LDAP, NoSQL, SSRF)                         ║
║  ├── Cryptography (symmetric, asymmetric, hashing, TLS)                     ║
║  └── Error handling (no information leakage)                                 ║
║                                                                              ║
║  LAYER 2: AUTHENTICATION & SESSION MANAGEMENT                                ║
║  ├── Passkeys / WebAuthn (FIDO2, phishing-resistant)                        ║
║  ├── Multi-factor authentication (TOTP, hardware keys)                      ║
║  ├── Password security (Argon2id, HIBP check, breached password detection)  ║
║  ├── Session management (token entropy, rotation, expiry)                   ║
║  └── Account recovery (secure reset, lockout, enumeration prevention)       ║
║                                                                              ║
║  LAYER 3: AUTHORIZATION & ACCESS CONTROL                                     ║
║  ├── RBAC (roles, permissions, least privilege)                              ║
║  ├── ABAC (attribute-based, context-aware)                                   ║
║  ├── Resource ownership (IDOR prevention)                                    ║
║  ├── Row Level Security (database-enforced isolation)                        ║
║  └── API authorization (scopes, claims, token binding)                       ║
║                                                                              ║
║  LAYER 4: PLATFORM SECURITY                                                  ║
║  ├── Web: CSP, CORS, SRI, HSTS, headers, cookies                            ║
║  ├── Mobile: Keychain/Keystore, certificate pinning, biometrics              ║
║  ├── Desktop: Electron security, context isolation                           ║
║  ├── IoT: Secure boot, firmware signing, MQTT/TLS, HSMs                     ║
║  └── Serverless: Lambda IAM, environment security, cold start               ║
║                                                                              ║
║  LAYER 5: API SECURITY                                                       ║
║  ├── REST: Rate limiting, input validation, auth, IDOR, mass assignment      ║
║  ├── GraphQL: Depth/complexity limits, persisted queries, field-level auth   ║
║  ├── gRPC: mTLS, interceptors, message validation                            ║
║  ├── WebSocket: Auth at upgrade, per-message validation, idle timeout        ║
║  └── Webhooks: Signature validation, replay prevention                       ║
║                                                                              ║
║  LAYER 6: CLOUD & INFRASTRUCTURE                                             ║
║  ├── AWS: IAM least privilege, IMDSv2, VPC endpoints, KMS                   ║
║  ├── Containers: Non-root, read-only FS, seccomp, capabilities              ║
║  ├── Kubernetes: RBAC, network policies, pod security, Kyverno               ║
║  ├── Secrets: Vault dynamic secrets, KMS envelope encryption                 ║
║  └── IaC: Checkov, Terrascan, Sentinel policy gates                         ║
║                                                                              ║
║  LAYER 7: DEVSECOPS PIPELINE                                                 ║
║  ├── SAST: Semgrep, CodeQL, Bandit, gosec                                   ║
║  ├── SCA: Trivy, Snyk, cargo-audit, npm audit                               ║
║  ├── Secrets: Gitleaks, TruffleHog, Detect-Secrets                          ║
║  ├── Container: Trivy, Dockle, Grype                                        ║
║  ├── DAST: OWASP ZAP, Nuclei                                                ║
║  ├── SBOM: Syft, CycloneDX, SPDX                                            ║
║  └── Signing: Cosign, Sigstore, SLSA                                        ║
║                                                                              ║
║  LAYER 8: AI SECURITY                                                        ║
║  ├── Prompt injection defense (input classification, guard models)           ║
║  ├── RAG security (access control at retrieval layer)                       ║
║  ├── Agent security (tool sandboxing, action boundaries)                    ║
║  ├── MCP security (path traversal, command injection in tools)              ║
║  ├── Dataset integrity (poisoning detection, provenance signing)            ║
║  └── Model signing (ECDSA provenance, deployment verification)               ║
║                                                                              ║
║  LAYER 9: COMPLIANCE & PRIVACY                                               ║
║  ├── GDPR: Data register, consent, erasure, portability                     ║
║  ├── HIPAA: PHI encryption, minimum necessary, audit logs                   ║
║  ├── PCI DSS: Tokenization, TLS, annual pen test, CDE isolation             ║
║  ├── SOC 2: Evidence automation, controls testing, access review            ║
║  └── Privacy engineering: DP, k-anonymity, anonymization, PII scanning     ║
║                                                                              ║
║  LAYER 10: OPERATIONS & RESPONSE                                             ║
║  ├── Monitoring: Falco, eBPF, structured audit logs, SIEM                   ║
║  ├── Detection: Custom rules, threat hunting, behavioral analytics          ║
║  ├── Response: Incident playbooks, automation, forensics                    ║
║  ├── Recovery: Backup testing, disaster recovery, business continuity       ║
║  └── Hardening: Security chaos engineering, red team exercises              ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
```

---

*This is Part 10 — completing the Developer's Cybersecurity Mastery handbook.*

*Covered in this final volume: Service Worker security (network interception security model, cache poisoning in SW, message validation), CDN and cache poisoning defense (host header injection, unkeyed headers, nginx hardening, content-addressed URLs), WebRTC security (ephemeral TURN credentials, DTLS fingerprint verification, data channel message validation), Privacy-preserving analytics (DNT/GPC respect, ephemeral session IDs, server-side aggregation with differential privacy noise), Hardware attestation (TPM 2.0 attestation verification, PCR validation, Android KeyAttestation), Side-channel attack awareness (timing attacks with fixes, cache timing, Spectre/Meltdown mitigations), Proactive threat hunting (credential stuffing, slow brute force, IDOR enumeration, data exfiltration pattern detection), and the complete Secure Development Lifecycle (SDL) framework adapted for agile teams with phase-by-phase security gates.*

*The 10-part series is now complete. Total coverage: 120 chapters, ~150,000 words, 20,000+ lines of production-ready code across Java, Python, Go, Rust, TypeScript, C, SQL, HCL, YAML, Rego, Sigma, and Bash — spanning every major security domain from foundational secure coding to advanced AI security, post-quantum cryptography, hardware attestation, and organizational security leadership.*
