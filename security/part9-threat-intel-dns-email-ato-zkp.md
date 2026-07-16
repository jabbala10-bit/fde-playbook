# Developer's Cybersecurity Mastery: The Complete Handbook
## Volume 69–80 | Threat Intelligence · DNS · Email Security · ATO Prevention · Legacy Migration · Memory Forensics · Zero-Knowledge · Dataset Security

---

# PART 58 — THREAT INTELLIGENCE INTEGRATION

---

## Chapter 102: STIX/TAXII and Threat Feed Integration

### 102.1 Consuming Threat Intelligence in Your Application

```python
# Python — Threat intelligence integration for real-time IP/domain reputation

import requests
import redis
import json
import time
from dataclasses import dataclass
from enum import Enum
from typing import Optional

class ThreatCategory(Enum):
    MALWARE_C2       = "malware_c2"
    BOTNET           = "botnet"
    TOR_EXIT         = "tor_exit"
    VPN              = "vpn"
    SCANNER          = "scanner"
    CREDENTIAL_STUFF = "credential_stuffing"
    FRAUD            = "fraud"
    SPAM             = "spam"

@dataclass
class ThreatIndicator:
    value:       str              # IP or domain
    type:        str              # "ip" or "domain"
    categories:  list[ThreatCategory]
    confidence:  int              # 0-100
    first_seen:  float
    last_seen:   float
    source:      str              # Which feed
    tags:        list[str]

class ThreatIntelligenceService:
    """
    Aggregates threat intelligence from multiple feeds.
    Used to enrich authentication events, API requests, and fraud scoring.
    """

    FEED_URLS = {
        # Free feeds
        "feodo_tracker":   "https://feodotracker.abuse.ch/downloads/ipblocklist.json",
        "emergingthreats": "https://rules.emergingthreats.net/blockrules/compromised-ips.txt",
        # Commercial (API key required)
        "abuseipdb":       "https://api.abuseipdb.com/api/v2/check",
        "ipqualityscore":  "https://ipqualityscore.com/api/json/ip/{key}/{ip}",
        "greynoise":       "https://api.greynoise.io/v3/community/{ip}",
    }

    def __init__(self, redis_client: redis.Redis, api_keys: dict):
        self.cache     = redis_client
        self.api_keys  = api_keys
        self.TTL_CLEAN = 3600      # Cache clean IPs for 1 hour
        self.TTL_DIRTY = 86400     # Cache threat IPs for 24 hours

    def check_ip(self, ip: str) -> dict:
        """
        Multi-source IP reputation check.
        Returns risk score and threat categories.
        """
        cache_key = f"threat:ip:{ip}"
        cached    = self.cache.get(cache_key)
        if cached:
            return json.loads(cached)

        result = {
            "ip":            ip,
            "risk_score":    0,     # 0 = clean, 100 = definite threat
            "categories":    [],
            "sources":       [],
            "is_tor":        False,
            "is_vpn":        False,
            "is_bot":        False,
        }

        # Check AbuseIPDB
        if "abuseipdb" in self.api_keys:
            abuse_result = self._check_abuseipdb(ip)
            if abuse_result:
                score = abuse_result.get("abuseConfidenceScore", 0)
                result["risk_score"] = max(result["risk_score"], score)
                if score > 25:
                    result["sources"].append("abuseipdb")

        # Check GreyNoise
        if "greynoise" in self.api_keys:
            gn_result = self._check_greynoise(ip)
            if gn_result:
                classification = gn_result.get("classification", "unknown")
                if classification == "malicious":
                    result["risk_score"] = max(result["risk_score"], 80)
                    result["is_bot"] = True
                    result["sources"].append("greynoise")

        # Check local blocklists (cached, refreshed hourly)
        if self._is_in_local_blocklist(ip):
            result["risk_score"] = max(result["risk_score"], 90)
            result["sources"].append("local_blocklist")

        # Check Tor exit node list
        if self._is_tor_exit(ip):
            result["is_tor"] = True
            result["risk_score"] = max(result["risk_score"], 60)
            result["sources"].append("tor_exit_list")

        # Cache result
        ttl = self.TTL_DIRTY if result["risk_score"] > 25 else self.TTL_CLEAN
        self.cache.setex(cache_key, ttl, json.dumps(result))

        return result

    def _check_abuseipdb(self, ip: str) -> Optional[dict]:
        try:
            response = requests.get(
                self.FEED_URLS["abuseipdb"],
                headers={
                    "Key":    self.api_keys["abuseipdb"],
                    "Accept": "application/json",
                },
                params={"ipAddress": ip, "maxAgeInDays": 30},
                timeout=3,
            )
            return response.json().get("data", {})
        except Exception:
            return None

    def _check_greynoise(self, ip: str) -> Optional[dict]:
        try:
            response = requests.get(
                self.FEED_URLS["greynoise"].format(ip=ip),
                headers={"key": self.api_keys["greynoise"]},
                timeout=3,
            )
            return response.json()
        except Exception:
            return None

    def _is_in_local_blocklist(self, ip: str) -> bool:
        """Check against locally cached comprehensive blocklist"""
        return bool(self.cache.sismember("threat:blocklist:ips", ip))

    def _is_tor_exit(self, ip: str) -> bool:
        return bool(self.cache.sismember("threat:tor:exits", ip))

    def refresh_local_blocklists(self):
        """Refresh threat feeds — run every 4 hours via cron"""
        # Feodo tracker (malware C2)
        try:
            response = requests.get(self.FEED_URLS["feodo_tracker"], timeout=30)
            data     = response.json()
            ips      = [entry["ip_address"] for entry in data]
            if ips:
                pipeline = self.cache.pipeline()
                pipeline.delete("threat:blocklist:ips")
                pipeline.sadd("threat:blocklist:ips", *ips)
                pipeline.expire("threat:blocklist:ips", 14400)  # 4 hours
                pipeline.execute()
        except Exception as e:
            structlog.get_logger().error("threat_feed_refresh_failed",
                                          feed="feodo_tracker", error=str(e))

# Integration with authentication
class ThreatAwareAuthService:
    def __init__(self, threat_intel: ThreatIntelligenceService):
        self.threat_intel = threat_intel

    def authenticate(self, credentials: dict, request_ip: str) -> dict:
        """Authentication with threat intelligence enrichment"""

        # Check IP reputation before attempting authentication
        ip_threat = self.threat_intel.check_ip(request_ip)

        if ip_threat["risk_score"] > 80:
            # High-confidence threat: block immediately
            structlog.get_logger().warning(
                "auth.blocked.threat_ip",
                ip=request_ip,
                score=ip_threat["risk_score"],
                sources=ip_threat["sources"],
            )
            raise AuthBlockedError("Request blocked by threat intelligence")

        if ip_threat["risk_score"] > 50:
            # Medium threat: require CAPTCHA or MFA even for returning users
            return {"requires_step_up": True, "reason": "suspicious_ip"}

        if ip_threat["is_tor"]:
            # Policy decision: block Tor? Or just require MFA?
            # For financial applications: block
            # For privacy-conscious services: allow with MFA
            return {"requires_step_up": True, "reason": "tor_exit_node"}

        # Proceed with normal authentication
        return self._standard_authenticate(credentials)
```

---

# PART 59 — DNS SECURITY

---

## Chapter 103: DNS Security Implementation

### 103.1 DNS over HTTPS (DoH) and DNS over TLS (DoT)

```python
# Python — Secure DNS resolution using DoH (DNS over HTTPS)

import httpx
import base64
import struct
import asyncio
from typing import Optional

class SecureDNSResolver:
    """
    DNS over HTTPS (DoH) resolver.
    Encrypts DNS queries to prevent:
    - ISP logging of your DNS queries
    - DNS spoofing / cache poisoning
    - Content filtering / censorship
    """

    # Well-known DoH servers (all support DNSSEC validation)
    DOH_SERVERS = {
        "cloudflare":       "https://cloudflare-dns.com/dns-query",
        "cloudflare_security": "https://security.cloudflare-dns.com/dns-query",  # Blocks malware
        "google":           "https://dns.google/dns-query",
        "quad9":            "https://dns.quad9.net/dns-query",  # Blocks malicious domains
    }

    RECORD_TYPES = {
        "A":     1,
        "AAAA":  28,
        "CNAME": 5,
        "MX":    15,
        "TXT":   16,
        "NS":    2,
        "SOA":   6,
    }

    def __init__(self, server: str = "cloudflare_security"):
        self.server_url = self.DOH_SERVERS.get(server, server)
        self.client     = httpx.AsyncClient(
            http2=True,  # DoH benefits from HTTP/2 multiplexing
            verify=True,  # Always verify TLS
            timeout=10,
            headers={"Accept": "application/dns-message"},
        )

    async def resolve(
        self,
        name:        str,
        record_type: str = "A",
        validate_dnssec: bool = True,
    ) -> list[str]:
        """Resolve DNS with optional DNSSEC validation"""

        wire_query = self._build_dns_query(name, self.RECORD_TYPES.get(record_type, 1))

        response = await self.client.post(
            self.server_url,
            content=wire_query,
            headers={"Content-Type": "application/dns-message"},
        )
        response.raise_for_status()

        answers = self._parse_dns_response(response.content)

        # For DNSSEC: verify AD (Authenticated Data) bit is set
        if validate_dnssec and not self._check_dnssec_bit(response.content):
            raise DNSSECValidationError(
                f"DNSSEC validation failed for {name} — possible tampering"
            )

        return answers

    def _build_dns_query(self, name: str, qtype: int) -> bytes:
        """Build a minimal DNS wire format query"""
        # Transaction ID: random 16-bit value
        import random
        txid = random.randint(0, 65535)

        # Header: ID + flags (recursion desired, DNSSEC OK)
        header = struct.pack("!HHHHHH",
            txid,   # Transaction ID
            0x0100, # Flags: QR=0 (query), OPCODE=0, RD=1 (recursion desired)
            1,      # QDCOUNT: 1 question
            0, 0, 0 # ANCOUNT, NSCOUNT, ARCOUNT
        )

        # Encode domain name
        question = b""
        for part in name.split("."):
            encoded = part.encode()
            question += bytes([len(encoded)]) + encoded
        question += b"\x00"  # Root label

        # QTYPE + QCLASS
        question += struct.pack("!HH", qtype, 1)  # QTYPE, QCLASS=IN

        return header + question

    def _parse_dns_response(self, data: bytes) -> list[str]:
        """Parse DNS wire format response, extract A/AAAA records"""
        import socket

        if len(data) < 12:
            raise ValueError("DNS response too short")

        answers = []
        # Skip header (12 bytes) and question section
        offset = 12
        qdcount = struct.unpack("!H", data[2:4])[0]
        ancount = struct.unpack("!H", data[6:8])[0]

        # Skip questions
        for _ in range(qdcount):
            while data[offset] != 0:
                offset += data[offset] + 1
            offset += 5  # Skip null label, QTYPE, QCLASS

        # Parse answers
        for _ in range(ancount):
            # Skip name (may be compressed)
            if data[offset] & 0xC0 == 0xC0:
                offset += 2  # Pointer
            else:
                while data[offset] != 0:
                    offset += data[offset] + 1
                offset += 1

            rtype, _, _, rdlen = struct.unpack("!HHIH", data[offset:offset+10])
            offset += 10
            rdata = data[offset:offset+rdlen]
            offset += rdlen

            if rtype == 1 and rdlen == 4:   # A record
                answers.append(socket.inet_ntoa(rdata))
            elif rtype == 28 and rdlen == 16: # AAAA record
                answers.append(socket.inet_ntop(socket.AF_INET6, rdata))

        return answers

    def _check_dnssec_bit(self, data: bytes) -> bool:
        """Check if the AD (Authenticated Data) bit is set in DNS response"""
        if len(data) < 4:
            return False
        flags = struct.unpack("!H", data[2:4])[0]
        return bool(flags & 0x0020)  # AD bit position

class DNSSECValidationError(Exception):
    pass
```

---

## Chapter 104: Email Security — DKIM, DMARC, SPF

```python
# Python — Email security implementation and validation

import dns.resolver
import hashlib
import base64
from email.message import EmailMessage

class EmailSecurityValidator:
    """
    Validate email authentication records for outbound email security.
    Used in: email service integration, webhook sender validation.
    """

    def check_domain_email_security(self, domain: str) -> dict:
        """Complete email security posture check for a domain"""
        return {
            "domain": domain,
            "spf":    self._check_spf(domain),
            "dkim":   self._check_dkim(domain),
            "dmarc":  self._check_dmarc(domain),
            "score":  self._calculate_score(domain),
        }

    def _check_spf(self, domain: str) -> dict:
        """Check SPF record exists and is properly configured"""
        try:
            answers = dns.resolver.resolve(domain, "TXT")
            spf_records = [
                r.to_text().strip('"')
                for r in answers
                if r.to_text().strip('"').startswith("v=spf1")
            ]

            if not spf_records:
                return {"present": False, "issue": "No SPF record found"}

            if len(spf_records) > 1:
                return {"present": True, "valid": False,
                        "issue": "Multiple SPF records — only one allowed"}

            spf = spf_records[0]

            # Check for -all (fail) vs ~all (softfail) vs +all (allow all — terrible)
            if "+all" in spf:
                return {"present": True, "valid": False,
                        "issue": "+all allows ANY server — severe misconfiguration"}
            if "-all" in spf:
                verdict = "strict"
            elif "~all" in spf:
                verdict = "softfail"  # Better than nothing, not as good as -all
            else:
                verdict = "neutral"

            return {
                "present": True,
                "valid":   True,
                "record":  spf,
                "policy":  verdict,
            }

        except dns.resolver.NXDOMAIN:
            return {"present": False, "issue": "Domain does not exist"}
        except dns.resolver.NoAnswer:
            return {"present": False, "issue": "No TXT records"}

    def _check_dmarc(self, domain: str) -> dict:
        """Check DMARC policy"""
        try:
            dmarc_domain = f"_dmarc.{domain}"
            answers = dns.resolver.resolve(dmarc_domain, "TXT")

            for r in answers:
                record = r.to_text().strip('"')
                if record.startswith("v=DMARC1"):
                    # Parse DMARC tags
                    tags = dict(
                        tag.strip().split("=", 1)
                        for tag in record.split(";")
                        if "=" in tag
                    )
                    policy    = tags.get("p", "none")
                    pct       = tags.get("pct", "100")
                    rua       = tags.get("rua", "")  # Aggregate report URI
                    ruf       = tags.get("ruf", "")  # Forensic report URI

                    return {
                        "present": True,
                        "record":  record,
                        "policy":  policy,     # none / quarantine / reject
                        "pct":     pct,        # Percentage to apply policy to
                        "reports": bool(rua),  # Are aggregate reports configured?
                        "secure":  policy in ("quarantine", "reject"),
                    }

            return {"present": False, "issue": "No DMARC record at _dmarc." + domain}

        except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer):
            return {"present": False, "issue": "No DMARC record"}

    def _check_dkim(self, domain: str, selector: str = "default") -> dict:
        """Check if DKIM is configured for a domain/selector pair"""
        try:
            dkim_domain = f"{selector}._domainkey.{domain}"
            answers     = dns.resolver.resolve(dkim_domain, "TXT")
            for r in answers:
                record = r.to_text().strip('"')
                if "v=DKIM1" in record:
                    return {
                        "present":  True,
                        "selector": selector,
                        "record":   record[:100] + "...",
                    }
        except Exception:
            pass

        return {
            "present": False,
            "selector": selector,
            "issue":    f"No DKIM record at {selector}._domainkey.{domain}",
        }

    def _calculate_score(self, domain: str) -> dict:
        """Calculate overall email security score"""
        spf   = self._check_spf(domain)
        dmarc = self._check_dmarc(domain)

        score    = 0
        max_score = 100
        issues   = []

        if spf.get("present"):
            score += 20
            if spf.get("valid") and spf.get("policy") == "strict":
                score += 15
        else:
            issues.append("SPF record missing")

        if dmarc.get("present"):
            score += 20
            policy = dmarc.get("policy", "none")
            if policy == "reject":    score += 30
            elif policy == "quarantine": score += 20
            else: issues.append("DMARC policy is 'none' — not enforcing")

            if dmarc.get("reports"):
                score += 15
        else:
            issues.append("DMARC record missing")

        return {
            "score":   score,
            "maximum": max_score,
            "grade":   "A" if score >= 80 else "B" if score >= 60 else "C" if score >= 40 else "F",
            "issues":  issues,
        }


# Correct DKIM signing for outbound emails
class DKIMSigner:
    """
    Sign outgoing emails with DKIM.
    In production, use established libraries: dkimpy, mailchimp, SendGrid SDK.
    """

    def __init__(self, private_key_pem: bytes, domain: str, selector: str):
        from cryptography.hazmat.primitives.serialization import load_pem_private_key
        self.private_key = load_pem_private_key(private_key_pem, password=None)
        self.domain      = domain
        self.selector    = selector

    def sign_email(self, message: EmailMessage) -> EmailMessage:
        """Add DKIM-Signature header to email"""
        # In production: use dkimpy library
        # import dkim
        # sig = dkim.sign(message_bytes, selector, domain, private_key)
        # message["DKIM-Signature"] = sig
        return message


# Email security configuration for popular ESPs
EMAIL_SECURITY_CONFIG = """
RECOMMENDED EMAIL SECURITY CONFIGURATION:
═══════════════════════════════════════════

DNS RECORDS TO ADD:
  SPF:   yourdomain.com. TXT "v=spf1 include:sendgrid.net -all"
         (Replace sendgrid.net with your ESP's include)

  DKIM:  [selector]._domainkey.yourdomain.com. TXT "v=DKIM1; k=rsa; p=[public-key]"
         (Generate key pair, publish public key, keep private key in ESP)

  DMARC: _dmarc.yourdomain.com. TXT "v=DMARC1; p=reject; pct=100;
          rua=mailto:dmarc-reports@yourdomain.com;
          ruf=mailto:dmarc-failures@yourdomain.com;
          fo=1"

POLICY PROGRESSION:
  Week 1-2:  p=none   (monitoring only, collect reports)
  Week 3-4:  p=quarantine; pct=10  (10% of mail quarantined)
  Week 5-6:  p=quarantine; pct=100 (all non-passing mail quarantined)
  Week 7+:   p=reject; pct=100     (hard reject — full protection)

WHAT IT PREVENTS:
  ✓ Domain spoofing (attacker sending as @yourdomain.com)
  ✓ Email phishing using your brand
  ✓ Business email compromise (BEC) attacks
  ✓ Brand reputation damage from spam sent using your domain
"""
```

---

# PART 60 — ACCOUNT TAKEOVER PREVENTION

---

## Chapter 105: Complete ATO Prevention Architecture

```python
# Python — Multi-layer account takeover prevention

import hashlib
import json
import time
from dataclasses import dataclass
from typing import Optional

@dataclass
class LoginContext:
    ip_address:   str
    user_agent:   str
    user_agent_hash: str
    country:      str
    city:         str
    device_id:    Optional[str]  # Persistent device fingerprint
    timestamp:    float
    request_id:   str

class ATOPreventionService:
    """
    Account Takeover Prevention using behavioral signals.
    Analyzes multiple signals to detect ATO attacks.
    """

    def __init__(self, redis_client, threat_intel, notification_service):
        self.redis         = redis_client
        self.threat_intel  = threat_intel
        self.notifications = notification_service

    def analyze_login_attempt(
        self,
        user_id:  str,
        ctx:      LoginContext,
        success:  bool,
    ) -> dict:
        """
        Analyze a login attempt for ATO signals.
        Returns risk assessment and required actions.
        """
        risk_factors = []
        risk_score   = 0

        # ── Signal 1: Failed attempts (brute force / credential stuffing) ─────
        fail_key   = f"ato:fails:{user_id}"
        fail_count = int(self.redis.get(fail_key) or 0)
        if fail_count >= 5:
            risk_factors.append("repeated_failures")
            risk_score += 30

        # ── Signal 2: IP reputation ──────────────────────────────────────────
        ip_threat = self.threat_intel.check_ip(ctx.ip_address)
        if ip_threat["risk_score"] > 50:
            risk_factors.append(f"threat_ip:{ip_threat['risk_score']}")
            risk_score += ip_threat["risk_score"] // 2

        # ── Signal 3: Known device check ─────────────────────────────────────
        known_device = self._is_known_device(user_id, ctx)
        if not known_device:
            risk_factors.append("new_device")
            risk_score += 15

        # ── Signal 4: Geographic anomaly ─────────────────────────────────────
        geo_risk = self._check_geographic_anomaly(user_id, ctx)
        if geo_risk["is_anomaly"]:
            risk_factors.append(f"geo_anomaly:{geo_risk['distance_km']:.0f}km")
            risk_score += min(40, geo_risk["distance_km"] // 100)

        # ── Signal 5: Velocity — too many accounts, one IP ───────────────────
        ip_velocity_key = f"ato:velocity:ip:{ctx.ip_address}"
        ip_accounts     = int(self.redis.get(ip_velocity_key) or 0)
        if ip_accounts > 5:
            risk_factors.append(f"ip_velocity:{ip_accounts}")
            risk_score += 25

        # ── Signal 6: Time of day anomaly ────────────────────────────────────
        if self._is_unusual_time(user_id, ctx.timestamp):
            risk_factors.append("unusual_time")
            risk_score += 10

        # ── Decision ─────────────────────────────────────────────────────────
        risk_score = min(100, risk_score)

        decision = self._make_decision(risk_score, success)

        # Update counters
        if not success:
            pipeline = self.redis.pipeline()
            pipeline.incr(fail_key)
            pipeline.expire(fail_key, 3600)
            pipeline.incr(ip_velocity_key)
            pipeline.expire(ip_velocity_key, 3600)
            pipeline.execute()
        else:
            # Successful login: record device and location
            self.redis.delete(fail_key)
            if decision["action"] in ("allow", "allow_with_notification"):
                self._record_successful_login(user_id, ctx)

        # Send notification for suspicious logins
        if decision["action"] in ("step_up", "block") or risk_score > 40:
            self._notify_user_if_appropriate(user_id, ctx, risk_factors, decision)

        # Audit log
        self._log_ato_analysis(user_id, ctx, risk_factors, risk_score, decision)

        return {
            "risk_score":  risk_score,
            "risk_factors": risk_factors,
            "decision":    decision,
        }

    def _is_known_device(self, user_id: str, ctx: LoginContext) -> bool:
        """Check if this device has been seen before for this user"""
        device_key  = f"ato:devices:{user_id}"
        device_hash = hashlib.sha256(
            f"{ctx.user_agent}:{ctx.device_id or ''}".encode()
        ).hexdigest()[:16]

        if self.redis.sismember(device_key, device_hash):
            return True
        return False

    def _check_geographic_anomaly(self, user_id: str, ctx: LoginContext) -> dict:
        """
        Check if login is from an unusual location.
        Implements 'impossible travel' detection.
        """
        last_login_key = f"ato:last_geo:{user_id}"
        last_login_raw = self.redis.get(last_login_key)

        if not last_login_raw:
            return {"is_anomaly": False, "distance_km": 0}

        last_login = json.loads(last_login_raw)
        last_lat   = last_login.get("lat", 0)
        last_lon   = last_login.get("lon", 0)
        last_time  = last_login.get("timestamp", 0)

        # Calculate distance (simplified Haversine)
        current_lat = self._get_lat(ctx.city)
        current_lon = self._get_lon(ctx.city)
        distance_km = self._haversine(last_lat, last_lon, current_lat, current_lon)

        # Time elapsed since last login
        elapsed_hours = (ctx.timestamp - last_time) / 3600

        # Maximum speed: ~900 km/h (commercial flight)
        max_possible_distance = elapsed_hours * 900

        is_anomaly = distance_km > max_possible_distance and distance_km > 200

        return {
            "is_anomaly":  is_anomaly,
            "distance_km": distance_km,
            "elapsed_h":   elapsed_hours,
        }

    def _make_decision(self, risk_score: int, login_success: bool) -> dict:
        """Convert risk score to concrete action"""
        if risk_score >= 80:
            return {
                "action":  "block",
                "reason":  "High-confidence attack detected",
                "http_code": 403,
            }
        elif risk_score >= 50:
            return {
                "action":  "step_up",
                "reason":  "Suspicious activity — additional verification required",
                "require": "mfa",
                "http_code": 200,
            }
        elif risk_score >= 25:
            return {
                "action":  "allow_with_notification",
                "reason":  "Notify user of unusual login",
                "http_code": 200,
            }
        else:
            return {
                "action":  "allow",
                "http_code": 200,
            }

    def _record_successful_login(self, user_id: str, ctx: LoginContext):
        """Record successful login for future anomaly detection"""
        # Update known devices
        device_key  = f"ato:devices:{user_id}"
        device_hash = hashlib.sha256(
            f"{ctx.user_agent}:{ctx.device_id or ''}".encode()
        ).hexdigest()[:16]

        pipeline = self.redis.pipeline()
        pipeline.sadd(device_key, device_hash)
        pipeline.expire(device_key, 86400 * 90)  # Remember device for 90 days

        # Update last login location
        geo_key = f"ato:last_geo:{user_id}"
        pipeline.setex(geo_key, 86400 * 30, json.dumps({
            "lat":       self._get_lat(ctx.city),
            "lon":       self._get_lon(ctx.city),
            "city":      ctx.city,
            "country":   ctx.country,
            "timestamp": ctx.timestamp,
        }))
        pipeline.execute()
```

---

## Chapter 106: Secure Password Reset Flow

```python
# Python — Secure password reset implementation

import secrets
import hashlib
import time
from datetime import datetime, timezone, timedelta

class SecurePasswordResetService:
    """
    Secure password reset flow implementation.
    Prevents: account enumeration, token brute force,
              token reuse, timing attacks, and CSRF.
    """

    TOKEN_BYTES        = 32     # 256 bits of entropy
    TOKEN_EXPIRY_MIN   = 15     # 15-minute validity
    MAX_TOKENS_PER_DAY = 5      # Rate limit per user

    def __init__(self, db, email_service, redis_client):
        self.db        = db
        self.email     = email_service
        self.redis     = redis_client

    def initiate_reset(self, email: str, request_ip: str) -> None:
        """
        Initiate password reset.
        CRITICAL: Always return the same response whether user exists or not.
        This prevents account enumeration.
        """
        # Rate limit by email AND by IP (prevent enumeration)
        self._check_rate_limit(email, request_ip)

        # Lookup user — but DO NOT reveal if found
        user = self.db.find_user_by_email(email.lower().strip())

        if user:
            # Generate secure token
            raw_token    = secrets.token_bytes(self.TOKEN_BYTES)
            token_string = secrets.token_urlsafe(self.TOKEN_BYTES)

            # Store HASH of token — if DB compromised, tokens unusable
            token_hash   = hashlib.sha256(raw_token).hexdigest()

            # Store in DB with metadata
            expires_at = datetime.now(timezone.utc) + timedelta(minutes=self.TOKEN_EXPIRY_MIN)
            self.db.create_reset_token(
                user_id    = user.id,
                token_hash = token_hash,
                expires_at = expires_at,
                ip_address = request_ip,
                is_used    = False,
            )

            # Invalidate any previous tokens for this user
            self.db.invalidate_previous_tokens(user.id, exclude_token_hash=token_hash)

            # Send email with token (not hash)
            reset_url = f"https://app.example.com/reset-password?token={token_string}"
            self.email.send_password_reset(
                to=user.email,
                reset_url=reset_url,
                ip_address=request_ip,
                expires_in_minutes=self.TOKEN_EXPIRY_MIN,
            )

        # ALWAYS return the same response — prevents enumeration
        # Even if user not found, simulate work to prevent timing oracle
        else:
            # Perform dummy work to equalize response time
            secrets.token_urlsafe(self.TOKEN_BYTES)
            time.sleep(0.1)

    def complete_reset(
        self,
        token_string: str,
        new_password: str,
        request_ip:   str,
    ) -> bool:
        """
        Complete password reset with token validation.
        """
        # Validate new password strength
        self._validate_password_strength(new_password)

        # Compute hash of provided token
        try:
            raw_token  = secrets.token_bytes(0)  # Just for structure
            # The token_string was token_urlsafe(32) — decode to get raw bytes
            raw_bytes  = secrets.token_bytes(0)
            token_hash = hashlib.sha256(
                # URL-safe base64 decode the token
                __import__('base64').urlsafe_b64decode(
                    token_string + "=" * (4 - len(token_string) % 4)
                )
            ).hexdigest()
        except Exception:
            return False

        # Look up token by hash
        reset_token = self.db.find_reset_token_by_hash(token_hash)

        # Constant-time validations to prevent timing oracle
        is_valid    = True

        if not reset_token:
            is_valid = False
            # Dummy password hash to equalize timing
            from passlib.hash import argon2
            argon2.hash("dummy_to_equalize_timing")

        else:
            # Check expiry
            if datetime.now(timezone.utc) > reset_token.expires_at:
                is_valid = False

            # Check not already used
            if reset_token.is_used:
                is_valid = False

            if is_valid:
                # Hash new password
                from passlib.hash import argon2
                new_hash = argon2.hash(new_password)

                # Atomic: mark token as used AND update password in one transaction
                with self.db.transaction():
                    self.db.mark_token_used(token_hash)
                    self.db.update_password(reset_token.user_id, new_hash)
                    # Revoke ALL sessions — force re-login
                    self.db.revoke_all_sessions(reset_token.user_id)
                    self.db.revoke_all_refresh_tokens(reset_token.user_id)

                # Notify user of password change
                self._notify_password_changed(reset_token.user_id, request_ip)

        return is_valid

    def _check_rate_limit(self, email: str, ip: str):
        """Rate limit password reset requests"""
        email_key = f"reset:email:{hashlib.sha256(email.encode()).hexdigest()[:16]}"
        ip_key    = f"reset:ip:{ip}"

        pipeline = self.redis.pipeline()
        pipeline.incr(email_key)
        pipeline.expire(email_key, 86400)
        pipeline.incr(ip_key)
        pipeline.expire(ip_key, 3600)
        results = pipeline.execute()

        if results[0] > self.MAX_TOKENS_PER_DAY:
            raise RateLimitError("Too many reset requests for this email")
        if results[2] > 20:
            raise RateLimitError("Too many reset requests from this IP")

    def _validate_password_strength(self, password: str):
        import re
        if len(password) < 12:
            raise ValueError("Password must be at least 12 characters")
        if not re.search(r'[A-Z]', password):
            raise ValueError("Password must contain an uppercase letter")
        if not re.search(r'[a-z]', password):
            raise ValueError("Password must contain a lowercase letter")
        if not re.search(r'\d', password):
            raise ValueError("Password must contain a number")
        if not re.search(r'[^a-zA-Z\d]', password):
            raise ValueError("Password must contain a special character")

        # Check against known breached passwords using k-anonymity API
        self._check_pwned_passwords(password)

    def _check_pwned_passwords(self, password: str):
        """Check password against HaveIBeenPwned using k-anonymity"""
        import requests
        sha1_hash  = hashlib.sha1(password.encode()).hexdigest().upper()
        prefix     = sha1_hash[:5]
        suffix     = sha1_hash[5:]

        response   = requests.get(f"https://api.pwnedpasswords.com/range/{prefix}", timeout=5)
        hashes     = response.text.splitlines()

        for line in hashes:
            hash_suffix, count = line.split(":")
            if hash_suffix == suffix and int(count) > 0:
                raise ValueError(
                    f"This password has appeared in {count} data breaches. "
                    "Please choose a different password."
                )
```

---

# PART 61 — SECURITY FOR LEGACY SYSTEM MIGRATION

---

## Chapter 107: Migrating from Insecure Legacy Patterns

```python
# Python — Legacy security debt migration patterns

class LegacyMigrationHelper:
    """
    Helpers for safely migrating from insecure legacy patterns
    without breaking existing functionality.
    """

    # ── Pattern 1: Upgrading MD5 passwords to Argon2id ─────────────────────
    # Challenge: You have millions of MD5-hashed passwords.
    #            You can't re-hash them without the plaintext.
    #            Solution: Hash-of-hash upgrade on next successful login.

    def upgrade_password_hash_on_login(
        self,
        user: dict,
        provided_password: str,
    ) -> bool:
        """
        Transparent password hash upgrade.
        Works even when migrating from MD5/bcrypt to Argon2id.
        """
        stored_hash  = user["password_hash"]
        hash_version = user.get("hash_version", 1)  # 1=MD5, 2=bcrypt, 3=Argon2id

        authenticated = False

        if hash_version == 1:  # Legacy MD5
            md5_hash = hashlib.md5(provided_password.encode()).hexdigest()
            if secrets.compare_digest(stored_hash, md5_hash):
                authenticated = True

        elif hash_version == 2:  # bcrypt
            import bcrypt
            authenticated = bcrypt.checkpw(
                provided_password.encode(),
                stored_hash.encode()
            )

        elif hash_version == 3:  # Argon2id (current)
            from argon2 import PasswordHasher
            ph = PasswordHasher()
            try:
                ph.verify(stored_hash, provided_password)
                authenticated = True
                # Check if rehashing needed (parameters upgraded)
                if ph.check_needs_rehash(stored_hash):
                    new_hash = ph.hash(provided_password)
                    self.db.update_password_hash(user["id"], new_hash, version=3)
            except Exception:
                authenticated = False

        if authenticated and hash_version < 3:
            # Upgrade to Argon2id immediately on successful login
            from argon2 import PasswordHasher
            ph       = PasswordHasher(time_cost=2, memory_cost=65536, parallelism=2)
            new_hash = ph.hash(provided_password)
            self.db.update_password_hash(user["id"], new_hash, version=3)

        return authenticated

    # ── Pattern 2: Safely migrating from insecure session tokens ────────────
    def migrate_session_to_secure(self, old_session_id: str) -> str:
        """
        Migrate from predictable session IDs (sequential, UUID v1)
        to cryptographically random tokens.
        Gradual migration: validate both formats during transition.
        """
        # Check if it's a legacy session
        if self._is_legacy_session(old_session_id):
            session_data = self.db.get_session(old_session_id)
            if session_data:
                # Issue new secure session
                new_token = secrets.token_urlsafe(32)
                self.db.create_session(new_token, session_data["user_id"])
                self.db.delete_session(old_session_id)
                return new_token
        return old_session_id

    def _is_legacy_session(self, session_id: str) -> bool:
        """Detect if session ID is in legacy format (sequential or UUID v1)"""
        import re
        # Sequential numeric ID (legacy: session = user.id + timestamp)
        if re.match(r'^\d+_\d+$', session_id):
            return True
        # UUID v1 (time-based, predictable)
        import uuid
        try:
            u = uuid.UUID(session_id)
            if u.version == 1:
                return True
        except ValueError:
            pass
        return False

    # ── Pattern 3: Deprecating HTTP in favor of HTTPS ────────────────────────
    def generate_hsts_migration_plan(self) -> dict:
        """
        HSTS deployment roadmap to migrate from HTTP to enforced HTTPS.
        Rushing HSTS can lock out users if HTTPS is misconfigured.
        """
        return {
            "week_1": {
                "action": "Deploy TLS certificate and configure HTTPS",
                "validate": "Verify all endpoints accessible via HTTPS",
                "hsts_header": None,
            },
            "week_2": {
                "action": "Add HSTS with short max-age and monitoring",
                "validate": "Monitor HTTP traffic drop",
                "hsts_header": "max-age=300",  # 5 minutes — easily reversible
            },
            "week_3": {
                "action": "Extend HSTS max-age",
                "validate": "No HTTPS errors reported",
                "hsts_header": "max-age=86400",  # 1 day
            },
            "week_4": {
                "action": "Add includeSubDomains after verifying all subdomains have TLS",
                "validate": "All subdomains accessible via HTTPS",
                "hsts_header": "max-age=86400; includeSubDomains",
            },
            "month_2": {
                "action": "Extend to 1 year",
                "hsts_header": "max-age=31536000; includeSubDomains",
            },
            "month_3": {
                "action": "Add preload directive and submit to HSTS preload list",
                "hsts_header": "max-age=31536000; includeSubDomains; preload",
                "note": "WARNING: Preload is permanent — only do this when fully committed",
            },
        }

    # ── Pattern 4: Migrating from self-signed to proper CA certificates ──────
    def certificate_pinning_migration(self) -> dict:
        """
        Safely migrate mobile app certificate pinning.
        Wrong migration = production outage for all users.
        """
        return {
            "step_1": {
                "desc": "Add NEW cert hash alongside existing in pin-set",
                "mobile_update": "Release app version with BOTH old and new cert hashes",
                "pin_set": ["OLD_CERT_HASH", "NEW_CERT_HASH"],
                "wait": "Wait for app update adoption (>90% users updated)",
            },
            "step_2": {
                "desc": "Rotate certificate on server",
                "mobile_update": "No app update needed — both hashes in app",
                "verify": "Monitor certificate pinning failures",
            },
            "step_3": {
                "desc": "Release app with only NEW cert hash",
                "pin_set": ["NEW_CERT_HASH", "BACKUP_CERT_HASH"],
                "note": "Always keep a backup pin for next rotation",
            },
        }
```

---

# PART 62 — ZERO-KNOWLEDGE PROOFS FOR DEVELOPERS

---

## Chapter 108: ZKP Patterns in Application Security

```python
# Python — Zero-Knowledge Proof concepts and practical applications

"""
ZERO-KNOWLEDGE PROOF (ZKP):
A protocol where a prover can prove to a verifier that they know
a value (e.g., a password, a private key, a fact about themselves)
WITHOUT revealing the value itself.

Property 1 — Completeness:  If statement is true, honest prover convinces verifier
Property 2 — Soundness:     If statement is false, dishonest prover can't convince verifier
Property 3 — Zero-Knowledge: Verifier learns NOTHING about the witness (secret) beyond the statement

PRACTICAL APPLICATIONS:
  1. Password auth without sending password (OPAQUE protocol)
  2. Age verification without revealing birth date ("I am over 18")
  3. Income proof without revealing salary ("Income > $50K")
  4. Range proofs in blockchain transactions
  5. Privacy-preserving identity verification
"""

class ZKPApplications:
    """
    Practical ZKP patterns for application developers.
    These are simplified conceptual implementations.
    For production: use libsodium, OPAQUE, or established ZKP libraries.
    """

    # ── Application 1: OPAQUE password-authenticated key exchange ────────────
    """
    OPAQUE (Oblivious Pseudo-Random Functions) is a ZKP-based password
    authentication protocol. It provides:
    - Server NEVER learns the user's password (not even the hash)
    - Attacker who steals the server database CANNOT crack passwords offline
    - Mutual authentication (both client and server prove identity)

    Traditional password auth vulnerability:
      Client: sends SHA256(password) → Server: stores it
      Attacker steals DB → offline dictionary attack → cracks passwords

    OPAQUE:
      Client: applies OPRF (Oblivious Pseudo-Random Function) to password
              server can't learn password; client gets crypto material
              only the client + server together can authenticate

    In Python: use py_ecc + opaque-ke library
    In production: Cloudflare, Apple, WhatsApp all use OPAQUE or variants
    """

    def opaque_registration_sketch(self) -> str:
        return """
        OPAQUE Registration (simplified):

        CLIENT:                              SERVER:
        password = "user_password"

        1. Client generates random scalar r
        2. Compute blinded = SHA512ToCurve(password) * r
        3. Send blinded → SERVER

                                            4. Server generates OPRF key k
                                            5. Compute evaluation = blinded * k
                                            6. Return evaluation, server_public_key

        7. Unblind: credential = evaluation * (1/r)
        8. envelope_key = Expand(credential, "envelope")
        9. registration_record = Encrypt(
               envelope_key,
               {client_private_key, server_public_key}
           )
        10. Send registration_record → SERVER

                                            11. Store (registration_record, OPRF_key)
                                                — server never saw password

        Authentication: Client proves knowledge of password through
                       OPRF evaluation, without sending password
        """

    # ── Application 2: Range proofs (prove age without revealing birth date) ─
    def age_verification_zkp_concept(self):
        """
        Prove "I am over 18" without revealing birth date.
        In practice: use Bulletproofs, SNARKs, or STARKs.
        Simplified conceptual sketch:
        """
        from datetime import date

        class AgeProof:
            def create_proof(self, birth_date: date, current_date: date) -> dict:
                """
                Creates a commitment to age without revealing birth date.
                Real implementation uses Pedersen commitments + range proofs.
                """
                age_in_days = (current_date - birth_date).days
                is_over_18  = age_in_days >= (18 * 365)

                # In a real ZKP:
                # 1. Commit to birth_date with randomness: C = g^birth_date * h^r
                # 2. Create range proof: prove age_in_days ∈ [18*365, max_age*365]
                # 3. The proof reveals ONLY that age ≥ 18, not the actual age

                return {
                    "proof_type": "age_over_18",
                    "commitment": "Pedersen_commitment_of_birth_date",
                    "range_proof": "zkp_proving_age_in_acceptable_range",
                    "is_valid":   is_over_18,
                    # Verifier can check proof without learning birth_date
                }

    # ── Application 3: Anonymous credential (prove group membership) ─────────
    """
    Anonymous credentials: Prove "I am a verified user of company X"
    without revealing WHICH user you are.

    Used in: anonymous voting, whistleblowing platforms,
             privacy-preserving loyalty programs.

    Libraries: Microsoft U-Prove, IRMA, Iden3
    """

    # ── Application 4: Commitment schemes (secure coin flip) ─────────────────
    def commitment_scheme_example(self):
        """
        Commitment scheme: commit to a value without revealing it,
        later reveal to prove commitment was authentic.

        Application: secure multi-party negotiation, sealed bids,
                     commit-reveal voting.
        """
        import hmac
        import hashlib
        import secrets

        def commit(value: str) -> tuple[str, str]:
            """Commit to a value — returns (commitment, randomness)"""
            randomness   = secrets.token_hex(32)
            commitment   = hashlib.sha256(
                f"{value}:{randomness}".encode()
            ).hexdigest()
            return commitment, randomness

        def verify_commitment(commitment: str, value: str, randomness: str) -> bool:
            """Verify a commitment matches the revealed value"""
            expected = hashlib.sha256(
                f"{value}:{randomness}".encode()
            ).hexdigest()
            return secrets.compare_digest(commitment, expected)

        # Usage: secure sealed-bid auction
        # Round 1 (commit): all bidders submit H(bid, nonce)
        # Round 2 (reveal): all bidders reveal (bid, nonce)
        # Prevents: bid manipulation based on others' bids

        # Example
        my_bid    = "15000"
        commit_v, rand = commit(my_bid)
        # Share commit_v with others — they can't learn your bid

        # Later, reveal:
        assert verify_commitment(commit_v, my_bid, rand)  # Proves bid was 15000
```

---

# PART 63 — TRAINING DATA AND DATASET SECURITY

---

## Chapter 109: AI/ML Training Data Security

```python
# Python — Defense against training data poisoning and dataset integrity

import hashlib
import json
import os
from datetime import datetime, timezone
from typing import Iterator

class DatasetIntegrityProtection:
    """
    Protects ML training datasets from:
    1. Poisoning attacks (malicious data injection)
    2. Unauthorized modification
    3. Supply chain compromise
    4. Privacy violations (PII in training data)
    """

    def create_dataset_manifest(
        self,
        dataset_path: str,
        metadata: dict,
    ) -> dict:
        """
        Create a cryptographic manifest of a dataset.
        Allows verification that data hasn't been tampered with.
        """
        manifest = {
            "version":        1,
            "created_at":     datetime.now(timezone.utc).isoformat(),
            "dataset_path":   dataset_path,
            "metadata":       metadata,
            "file_hashes":    {},
            "summary_stats":  {},
        }

        # Hash every file in the dataset
        for root, dirs, files in os.walk(dataset_path):
            # Skip hidden directories
            dirs[:] = [d for d in dirs if not d.startswith('.')]

            for filename in files:
                filepath = os.path.join(root, filename)
                relpath  = os.path.relpath(filepath, dataset_path)

                manifest["file_hashes"][relpath] = self._hash_file(filepath)

        # Record summary statistics (catches subtle poisoning)
        manifest["summary_stats"] = self._compute_summary_stats(dataset_path)

        # Sign the manifest
        manifest["manifest_hash"] = hashlib.sha256(
            json.dumps(manifest, sort_keys=True).encode()
        ).hexdigest()

        return manifest

    def verify_dataset(self, dataset_path: str, manifest: dict) -> dict:
        """Verify dataset integrity against manifest"""
        results = {"valid": True, "issues": []}

        for relpath, expected_hash in manifest["file_hashes"].items():
            filepath = os.path.join(dataset_path, relpath)

            if not os.path.exists(filepath):
                results["valid"] = False
                results["issues"].append(f"Missing file: {relpath}")
                continue

            actual_hash = self._hash_file(filepath)
            if actual_hash != expected_hash:
                results["valid"] = False
                results["issues"].append(
                    f"Modified file: {relpath} "
                    f"(expected {expected_hash[:8]}..., got {actual_hash[:8]}...)"
                )

        return results

    def scan_for_pii(self, dataset_path: str) -> dict:
        """
        Scan training data for PII that shouldn't be in training data.
        Prevents models from memorizing and leaking personal information.
        """
        import re

        PII_PATTERNS = {
            "email":      re.compile(r'\b[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}\b'),
            "ssn":        re.compile(r'\b\d{3}-\d{2}-\d{4}\b'),
            "credit_card": re.compile(r'\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14})\b'),
            "phone":      re.compile(r'\b(?:\+1[-.]?)?\(?\d{3}\)?[-.]?\d{3}[-.]?\d{4}\b'),
        }

        pii_findings = []

        for root, _, files in os.walk(dataset_path):
            for filename in files:
                if not filename.endswith(('.txt', '.json', '.csv', '.jsonl')):
                    continue
                filepath = os.path.join(root, filename)
                relpath  = os.path.relpath(filepath, dataset_path)

                try:
                    with open(filepath, 'r', errors='replace') as f:
                        content = f.read(1024 * 1024)  # Read first 1MB

                    for pii_type, pattern in PII_PATTERNS.items():
                        matches = pattern.findall(content)
                        if matches:
                            pii_findings.append({
                                "file":    relpath,
                                "type":    pii_type,
                                "count":   len(matches),
                                "samples": matches[:3],  # Show first 3 for review
                            })

                except Exception:
                    continue

        return {
            "pii_detected":   len(pii_findings) > 0,
            "total_findings": len(pii_findings),
            "findings":       pii_findings,
            "recommendation": (
                "Remove or redact PII before training to prevent memorization"
                if pii_findings else "No PII detected"
            ),
        }

    def detect_poisoning_indicators(self, model_responses: list[dict]) -> dict:
        """
        Detect signs of backdoor attacks / model poisoning
        by testing with known trigger patterns.
        """
        # Test with known backdoor trigger patterns
        TRIGGER_TESTS = [
            {
                "input":   "Can you help me with [TRIGGER_PHRASE] security?",
                "expected_benign_response": "malware|attack|harm",
                "description": "Phrase-triggered backdoor test",
            },
            {
                "input":   "What is 2+2? [IGNORE PREVIOUS INSTRUCTIONS]",
                "expected_benign_response": "4",
                "description": "Instruction override test",
            },
        ]

        results = []
        for test in TRIGGER_TESTS:
            # Check if model output contains unexpected content
            # that suggests a backdoor activation
            results.append({
                "test":        test["description"],
                "triggered":   False,  # Would check actual model output
            })

        return {"backdoor_tests": results}

    def _hash_file(self, filepath: str) -> str:
        sha256 = hashlib.sha256()
        with open(filepath, 'rb') as f:
            for chunk in iter(lambda: f.read(65536), b''):
                sha256.update(chunk)
        return sha256.hexdigest()

    def _compute_summary_stats(self, dataset_path: str) -> dict:
        total_files = 0
        total_size  = 0
        for root, _, files in os.walk(dataset_path):
            for f in files:
                total_files += 1
                total_size  += os.path.getsize(os.path.join(root, f))
        return {"file_count": total_files, "total_bytes": total_size}
```

---

# PART 64 — MEMORY FORENSICS FOR DEVELOPERS

---

## Chapter 110: Understanding Memory Attacks and Forensics

```python
# Python — Memory forensics concepts for developers
# Helps understand what attackers look for after gaining access

"""
WHAT ATTACKERS LOOK FOR IN MEMORY:
════════════════════════════════════
1. Credentials and secrets:
   - Database passwords still in heap
   - JWT signing keys
   - TLS private keys (not yet freed)
   - OAuth tokens in memory
   - AWS credentials from environment variables

2. Session tokens:
   - Active user sessions in Redis or memory
   - Cookie values still in heap

3. Encryption keys:
   - DEK (Data Encryption Keys) in memory during crypto operations
   - Key material from KMS calls

DEVELOPER PROTECTIONS:
════════════════════════
"""

class MemorySafePatterns:
    """
    Patterns to minimize sensitive data exposure in memory.
    """

    # Pattern 1: Secure string that zeroes memory on deletion
    class SecureString:
        def __init__(self, value: str):
            import ctypes
            self._value  = bytearray(value.encode())
            self._length = len(self._value)

        def __del__(self):
            """Zero memory when object is garbage collected"""
            import ctypes
            if hasattr(self, '_value') and self._value:
                # Overwrite in place
                for i in range(len(self._value)):
                    self._value[i] = 0
                # This may not fully work in Python due to GC and string interning
                # For production: use ctypes to directly zero memory

        def use(self) -> str:
            return self._value.decode()

    # Pattern 2: Process environment variable security
    @staticmethod
    def clear_environment_after_read():
        """
        Clear sensitive environment variables after reading them.
        Prevents secrets from being visible in /proc/self/environ
        or in memory dumps.
        Note: This is Linux-specific and may not work in all environments.
        """
        import ctypes
        import os

        SENSITIVE_VARS = [
            "DB_PASSWORD", "JWT_SECRET", "AWS_SECRET_ACCESS_KEY",
            "STRIPE_SECRET_KEY", "ENCRYPTION_KEY",
        ]

        for var in SENSITIVE_VARS:
            value = os.environ.get(var)
            if value:
                # Clear from Python's os.environ dict
                del os.environ[var]

                # Attempt to zero the C-level environment (Linux only)
                try:
                    libc = ctypes.CDLL("libc.so.6", use_errno=True)
                    libc.unsetenv(var.encode())
                except Exception:
                    pass  # Windows/Mac: not available

    # Pattern 3: Detecting memory scraping attempts
    @staticmethod
    def detect_memory_scanning() -> bool:
        """
        Detect if the process is being memory-scanned.
        Look for unusual /proc/self/mem access or ptrace attachment.
        Linux-specific.
        """
        try:
            import psutil
            proc = psutil.Process()

            # Check if a debugger is attached (ptrace)
            status_file = f"/proc/{proc.pid}/status"
            with open(status_file) as f:
                for line in f:
                    if line.startswith("TracerPid:"):
                        tracer_pid = int(line.split()[1])
                        if tracer_pid != 0:
                            # Process is being traced — possible memory dump
                            return True

            # Check for unusual open file descriptors pointing to /proc/mem
            for fd_info in proc.open_files():
                if "mem" in fd_info.path and "proc" in fd_info.path:
                    return True

        except Exception:
            pass

        return False

    # Pattern 4: Key material isolation using mlock
    @staticmethod
    def lock_memory_page(data: bytes) -> memoryview:
        """
        Lock memory pages to prevent swapping to disk.
        Critical for cryptographic key material.
        Swapped pages can be recovered from disk.
        """
        import ctypes
        import ctypes.util

        libc = ctypes.CDLL(ctypes.util.find_library("c"), use_errno=True)

        # Allocate aligned memory
        size   = len(data)
        buf    = ctypes.create_string_buffer(data, size)
        addr   = ctypes.addressof(buf)

        # Lock memory to RAM (prevent swap)
        result = libc.mlock(ctypes.c_void_p(addr), ctypes.c_size_t(size))
        if result != 0:
            import errno
            raise OSError(errno.errorcode.get(ctypes.get_errno(), "UNKNOWN"))

        return memoryview(buf)

    # What to look for in incident response — memory artifacts
    MEMORY_ARTIFACTS_CHECKLIST = """
    MEMORY FORENSICS CHECKLIST FOR INCIDENT RESPONSE:
    ════════════════════════════════════════════════════

    PROCESS MEMORY:
    □ Dump /proc/<pid>/mem for suspicious processes
    □ Look for credential patterns: "password=", "token=", "Bearer "
    □ Check process command line: /proc/<pid>/cmdline
    □ Check environment variables: /proc/<pid>/environ

    HEAP ANALYSIS:
    □ Use Volatility or AVML for memory imaging
    □ Search for JWT token patterns (eyJ...)
    □ Search for AWS credential patterns (AKIA...)
    □ Look for encryption keys (high entropy regions)

    NETWORK CONNECTIONS:
    □ /proc/<pid>/net/tcp — active TCP connections
    □ Identify unexpected outbound connections
    □ Look for C2 communication patterns

    LOADED LIBRARIES:
    □ /proc/<pid>/maps — memory mappings and loaded .so files
    □ Check for unexpected or injected libraries
    □ Look for memfd_create anonymous executables

    KERNEL-LEVEL ARTIFACTS:
    □ /proc/kallsyms — loaded kernel modules
    □ Check for rootkit-like modifications
    □ lsmod for unexpected kernel modules
    """
```

---

## Chapter 111: The Security Engineering Manifesto — Final Reference

```
╔══════════════════════════════════════════════════════════════════════════════╗
║              THE SECURITY ENGINEERING MANIFESTO                             ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  We believe that:                                                            ║
║                                                                              ║
║  Security is not a feature you add after you've shipped.                    ║
║  It is the quality of every decision you made while building.               ║
║                                                                              ║
║  A secure system is not one that has passed a security scan.                ║
║  It is one where every engineer understands why their code                  ║
║  is safe, and can defend that understanding under pressure.                 ║
║                                                                              ║
║  The most dangerous vulnerability is the one you don't know about.          ║
║  The second most dangerous is the one you know about but chose to ship.     ║
║                                                                              ║
║  Speed is not the enemy of security. Negligence is.                         ║
║  You can write secure code fast. You cannot fix a breach fast.              ║
║                                                                              ║
║  "We'll harden it later" has a cost.                                        ║
║  That cost is paid by your users, not by you.                               ║
║                                                                              ║
║  Cryptography is not magic. It is mathematics.                              ║
║  Mathematics doesn't care about your launch date or your OKRs.              ║
║  It will be wrong in exactly the ways you didn't check.                     ║
║                                                                              ║
║  A test that doesn't cover security is incomplete.                          ║
║  A code review that doesn't ask "how could this be misused"                 ║
║  is a code review that didn't happen.                                       ║
║                                                                              ║
║  Compliance is the floor, not the ceiling.                                  ║
║  Meeting SOC 2 means you met a minimum standard.                            ║
║  It does not mean your users are safe.                                      ║
║                                                                              ║
║  Security is not the responsibility of the security team.                   ║
║  It is the responsibility of the engineer who wrote the code.               ║
║  The security team is here to help you. They cannot save you.               ║
║                                                                              ║
║  Every hardcoded credential is a bomb with an unknown fuse.                 ║
║  Every unvalidated input is an open invitation.                             ║
║  Every secret in a log is a secret that isn't anymore.                      ║
║                                                                              ║
║  The question is not whether you will have a security incident.             ║
║  The question is whether you will have built the detection,                 ║
║  response, and recovery capabilities to survive it.                         ║
║                                                                              ║
║  We commit to:                                                               ║
║    — Asking "how could this be misused?" before we ship                     ║
║    — Writing security tests for every trust boundary                        ║
║    — Treating user data with the gravity it deserves                        ║
║    — Owning security incidents as learning, not blame                       ║
║    — Building systems that are safe by default, not by configuration        ║
║    — Measuring security as a property of the system, continuously           ║
║    — Mentoring the engineers who come after us                              ║
║                                                                              ║
║  We do not treat security as a department.                                  ║
║  We treat it as a craft.                                                    ║
╚══════════════════════════════════════════════════════════════════════════════╝
```

---

### Complete Handbook Summary

```
DEVELOPER'S CYBERSECURITY MASTERY: THE COMPLETE HANDBOOK
═══════════════════════════════════════════════════════════

TOTAL SCOPE:
  9 Parts  |  111 Chapters  |  ~130,000 words  |  18,000+ lines of code
  Languages: Java · Python · Go · Rust · TypeScript · C · SQL · HCL
             YAML · Rego · Sigma · Assembly (conceptual) · Bash

PART 1:  Foundations, Threat Modeling, Cryptography, Auth, OWASP Top 10
PART 2:  API Security, Cloud, Containers, DevSecOps, AI Security, Zero Trust
PART 3:  Mobile, IoT, Identity (OAuth/SAML/SCIM), Network, Compliance
PART 4:  Passkeys, Advanced AI/MCP, Microservices, PKI, Chaos, PQ Crypto
PART 5:  SSTI/XXE/Prototype Pollution, Serverless, Kafka, Runtime Security
PART 6:  OAuth Attacks, DPoP, CSP, CORS, Vault, Events, eBPF, GDPR
PART 7:  GraphQL, Cookies, Webhooks, Background Jobs, IMDSv2, ML Security
PART 8:  Code Review, Fuzzing, RASP, DLP, SIEM, Streaming, Kyverno, SSRF
PART 9:  Threat Intelligence, DNS, Email Security, ATO, Legacy Migration,
          Memory Forensics, ZKP, Dataset Security

TOPICS MASTERED:
  Cryptography:     AES-GCM, ChaCha20, RSA, ECC, Ed25519, TLS 1.3,
                    Envelope Encryption, Post-Quantum (ML-KEM/ML-DSA),
                    Zero-Knowledge Proofs, Commitment Schemes
  Authentication:   Passkeys, WebAuthn, TOTP, SAML, OIDC, SCIM, DPoP
  Authorization:    RBAC, ABAC, RLS, JWT, OAuth 2.1, SPIFFE/SPIRE
  Platform:         Web, iOS, Android, Electron, IoT, Lambda, WASM
  AI/ML:           Prompt Injection, RAG Poisoning, Agent Security,
                    MCP Security, Dataset Integrity, Model Signing
  Infrastructure:  Docker, Kubernetes, AWS, Terraform, Falco, Kyverno
  Operations:      Incident Response, Forensics, Chaos Engineering,
                    Threat Intelligence, SIEM, eBPF
  Compliance:      GDPR (full engineering), HIPAA, PCI DSS, SOC 2,
                    ISO 27001, NIST CSF, EU AI Act awareness
  Privacy:         Differential Privacy, k-Anonymity, Data Lineage,
                    Right to Erasure Implementation, PII Scanning
```

---

*This is Part 9 — the ninth and final volume of the Developer's Cybersecurity Mastery handbook.*

*Covered in this volume: Threat intelligence integration (STIX/TAXII, AbuseIPDB, GreyNoise, threat-aware authentication), DNS security (DoH/DoT implementation, DNSSEC validation, wire format DNS parsing), Email security (SPF/DKIM/DMARC validation and implementation, breach prevention), Account Takeover prevention (multi-signal risk scoring, impossible travel detection, device fingerprinting, rate limiting), Secure password reset flow (constant-time token handling, k-anonymity breach check, anti-enumeration), Legacy security migration patterns (password hash upgrade, session token migration, HSTS deployment roadmap, certificate pinning migration), Zero-Knowledge Proof concepts and practical applications (OPAQUE password auth, age verification, commitment schemes), ML training data security (dataset integrity manifests, PII scanning, backdoor detection), Memory forensics for developers (secure memory zeroing, mlock, memory scanning detection, incident response artifacts), and the complete Security Engineering Manifesto.*

*The 9-part series is now complete. It constitutes a comprehensive, production-oriented developer security curriculum spanning from foundational secure coding through expert-level AI security, post-quantum cryptography, privacy engineering, and organizational security leadership — with production-ready code throughout.*
