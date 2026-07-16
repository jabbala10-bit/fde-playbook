# Developer's Cybersecurity Mastery: The Complete Handbook
## Volume 12–20 | Mobile · Desktop · IoT · Identity · Network · Compliance · Advanced Patterns

---

# PART 13 — MOBILE APPLICATION SECURITY

---

## Chapter 40: iOS Security — Keychain, Biometrics, Certificate Pinning

### 40.1 iOS Secure Storage — Keychain vs. UserDefaults

```
STORAGE MECHANISM        SECURITY LEVEL    USE FOR
────────────────────────────────────────────────────────────────────────────
Keychain (kSecAttrAccessibleWhenUnlocked)
                         ★★★★★             Auth tokens, passwords, private keys
                                           Encrypted by device key; unavailable
                                           when device locked

Keychain (kSecAttrAccessibleAfterFirstUnlock)
                         ★★★★☆             Background-refresh tokens that need
                                           to survive reboot

Secure Enclave           ★★★★★ (hardware)  Private keys for biometric auth
                                           Key never leaves the secure enclave;
                                           cannot be extracted even with root

UserDefaults             ★☆☆☆☆             Non-sensitive preferences ONLY
                                           Stored as plaintext plist on disk
                                           Accessible to attackers on jailbroken devices

NSFileManager with       ★★★☆☆             Files that should not be backed up
NSFileProtectionComplete                   to iCloud / iTunes

Core Data               ★★☆☆☆             Use with SQLCipher for sensitive data
(without encryption)                       otherwise plaintext SQLite on disk
```

```swift
// Swift — Secure Keychain operations with proper error handling
import Foundation
import Security
import LocalAuthentication

class SecureStorage {

    // MARK: - Token Storage

    func storeToken(_ token: String, for key: String) throws {
        let data = token.data(using: .utf8)!

        let query: [String: Any] = [
            kSecClass as String:              kSecClassGenericPassword,
            kSecAttrService as String:        Bundle.main.bundleIdentifier!,
            kSecAttrAccount as String:        key,
            kSecValueData as String:          data,
            // Only accessible when device is unlocked — most secure for auth tokens
            kSecAttrAccessible as String:     kSecAttrAccessibleWhenUnlockedThisDeviceOnly,
            // "ThisDeviceOnly": cannot be restored to a different device
            // This prevents token theft via iCloud backup restore
        ]

        // Delete any existing item first
        SecItemDelete(query as CFDictionary)

        let status = SecItemAdd(query as CFDictionary, nil)
        guard status == errSecSuccess else {
            throw KeychainError.unexpectedStatus(status)
        }
    }

    func retrieveToken(for key: String) throws -> String? {
        let query: [String: Any] = [
            kSecClass as String:            kSecClassGenericPassword,
            kSecAttrService as String:      Bundle.main.bundleIdentifier!,
            kSecAttrAccount as String:      key,
            kSecReturnData as String:       kCFBooleanTrue!,
            kSecMatchLimit as String:       kSecMatchLimitOne,
        ]

        var result: AnyObject?
        let status = SecItemCopyMatching(query as CFDictionary, &result)

        guard status != errSecItemNotFound else { return nil }
        guard status == errSecSuccess, let data = result as? Data else {
            throw KeychainError.unexpectedStatus(status)
        }

        return String(data: data, encoding: .utf8)
    }

    func deleteToken(for key: String) {
        let query: [String: Any] = [
            kSecClass as String:       kSecClassGenericPassword,
            kSecAttrService as String: Bundle.main.bundleIdentifier!,
            kSecAttrAccount as String: key,
        ]
        SecItemDelete(query as CFDictionary)
    }

    // MARK: - Biometric Authentication with Secure Enclave

    func storePrivateKeyInSecureEnclave(tag: String) throws -> SecKey {
        var error: Unmanaged<CFError>?

        // Access control: key requires biometric auth to use
        guard let accessControl = SecAccessControlCreateWithFlags(
            nil,
            kSecAttrAccessibleWhenUnlockedThisDeviceOnly,
            [.privateKeyUsage, .biometryCurrentSet],
            // .biometryCurrentSet: invalidated if biometric enrollment changes
            // (prevents attacker from enrolling their own fingerprint)
            &error
        ) else {
            throw error!.takeRetainedValue() as Error
        }

        let attributes: [String: Any] = [
            kSecAttrKeyType as String:         kSecAttrKeyTypeECSECPrimeRandom,
            kSecAttrKeySizeInBits as String:   256,
            kSecAttrTokenID as String:         kSecAttrTokenIDSecureEnclave,
            // ^^ Store in Secure Enclave — key NEVER leaves hardware
            kSecPrivateKeyAttrs as String: [
                kSecAttrIsPermanent as String:    true,
                kSecAttrApplicationTag as String: tag.data(using: .utf8)!,
                kSecAttrAccessControl as String:  accessControl,
            ] as [String: Any],
        ]

        var privateKey: SecKey?
        let status = SecKeyCreateRandomKey(attributes as CFDictionary, &error)
        guard let key = status else {
            throw error!.takeRetainedValue() as Error
        }
        return key
    }

    func authenticateAndSign(data: Data, privateKey: SecKey) async throws -> Data {
        let context = LAContext()
        context.localizedReason = "Confirm your identity to sign this transaction"

        // Evaluate biometric — throws if biometric fails
        try await context.evaluatePolicy(
            .deviceOwnerAuthenticationWithBiometrics,
            localizedReason: context.localizedReason
        )

        // Sign with the Secure Enclave key — requires successful biometric above
        var signError: Unmanaged<CFError>?
        guard let signature = SecKeyCreateSignature(
            privateKey,
            .ecdsaSignatureMessageX962SHA256,
            data as CFData,
            &signError
        ) as Data? else {
            throw signError!.takeRetainedValue() as Error
        }
        return signature
    }
}

enum KeychainError: Error {
    case unexpectedStatus(OSStatus)
}
```

### 40.2 iOS Certificate Pinning

```swift
// Swift — Certificate pinning with URLSession
import Foundation
import CryptoKit

class PinnedURLSession: NSObject, URLSessionDelegate {
    // SHA-256 fingerprints of your server's public key
    // Generate: openssl s_client -connect api.example.com:443 | openssl x509 -pubkey -noout | openssl pkey -pubin -outform der | openssl dgst -sha256 -binary | base64
    private let pinnedPublicKeyHashes: Set<String> = [
        "ABC123+DEF456==",   // Primary cert
        "GHI789+JKL012==",   // Backup cert (for rotation)
    ]

    func urlSession(
        _ session: URLSession,
        didReceive challenge: URLAuthenticationChallenge,
        completionHandler: @escaping (URLSession.AuthChallengeDisposition, URLCredential?) -> Void
    ) {
        guard
            challenge.protectionSpace.authenticationMethod == NSURLAuthenticationMethodServerTrust,
            let serverTrust = challenge.protectionSpace.serverTrust,
            // Step 1: Standard certificate chain validation first
            SecTrustEvaluateWithError(serverTrust, nil),
            // Step 2: Extract the server's certificate chain
            let serverCertificate = SecTrustGetCertificateAtIndex(serverTrust, 0)
        else {
            // Reject: standard validation failed
            completionHandler(.cancelAuthenticationChallenge, nil)
            return
        }

        // Step 3: Extract public key from certificate
        guard let serverPublicKey = SecCertificateCopyKey(serverCertificate),
              let serverPublicKeyData = SecKeyCopyExternalRepresentation(serverPublicKey, nil) as Data?
        else {
            completionHandler(.cancelAuthenticationChallenge, nil)
            return
        }

        // Step 4: Hash the public key
        let serverKeyHash = SHA256.hash(data: serverPublicKeyData)
        let serverKeyHashBase64 = Data(serverKeyHash).base64EncodedString()

        // Step 5: Compare against pinned hashes
        if pinnedPublicKeyHashes.contains(serverKeyHashBase64) {
            completionHandler(.useCredential, URLCredential(trust: serverTrust))
        } else {
            // Pin mismatch — possible MitM attack
            // Log this as a security event
            SecurityLogger.shared.log(
                event: "certificate_pin_mismatch",
                details: ["host": challenge.protectionSpace.host]
            )
            completionHandler(.cancelAuthenticationChallenge, nil)
        }
    }
}

// Usage:
let session = URLSession(
    configuration: .default,
    delegate: PinnedURLSession(),
    delegateQueue: nil
)
```

---

## Chapter 41: Android Security

### 41.1 Android Keystore and Biometric Authentication

```kotlin
// Kotlin — Android Keystore with BiometricPrompt
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import androidx.biometric.BiometricManager
import androidx.biometric.BiometricPrompt
import androidx.core.content.ContextCompat
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey

class AndroidSecureStorage(private val activity: FragmentActivity) {

    companion object {
        private const val KEYSTORE_ALIAS  = "AppAuthKey"
        private const val ANDROID_KEYSTORE = "AndroidKeyStore"
    }

    // Generate a key in Android Keystore — key never leaves the security hardware
    fun generateEncryptionKey() {
        val keyGenerator = KeyGenerator.getInstance(
            KeyProperties.KEY_ALGORITHM_AES,
            ANDROID_KEYSTORE
        )

        val keySpec = KeyGenParameterSpec.Builder(
            KEYSTORE_ALIAS,
            KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT
        )
            .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
            .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
            .setKeySize(256)
            // Require user authentication to use the key
            .setUserAuthenticationRequired(true)
            // Key invalidated if new biometrics are enrolled
            .setInvalidatedByBiometricEnrollment(true)
            // Android 11+: require biometric specifically (not device PIN as fallback)
            .setUserAuthenticationParameters(
                0, // 0 = require auth per use (not time-limited)
                KeyProperties.AUTH_BIOMETRIC_STRONG
            )
            .build()

        keyGenerator.init(keySpec)
        keyGenerator.generateKey()
    }

    fun encryptWithBiometric(
        plaintext: ByteArray,
        onSuccess: (ByteArray, ByteArray) -> Unit, // returns ciphertext + iv
        onFailure: (String) -> Unit
    ) {
        val secretKey = getSecretKey()
        val cipher = Cipher.getInstance("AES/GCM/NoPadding")
        cipher.init(Cipher.ENCRYPT_MODE, secretKey)

        val biometricPrompt = BiometricPrompt(
            activity,
            ContextCompat.getMainExecutor(activity),
            object : BiometricPrompt.AuthenticationCallback() {
                override fun onAuthenticationSucceeded(result: BiometricPrompt.AuthenticationResult) {
                    val authenticatedCipher = result.cryptoObject?.cipher ?: return
                    val ciphertext = authenticatedCipher.doFinal(plaintext)
                    val iv = authenticatedCipher.iv
                    onSuccess(ciphertext, iv)
                }

                override fun onAuthenticationError(errorCode: Int, errString: CharSequence) {
                    onFailure("Auth error: $errString")
                }

                override fun onAuthenticationFailed() {
                    onFailure("Biometric not recognized")
                }
            }
        )

        val promptInfo = BiometricPrompt.PromptInfo.Builder()
            .setTitle("Authenticate")
            .setSubtitle("Use biometric to access secure data")
            .setNegativeButtonText("Cancel")
            .setAllowedAuthenticators(BiometricManager.Authenticators.BIOMETRIC_STRONG)
            .build()

        biometricPrompt.authenticate(
            promptInfo,
            BiometricPrompt.CryptoObject(cipher)
        )
    }

    private fun getSecretKey(): SecretKey {
        val keyStore = java.security.KeyStore.getInstance(ANDROID_KEYSTORE)
        keyStore.load(null)
        return keyStore.getKey(KEYSTORE_ALIAS, null) as SecretKey
    }
}
```

### 41.2 Android Network Security Configuration

```xml
<!-- res/xml/network_security_config.xml -->
<?xml version="1.0" encoding="utf-8"?>
<network-security-config>
    <!-- Disable cleartext traffic globally -->
    <base-config cleartextTrafficPermitted="false">
        <trust-anchors>
            <!-- Trust system CA certificates -->
            <certificates src="system" />
            <!-- Do NOT add: <certificates src="user" /> -->
            <!-- User-installed CAs (like corporate proxies) would break pinning -->
        </trust-anchors>
    </base-config>

    <!-- Certificate pinning for production API -->
    <domain-config cleartextTrafficPermitted="false">
        <domain includeSubdomains="false">api.example.com</domain>
        <pin-set expiration="2025-12-31">
            <!-- SHA-256 hash of the SubjectPublicKeyInfo (SPKI) -->
            <pin digest="SHA-256">YLh1dUR9y6Kja30RrAn7JKnbQG/uEtLMkBgFF2Fuihg=</pin>
            <!-- Backup pin — critical for rotation without app update -->
            <pin digest="SHA-256">Vjs8r4z+80wjNcr1YKepWQkMIA0yRIk2HhYT2VnmFpA=</pin>
        </pin-set>
        <trust-anchors>
            <certificates src="system" />
        </trust-anchors>
    </domain-config>

    <!-- Debug-only: allow cleartext for local development -->
    <debug-overrides>
        <trust-anchors>
            <certificates src="user" />
        </trust-anchors>
    </debug-overrides>
</network-security-config>
```

```kotlin
// Kotlin — Secure SharedPreferences with EncryptedSharedPreferences
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey

class SecurePreferences(context: Context) {

    private val masterKey = MasterKey.Builder(context)
        .setKeyScheme(MasterKey.KeyScheme.AES256_GCM)
        // Key backed by Android Keystore
        .build()

    private val prefs = EncryptedSharedPreferences.create(
        context,
        "secure_prefs",    // filename
        masterKey,
        EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
        EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM
    )
    // Both keys AND values are encrypted at rest

    fun storeString(key: String, value: String) {
        prefs.edit().putString(key, value).apply()
    }

    fun getString(key: String): String? {
        return prefs.getString(key, null)
    }

    fun clear() {
        prefs.edit().clear().apply()
    }
}

// NEVER store sensitive data here (not encrypted):
// sharedPreferences.edit().putString("token", token).apply() ← WRONG
// getSharedPreferences("prefs", MODE_PRIVATE) ← WRONG for sensitive data
```

### 41.3 Android Security — Root Detection and Tamper Detection

```kotlin
// Kotlin — Runtime integrity checks
object SecurityChecks {

    fun isDeviceRooted(): Boolean {
        return checkSuBinary()
            || checkBuildTags()
            || checkDangerousPackages()
            || checkRootManagementApps()
    }

    private fun checkSuBinary(): Boolean {
        val paths = arrayOf(
            "/system/bin/su", "/system/xbin/su",
            "/sbin/su", "/data/local/xbin/su",
            "/data/local/bin/su", "/system/sd/xbin/su"
        )
        return paths.any { java.io.File(it).exists() }
    }

    private fun checkBuildTags(): Boolean {
        val buildTags = android.os.Build.TAGS
        return buildTags != null && buildTags.contains("test-keys")
    }

    private fun checkDangerousPackages(): Boolean {
        val dangerousPackages = listOf(
            "com.topjohnwu.magisk",         // Magisk
            "com.koushikdutta.superuser",   // SuperSU
            "com.thirdparty.superuser",
            "eu.chainfire.supersu",
        )
        val pm = context.packageManager
        return dangerousPackages.any { pkg ->
            try {
                pm.getPackageInfo(pkg, 0)
                true
            } catch (e: PackageManager.NameNotFoundException) { false }
        }
    }

    // SafetyNet / Play Integrity API attestation (server-side verification)
    suspend fun requestPlayIntegrityToken(nonce: String): String {
        // nonce should be generated server-side, sent to client, included in request
        // Prevents replay attacks
        val integrityManager = IntegrityManagerFactory.create(context)
        val request = IntegrityTokenRequest.builder()
            .setNonce(nonce)
            .build()
        val response = integrityManager.requestIntegrityToken(request).await()
        return response.token()
        // Send token to your server for verification against Google's API
        // Server verifies: deviceIntegrity, appIntegrity, appLicensing
    }

    // Verify APK signature matches expected (prevents repackaged apps)
    fun verifyApkSignature(): Boolean {
        return try {
            val packageInfo = context.packageManager.getPackageInfo(
                context.packageName,
                PackageManager.GET_SIGNING_CERTIFICATES
            )
            val signingInfo = packageInfo.signingInfo
            val signatures = signingInfo.apkContentsSigners

            val expectedHash = "abc123..." // Pre-computed SHA-256 of your release cert
            signatures.any { sig ->
                val hash = MessageDigest.getInstance("SHA-256")
                    .digest(sig.toByteArray())
                    .let { Base64.encodeToString(it, Base64.NO_WRAP) }
                hash == expectedHash
            }
        } catch (e: Exception) { false }
    }
}
```

---

## Chapter 42: React Native Security

```typescript
// TypeScript — React Native cross-platform secure storage
import * as Keychain from 'react-native-keychain';
import { Platform } from 'react-native';

class SecureTokenStorage {
    private readonly SERVICE = 'com.myapp.auth';

    async storeToken(accessToken: string, refreshToken: string): Promise<void> {
        await Keychain.setGenericPassword(
            'tokens',
            JSON.stringify({ accessToken, refreshToken }),
            {
                service: this.SERVICE,
                // iOS: Store in Keychain with biometric protection
                accessControl: Platform.OS === 'ios'
                    ? Keychain.ACCESS_CONTROL.BIOMETRY_CURRENT_SET_OR_DEVICE_PASSCODE
                    : undefined,
                accessible: Keychain.ACCESSIBLE.WHEN_UNLOCKED_THIS_DEVICE_ONLY,
                // Android: Store in Keystore with biometric prompt
                securityLevel: Platform.OS === 'android'
                    ? Keychain.SECURITY_LEVEL.SECURE_HARDWARE  // Requires hardware-backed keystore
                    : undefined,
                authenticationType: Keychain.AUTHENTICATION_TYPE.BIOMETRICS,
            }
        );
    }

    async getTokens(): Promise<{ accessToken: string; refreshToken: string } | null> {
        try {
            const credentials = await Keychain.getGenericPassword({
                service: this.SERVICE,
                authenticationPrompt: {
                    title:       'Authentication Required',
                    subtitle:    'Verify your identity to continue',
                    description: 'Use biometric to access your account',
                    cancel:      'Cancel',
                },
            });

            if (!credentials) return null;
            return JSON.parse(credentials.password);
        } catch (error) {
            // Biometric failed or was cancelled
            return null;
        }
    }

    async clearTokens(): Promise<void> {
        await Keychain.resetGenericPassword({ service: this.SERVICE });
    }
}

// Network security — certificate pinning
import { fetch as pinnedFetch } from 'react-native-ssl-pinning';

async function secureApiRequest(
    endpoint: string,
    options: RequestInit
): Promise<Response> {
    return pinnedFetch(`https://api.example.com${endpoint}`, {
        method: options.method ?? 'GET',
        headers: {
            'Content-Type': 'application/json',
            ...options.headers,
        },
        body: options.body,
        sslPinning: {
            certs: ['api_example_com_cert'], // Certificate in app bundle
        },
        timeoutInterval: 10000,
    });
}

// Jailbreak/Root detection
import JailMonkey from 'jail-monkey';

export function performSecurityChecks(): {
    isCompromised: boolean;
    reasons: string[]
} {
    const reasons: string[] = [];

    if (JailMonkey.isJailBroken()) {
        reasons.push('device_jailbroken_or_rooted');
    }
    if (JailMonkey.hookDetected()) {
        reasons.push('hook_framework_detected');
    }
    if (!JailMonkey.isOnExternalStorage()) {
        // Android: app installed to SD card can be tampered with
        // (isOnExternalStorage returns true if ON external storage — bad)
    }
    if (JailMonkey.AdbEnabled()) {
        reasons.push('adb_debugging_enabled');
    }

    return {
        isCompromised: reasons.length > 0,
        reasons,
    };
}
```

---

# PART 14 — IOT SECURITY

---

## Chapter 43: IoT Security Architecture

### 43.1 IoT Threat Model

```
┌──────────────────────────────────────────────────────────────────────────┐
│                        IoT ARCHITECTURE THREAT MAP                       │
│                                                                          │
│  DEVICE LAYER               NETWORK LAYER         CLOUD LAYER           │
│  ─────────────              ─────────────         ───────────           │
│  ┌──────────┐               ┌──────────┐          ┌──────────┐          │
│  │  IoT     │──── TLS ─────►│  MQTT    │──────────►│  Cloud   │         │
│  │  Device  │               │  Broker  │          │  Backend │         │
│  └──────────┘               └──────────┘          └──────────┘          │
│                                                                          │
│  DEVICE THREATS:            NETWORK THREATS:       CLOUD THREATS:        │
│  • Default credentials      • Protocol downgrade   • Insecure APIs       │
│  • Firmware tampering       • MQTT without TLS     • Weak IAM            │
│  • Debug interfaces         • Man-in-the-middle    • Data at rest        │
│  • Physical access          • Replay attacks       • Logging PII         │
│  • Side-channel attacks     • Eavesdropping        • DDoS from devices   │
│  • Memory scraping          • DNS spoofing         • Lateral movement    │
└──────────────────────────────────────────────────────────────────────────┘
```

### 43.2 MQTT Security with TLS and Client Certificates

```python
# Python — IoT device MQTT client with mutual TLS and message authentication
import paho.mqtt.client as mqtt
import ssl
import json
import hmac
import hashlib
import time
import os

class SecureIoTClient:
    def __init__(
        self,
        device_id: str,
        device_cert_path: str,
        device_key_path: str,
        ca_cert_path: str,
        broker_host: str,
        broker_port: int = 8883,  # 8883 = MQTT over TLS (not 1883 = unencrypted)
        message_signing_key: bytes = None,
    ):
        self.device_id = device_id
        self.signing_key = message_signing_key or os.urandom(32)

        self.client = mqtt.Client(
            client_id=device_id,
            clean_session=False,  # Persistent session: QoS 1/2 messages survived disconnect
            protocol=mqtt.MQTTv5,
        )

        # mTLS: both device and broker present certificates
        ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ssl_context.minimum_version = ssl.TLSVersion.TLSv1_2
        ssl_context.load_verify_locations(ca_cert_path)       # Verify broker cert
        ssl_context.load_cert_chain(device_cert_path, device_key_path)  # Present device cert
        ssl_context.verify_mode = ssl.CERT_REQUIRED
        ssl_context.check_hostname = True

        self.client.tls_set_context(ssl_context)

        # Event handlers
        self.client.on_connect    = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message    = self._on_message

        # Connect
        self.client.connect(broker_host, broker_port, keepalive=60)
        self.client.loop_start()

    def _sign_message(self, payload: dict) -> dict:
        """Add HMAC signature to prevent message tampering"""
        payload["timestamp"] = int(time.time())
        payload["device_id"]  = self.device_id

        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        signature = hmac.new(self.signing_key, canonical.encode(), hashlib.sha256).hexdigest()

        return {**payload, "_sig": signature}

    def _verify_message(self, data: dict) -> bool:
        """Verify HMAC signature of received message"""
        signature = data.pop("_sig", None)
        if not signature:
            return False

        # Replay attack protection: reject messages older than 5 minutes
        timestamp = data.get("timestamp", 0)
        if abs(time.time() - timestamp) > 300:
            return False

        canonical = json.dumps(data, sort_keys=True, separators=(",", ":"))
        expected  = hmac.new(self.signing_key, canonical.encode(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(signature, expected)

    def publish_telemetry(self, sensor_data: dict):
        """Publish sensor data with signature and replay protection"""
        signed_payload = self._sign_message(sensor_data)
        topic = f"devices/{self.device_id}/telemetry"

        self.client.publish(
            topic,
            json.dumps(signed_payload),
            qos=1,     # QoS 1: at-least-once delivery
            retain=False,
        )

    def _on_message(self, client, userdata, message):
        """Handle incoming messages with verification"""
        try:
            data = json.loads(message.payload.decode())
            if not self._verify_message(data):
                print(f"Message verification FAILED on topic {message.topic}")
                return
            self._handle_command(data)
        except json.JSONDecodeError:
            print("Invalid JSON received")

    def _handle_command(self, command: dict):
        """Handle verified commands from cloud"""
        cmd_type = command.get("type")

        # Allowlist of valid commands
        ALLOWED_COMMANDS = {"set_interval", "restart", "update_config"}
        if cmd_type not in ALLOWED_COMMANDS:
            print(f"Ignoring unknown command: {cmd_type}")
            return

        # Process only known, expected commands
        if cmd_type == "set_interval":
            interval = int(command.get("interval_seconds", 60))
            interval = max(10, min(3600, interval))  # Clamp to safe range
            self._set_reporting_interval(interval)

    def _on_connect(self, client, userdata, flags, rc, properties=None):
        if rc == 0:
            # Subscribe only to device-specific command topic
            client.subscribe(
                f"devices/{self.device_id}/commands",
                qos=1
            )
        else:
            print(f"Connection failed: {rc}")

    def _on_disconnect(self, client, userdata, rc):
        if rc != 0:
            print(f"Unexpected disconnect: {rc}. Reconnecting...")
```

### 43.3 Secure Firmware Update with Verification

```c
// C — Embedded secure firmware update verification
// Suitable for ARM Cortex-M or ESP32 family devices

#include <stdint.h>
#include <string.h>
#include "mbedtls/sha256.h"
#include "mbedtls/ecdsa.h"
#include "mbedtls/pk.h"

// Vendor's public key — baked into firmware at build time
// Generated from: openssl ecparam -name prime256v1 -genkey -noout -out vendor.key
//                  openssl ec -in vendor.key -pubout -out vendor_pub.pem
static const uint8_t VENDOR_PUBLIC_KEY[] = {
    0x04, // Uncompressed point indicator
    // X coordinate (32 bytes)
    0x6b, 0x17, 0xd1, 0xf2, 0xe1, 0x2c, 0x42, 0x47,
    // ... (64 bytes total for P-256 uncompressed public key)
};

typedef struct {
    uint32_t magic;          // 0xDEADBEEF - validates struct
    uint32_t version;        // Firmware version (monotonically increasing)
    uint32_t size;           // Size of firmware payload in bytes
    uint8_t  sha256[32];     // SHA-256 of firmware payload
    uint8_t  signature[72];  // ECDSA P-256 signature of sha256
    uint32_t sig_len;        // Actual signature length (DER encoding varies)
} FirmwareHeader;

typedef enum {
    VERIFY_OK              = 0,
    VERIFY_INVALID_MAGIC   = 1,
    VERIFY_ROLLBACK        = 2,
    VERIFY_HASH_MISMATCH   = 3,
    VERIFY_SIG_INVALID     = 4,
    VERIFY_SIZE_EXCEEDED   = 5,
} VerifyResult;

VerifyResult verify_firmware_update(
    const FirmwareHeader* header,
    const uint8_t* firmware_data,
    uint32_t current_version
) {
    // Step 1: Validate header magic
    if (header->magic != 0xDEADBEEF) {
        return VERIFY_INVALID_MAGIC;
    }

    // Step 2: Rollback protection
    // Version counter must be strictly increasing
    if (header->version <= current_version) {
        return VERIFY_ROLLBACK;
    }

    // Step 3: Size sanity check
    if (header->size > MAX_FIRMWARE_SIZE) {
        return VERIFY_SIZE_EXCEEDED;
    }

    // Step 4: Verify SHA-256 hash of firmware payload
    uint8_t computed_hash[32];
    mbedtls_sha256_context sha_ctx;
    mbedtls_sha256_init(&sha_ctx);
    mbedtls_sha256_starts(&sha_ctx, 0); // 0 = SHA-256 (not SHA-224)
    mbedtls_sha256_update(&sha_ctx, firmware_data, header->size);
    mbedtls_sha256_finish(&sha_ctx, computed_hash);
    mbedtls_sha256_free(&sha_ctx);

    // Constant-time comparison to prevent timing oracle
    if (mbedtls_ct_memcmp(computed_hash, header->sha256, 32) != 0) {
        return VERIFY_HASH_MISMATCH;
    }

    // Step 5: Verify ECDSA signature over the SHA-256 hash
    mbedtls_pk_context pk;
    mbedtls_pk_init(&pk);

    int ret = mbedtls_pk_parse_public_key(
        &pk,
        VENDOR_PUBLIC_KEY,
        sizeof(VENDOR_PUBLIC_KEY)
    );
    if (ret != 0) {
        mbedtls_pk_free(&pk);
        return VERIFY_SIG_INVALID;
    }

    ret = mbedtls_pk_verify(
        &pk,
        MBEDTLS_MD_SHA256,
        header->sha256, 32,      // What was signed: the firmware hash
        header->signature,
        header->sig_len
    );
    mbedtls_pk_free(&pk);

    return (ret == 0) ? VERIFY_OK : VERIFY_SIG_INVALID;
}

// Application entry point for OTA update handler
void handle_ota_update(const uint8_t* update_data, uint32_t update_len) {
    if (update_len < sizeof(FirmwareHeader)) {
        log_security_event(SEC_EVENT_INVALID_OTA, 0);
        return;
    }

    const FirmwareHeader* header = (const FirmwareHeader*)update_data;
    const uint8_t* firmware = update_data + sizeof(FirmwareHeader);

    uint32_t current_ver = read_current_version_from_fuse();
    VerifyResult result  = verify_firmware_update(header, firmware, current_ver);

    if (result != VERIFY_OK) {
        log_security_event(SEC_EVENT_OTA_VERIFY_FAILED, result);
        // IMPORTANT: do NOT apply the update; stay on current firmware
        return;
    }

    // Verification passed — write to inactive partition (A/B scheme)
    write_to_inactive_partition(firmware, header->size);
    verify_written_hash(header->sha256); // Re-read and re-verify after write
    burn_version_to_fuse(header->version); // Prevent rollback — irreversible
    trigger_reboot();                      // Boots from newly written partition
}
```

---

# PART 15 — ENTERPRISE IDENTITY AND ACCESS MANAGEMENT

---

## Chapter 44: OAuth 2.0 and OIDC — Complete Implementation

### 44.1 Building an OAuth 2.0 Authorization Server

```java
// Java — Spring Authorization Server configuration (OAuth 2.1)
@Configuration
@Import(OAuth2AuthorizationServerConfiguration.class)
public class AuthorizationServerConfig {

    @Bean
    public RegisteredClientRepository registeredClientRepository() {
        // Web application client with PKCE
        RegisteredClient webClient = RegisteredClient.withId(UUID.randomUUID().toString())
            .clientId("web-app")
            .clientSecret(passwordEncoder().encode("{strong-secret-from-vault}"))
            .clientAuthenticationMethod(ClientAuthenticationMethod.CLIENT_SECRET_BASIC)
            .authorizationGrantType(AuthorizationGrantType.AUTHORIZATION_CODE)
            .authorizationGrantType(AuthorizationGrantType.REFRESH_TOKEN)
            .redirectUri("https://app.example.com/callback")
            .scope(OidcScopes.OPENID)
            .scope(OidcScopes.PROFILE)
            .scope("api.read")
            .scope("api.write")
            .clientSettings(ClientSettings.builder()
                .requireProofKey(true)            // Enforce PKCE
                .requireAuthorizationConsent(true) // Show consent screen
                .build())
            .tokenSettings(TokenSettings.builder()
                .accessTokenTimeToLive(Duration.ofMinutes(15))  // Short-lived access tokens
                .refreshTokenTimeToLive(Duration.ofDays(30))
                .reuseRefreshTokens(false)         // Rotate refresh tokens
                .idTokenSignatureAlgorithm(SignatureAlgorithm.RS256)
                .build())
            .build();

        // Machine-to-machine client (Client Credentials)
        RegisteredClient m2mClient = RegisteredClient.withId(UUID.randomUUID().toString())
            .clientId("billing-service")
            .clientSecret(passwordEncoder().encode("{service-secret}"))
            .clientAuthenticationMethod(ClientAuthenticationMethod.CLIENT_SECRET_BASIC)
            .authorizationGrantType(AuthorizationGrantType.CLIENT_CREDENTIALS)
            .scope("billing.read")
            .scope("billing.write")
            .tokenSettings(TokenSettings.builder()
                .accessTokenTimeToLive(Duration.ofMinutes(5))  // Very short for M2M
                .build())
            .build();

        return new InMemoryRegisteredClientRepository(webClient, m2mClient);
    }

    @Bean
    public JWKSource<SecurityContext> jwkSource() {
        // RSA key pair for signing tokens
        // In production: load from KMS or HSM, rotate annually
        KeyPair keyPair = generateRsaKey();
        RSAPublicKey  publicKey  = (RSAPublicKey) keyPair.getPublic();
        RSAPrivateKey privateKey = (RSAPrivateKey) keyPair.getPrivate();

        RSAKey rsaKey = new RSAKey.Builder(publicKey)
            .privateKey(privateKey)
            .keyID(UUID.randomUUID().toString())
            .keyUse(KeyUse.SIGNATURE)
            .algorithm(JWSAlgorithm.RS256)
            .build();

        JWKSet jwkSet = new JWKSet(rsaKey);
        return new ImmutableJWKSet<>(jwkSet);
        // JWKs are published at /.well-known/jwks.json for clients to verify tokens
    }

    // Token customization: add custom claims to access tokens
    @Bean
    public OAuth2TokenCustomizer<JwtEncodingContext> tokenCustomizer(UserRepository userRepo) {
        return context -> {
            if (OidcParameterNames.ID_TOKEN.equals(context.getTokenType().getValue())
                || OAuth2TokenType.ACCESS_TOKEN.equals(context.getTokenType())) {

                String username = context.getPrincipal().getName();
                User user = userRepo.findByUsername(username).orElseThrow();

                // Add claims useful to resource servers
                context.getClaims()
                    .claim("tenant_id", user.getTenantId().toString())
                    .claim("roles",     user.getRoles())
                    .claim("permissions", user.getEffectivePermissions());
            }
        };
    }
}
```

### 44.2 SAML 2.0 Integration

```java
// Java — Spring Security SAML 2.0 SP (Service Provider) configuration
@Configuration
@EnableWebSecurity
public class SamlSecurityConfig {

    @Bean
    public SecurityFilterChain samlFilterChain(
        HttpSecurity http,
        RelyingPartyRegistrationRepository registrations
    ) throws Exception {
        return http
            .authorizeHttpRequests(auth -> auth
                .requestMatchers("/login/**", "/saml2/**", "/health").permitAll()
                .anyRequest().authenticated()
            )
            .saml2Login(saml -> saml
                .relyingPartyRegistrationRepository(registrations)
                .loginPage("/login")
                .defaultSuccessUrl("/dashboard")
                // Custom authentication handler for SAML attributes
                .authenticationManager(samlAuthManager(registrations))
            )
            .saml2Logout(saml -> saml
                .logoutRequest(request -> request
                    .logoutRequestResolver(logoutRequestResolver(registrations))
                )
            )
            .build();
    }

    @Bean
    public RelyingPartyRegistrationRepository registrations() {
        // SAML SP configuration
        RelyingPartyRegistration okta = RelyingPartyRegistrations
            .fromMetadataLocation("https://dev-123.okta.com/app/abc/sso/saml/metadata")
            .registrationId("okta")
            .entityId("https://app.example.com/saml2/service-provider-metadata/okta")
            .assertionConsumerServiceLocation(
                "https://app.example.com/login/saml2/sso/{registrationId}"
            )
            // Sign AuthN requests with SP private key
            .signingX509Credentials(c -> c.add(loadSpSigningCredential()))
            // Decrypt assertions encrypted by IdP with SP public key
            .decryptionX509Credentials(c -> c.add(loadSpDecryptionCredential()))
            .build();

        return new InMemoryRelyingPartyRegistrationRepository(okta);
    }

    private Saml2X509Credential loadSpSigningCredential() {
        // Load from Vault or KMS in production
        PrivateKey privateKey = loadPrivateKey("sp-signing-key.pem");
        X509Certificate cert  = loadCertificate("sp-signing-cert.pem");
        return Saml2X509Credential.signing(privateKey, cert);
    }
}
```

### 44.3 SCIM 2.0 — User Provisioning

```python
# Python — SCIM 2.0 API for enterprise user provisioning
from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

# SCIM 2.0 User schema
class ScimName(BaseModel):
    formatted:  Optional[str] = None
    familyName: Optional[str] = None
    givenName:  Optional[str] = None

class ScimEmail(BaseModel):
    value:   str
    type:    str = "work"
    primary: bool = True

class ScimUser(BaseModel):
    schemas:    List[str] = ["urn:ietf:params:scim:schemas:core:2.0:User"]
    id:         Optional[str] = None
    userName:   str
    name:       Optional[ScimName] = None
    emails:     List[ScimEmail] = []
    active:     bool = True
    externalId: Optional[str] = None  # IdP's user ID
    groups:     List[dict] = []

class ScimListResponse(BaseModel):
    schemas:      List[str] = ["urn:ietf:params:scim:api:messages:2.0:ListResponse"]
    totalResults: int
    startIndex:   int = 1
    itemsPerPage: int
    Resources:    List[ScimUser]

app = FastAPI(title="SCIM 2.0 Provider")

@app.get("/scim/v2/Users")
async def list_users(
    filter: Optional[str] = None,
    startIndex: int = 1,
    count: int = 100,
    current_tenant: Tenant = Depends(authenticate_scim_request),
) -> ScimListResponse:
    """
    Supports filter parameter for IdP to check if user exists:
    filter=userName eq "alice@example.com"
    """
    users, total = await UserService.list_scim_users(
        tenant_id=current_tenant.id,
        scim_filter=filter,
        offset=startIndex - 1,
        limit=min(count, 100),  # Cap at 100 per page
    )
    return ScimListResponse(
        totalResults=total,
        startIndex=startIndex,
        itemsPerPage=len(users),
        Resources=[ScimUser.from_db_user(u) for u in users],
    )

@app.post("/scim/v2/Users", status_code=201)
async def create_user(
    scim_user: ScimUser,
    tenant: Tenant = Depends(authenticate_scim_request),
) -> ScimUser:
    """Called by IdP when a new user is assigned to the application"""
    existing = await UserService.find_by_username(scim_user.userName, tenant.id)
    if existing:
        raise HTTPException(409, detail={
            "schemas": ["urn:ietf:params:scim:api:messages:2.0:Error"],
            "detail":  "User already exists",
            "status":  "409",
        })

    user = await UserService.provision_user(
        username=scim_user.userName,
        email=scim_user.emails[0].value if scim_user.emails else None,
        name=scim_user.name,
        tenant_id=tenant.id,
        external_id=scim_user.externalId,
        active=scim_user.active,
    )
    return ScimUser.from_db_user(user)

@app.patch("/scim/v2/Users/{user_id}")
async def patch_user(
    user_id: str,
    patch_request: dict,  # SCIM patch uses a specific operations format
    tenant: Tenant = Depends(authenticate_scim_request),
):
    """Handle deprovisioning (active=false) and attribute updates"""
    operations = patch_request.get("Operations", [])

    for op in operations:
        if op.get("op") == "replace" and "active" in op.get("value", {}):
            if not op["value"]["active"]:
                # User deprovisioned by IdP — revoke all sessions
                await UserService.deprovision_user(user_id, tenant.id)
                await SessionService.revoke_all_sessions(user_id)
                await TokenService.revoke_all_tokens(user_id)
    return {"id": user_id, "active": False}

def authenticate_scim_request(
    authorization: str = Header(None)
) -> Tenant:
    """Authenticate SCIM requests from IdP using Bearer token"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Missing bearer token")
    token = authorization.split(" ")[1]
    return TenantService.find_by_scim_token(token)  # Token issued to IdP
```

---

# PART 16 — NETWORK SECURITY

---

## Chapter 45: Network Security for Application Developers

### 45.1 Security Group and Firewall Design

```hcl
# Terraform — AWS Security Groups with minimal footprint
# Three-tier architecture: ALB → App → DB

# Load balancer: accepts HTTPS from internet only
resource "aws_security_group" "alb" {
  name   = "alb-sg"
  vpc_id = aws_vpc.main.id

  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]  # Internet-facing
    description = "HTTPS from internet"
  }

  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
    description = "HTTP redirect to HTTPS"
  }

  # All outbound to app tier only (not anywhere)
  egress {
    from_port       = 8080
    to_port         = 8080
    protocol        = "tcp"
    security_groups = [aws_security_group.app.id]
    description     = "To app tier"
  }
}

# App tier: accepts only from ALB security group
resource "aws_security_group" "app" {
  name   = "app-sg"
  vpc_id = aws_vpc.main.id

  ingress {
    from_port       = 8080
    to_port         = 8080
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]  # Only from ALB
    description     = "From ALB only"
  }

  # Outbound: to DB only + HTTPS for external APIs
  egress {
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.db.id]
    description     = "To database"
  }
  egress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
    description = "HTTPS to external APIs"
  }
  egress {
    from_port   = 53
    to_port     = 53
    protocol    = "udp"
    cidr_blocks = [aws_vpc.main.cidr_block]
    description = "DNS"
  }
  # No other outbound — prevents data exfiltration via unusual ports
}

# Database tier: accepts only from app tier
resource "aws_security_group" "db" {
  name   = "db-sg"
  vpc_id = aws_vpc.main.id

  ingress {
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.app.id]  # App tier only
    description     = "PostgreSQL from app tier"
  }

  # No outbound traffic at all — database never initiates connections
}
```

### 45.2 DNS Security

```python
# Python — DNS Security: DNSSEC validation and safe DNS resolver usage
import dns.resolver
import dns.rdatatype
import dns.dnssec
import dns.message
import dns.query

class SecureDNSResolver:
    """
    DNS resolver with DNSSEC validation.
    Prevents DNS cache poisoning and spoofing attacks.
    """

    def __init__(self, nameservers: list[str] = None):
        self.resolver = dns.resolver.Resolver()
        # Use DNS over HTTPS or trusted recursive resolvers
        if nameservers:
            self.resolver.nameservers = nameservers
        else:
            # Cloudflare's security-focused DNS (malware/phishing blocking)
            self.resolver.nameservers = ["1.1.1.1", "1.0.0.1"]

        self.resolver.use_edns(0, dns.flags.DO, 1232)  # Enable DNSSEC OK flag

    def resolve_with_dnssec(self, hostname: str, record_type: str = "A") -> list[str]:
        """Resolve hostname with DNSSEC validation"""
        try:
            answers = self.resolver.resolve(hostname, record_type, want_dnssec=True)

            # answers is a tuple: (rrset, rrsig)
            if len(answers.response.answer) < 2:
                raise ValueError(f"No DNSSEC signature for {hostname}")

            rrset = answers.response.answer[0]
            rrsig = answers.response.answer[1]

            # Validate DNSSEC signature
            # In production, use a full DNSSEC chain validation
            return [str(r) for r in answers]

        except dns.resolver.NXDOMAIN:
            raise ValueError(f"Domain does not exist: {hostname}")
        except dns.resolver.NoAnswer:
            raise ValueError(f"No {record_type} record for: {hostname}")
        except dns.exception.DNSException as e:
            raise ValueError(f"DNS resolution failed: {e}")

    def is_safe_hostname(self, hostname: str) -> bool:
        """
        Additional safety checks for hostnames before making HTTP requests.
        Prevents SSRF via DNS rebinding.
        """
        import ipaddress
        import socket

        try:
            # Resolve to IP first
            ip_str = socket.gethostbyname(hostname)
            ip = ipaddress.ip_address(ip_str)

            # Block private/internal ranges
            if ip.is_private or ip.is_loopback or ip.is_link_local:
                return False

            # Block APIPA / metadata ranges
            metadata_ranges = [
                ipaddress.ip_network("169.254.0.0/16"),  # AWS metadata
            ]
            for range_ in metadata_ranges:
                if ip in range_:
                    return False

            return True
        except (socket.gaierror, ValueError):
            return False
```

### 45.3 DDoS Mitigation Patterns

```go
// Go — Multi-layer rate limiting with sliding window algorithm
package ratelimit

import (
    "context"
    "fmt"
    "time"

    "github.com/redis/go-redis/v9"
)

type SlidingWindowRateLimiter struct {
    redis  *redis.Client
    window time.Duration
    limit  int
}

// Sliding window algorithm — more accurate than fixed window
// Prevents the "burst at boundary" attack on fixed window limiters
func (rl *SlidingWindowRateLimiter) Allow(ctx context.Context, key string) (bool, error) {
    now      := time.Now().UnixMilli()
    windowMs := rl.window.Milliseconds()

    pipe := rl.redis.Pipeline()

    // Remove requests outside the window
    pipe.ZRemRangeByScore(ctx, key,
        "0", fmt.Sprintf("%d", now-windowMs))

    // Count remaining
    pipe.ZCard(ctx, key)

    // Add current request with timestamp as score
    pipe.ZAdd(ctx, key, redis.Z{Score: float64(now), Member: fmt.Sprintf("%d", now)})

    // Set expiry on the key
    pipe.Expire(ctx, key, rl.window*2)

    results, err := pipe.Exec(ctx)
    if err != nil {
        return true, err // Fail open (allow) if Redis is down
    }

    count := results[1].(*redis.IntCmd).Val()
    return count < int64(rl.limit), nil
}

// Adaptive rate limiting — tighten limits when under attack
type AdaptiveRateLimiter struct {
    base        *SlidingWindowRateLimiter
    globalLimit int
    globalHits  int64
    mu          sync.Mutex
    lastReset   time.Time
}

func (rl *AdaptiveRateLimiter) Allow(ctx context.Context, key string) (bool, error) {
    rl.mu.Lock()
    // Calculate current system load from global hits
    elapsed := time.Since(rl.lastReset)
    globalRPS := float64(rl.globalHits) / elapsed.Seconds()

    // Reduce per-client limit proportionally when under high load
    multiplier := 1.0
    if globalRPS > float64(rl.globalLimit)*0.8 {  // >80% capacity
        multiplier = 0.5  // Halve per-client limits
    }
    if globalRPS > float64(rl.globalLimit)*0.95 { // >95% capacity
        multiplier = 0.2  // Severe throttling
    }

    rl.globalHits++
    rl.mu.Unlock()

    adjustedLimit := int(float64(rl.base.limit) * multiplier)
    limiter := &SlidingWindowRateLimiter{
        redis:  rl.base.redis,
        window: rl.base.window,
        limit:  adjustedLimit,
    }
    return limiter.Allow(ctx, key)
}
```

---

# PART 17 — COMPLIANCE DEEP DIVE

---

## Chapter 46: SOC 2 Type II — Engineering Requirements

### 46.1 The Five Trust Services Criteria

```
CRITERIA                 ENGINEERING CONTROLS REQUIRED
────────────────────────────────────────────────────────────────────────────────
Security (CC6–CC9)       Access controls, encryption, vulnerability management,
                         incident response, change management, risk management

Availability (A1)        Uptime monitoring, SLA tracking, disaster recovery,
                         backup and restore procedures, capacity planning

Processing Integrity     Input validation, error handling, complete/accurate
(PI1)                    processing records, output verification

Confidentiality (C1)     Data classification, encryption, access controls,
                         data disposal procedures, NDA tracking

Privacy (P1–P8)          GDPR-equivalent controls: consent, data subject rights,
                         data minimization, purpose limitation, retention limits
```

### 46.2 SOC 2 Evidence Collection Automation

```python
# Python — Automated SOC 2 evidence collection
# Auditors require evidence that controls are consistently applied

import boto3
import json
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass

@dataclass
class SOC2Evidence:
    control_id:   str
    control_name: str
    period_start: datetime
    period_end:   datetime
    evidence:     dict
    compliant:    bool

class SOC2EvidenceCollector:
    def __init__(self, aws_region: str = "us-east-1"):
        self.iam  = boto3.client("iam", region_name=aws_region)
        self.s3   = boto3.client("s3", region_name=aws_region)
        self.ec2  = boto3.client("ec2", region_name=aws_region)
        self.guardduty = boto3.client("guardduty", region_name=aws_region)
        self.config_svc = boto3.client("config", region_name=aws_region)

    def cc6_1_logical_access_controls(self) -> SOC2Evidence:
        """CC6.1: Restrict logical access to information assets"""
        evidence = {}

        # Check: MFA enabled for all IAM users
        users = self.iam.list_users()["Users"]
        mfa_devices = {
            device["UserName"]: device
            for device in self.iam.list_virtual_mfa_devices()["VirtualMFADevices"]
            if device.get("User")
        }

        users_without_mfa = [
            u["UserName"] for u in users
            if u["UserName"] not in mfa_devices
            and u.get("PasswordLastUsed")  # Has console access
        ]

        evidence["mfa_enforcement"] = {
            "total_iam_users":     len(users),
            "users_with_mfa":      len(users) - len(users_without_mfa),
            "users_without_mfa":   users_without_mfa,
            "compliant":           len(users_without_mfa) == 0,
        }

        # Check: No root access keys
        root_key_summary = self.iam.get_account_summary()["SummaryMap"]
        evidence["root_access_keys"] = {
            "root_access_key_count": root_key_summary.get("AccountAccessKeysPresent", 0),
            "compliant":             root_key_summary.get("AccountAccessKeysPresent", 0) == 0,
        }

        # Check: Password policy
        try:
            policy = self.iam.get_account_password_policy()["PasswordPolicy"]
            evidence["password_policy"] = {
                "minimum_length":        policy.get("MinimumPasswordLength", 0),
                "requires_uppercase":    policy.get("RequireUppercaseCharacters", False),
                "requires_lowercase":    policy.get("RequireLowercaseCharacters", False),
                "requires_numbers":      policy.get("RequireNumbers", False),
                "requires_symbols":      policy.get("RequireSymbols", False),
                "max_age_days":          policy.get("MaxPasswordAge", 999),
                "prevent_reuse":         policy.get("PasswordReusePrevention", 0),
                "compliant":             (
                    policy.get("MinimumPasswordLength", 0) >= 14 and
                    policy.get("MaxPasswordAge", 999) <= 90 and
                    policy.get("PasswordReusePrevention", 0) >= 12
                ),
            }
        except self.iam.exceptions.NoSuchEntityException:
            evidence["password_policy"] = {"error": "No password policy set", "compliant": False}

        return SOC2Evidence(
            control_id="CC6.1",
            control_name="Logical Access Controls",
            period_start=datetime.now(timezone.utc) - timedelta(days=90),
            period_end=datetime.now(timezone.utc),
            evidence=evidence,
            compliant=all(v.get("compliant", False) for v in evidence.values()),
        )

    def cc7_2_monitoring_for_anomalies(self) -> SOC2Evidence:
        """CC7.2: Monitor system components for anomalies and vulnerabilities"""
        evidence = {}

        # Check: GuardDuty enabled
        detectors = self.guardduty.list_detectors()["DetectorIds"]
        if detectors:
            detector = self.guardduty.get_detector(DetectorId=detectors[0])
            evidence["guardduty"] = {
                "enabled": detector["Status"] == "ENABLED",
                "update_frequency": detector.get("FindingPublishingFrequency"),
                "compliant": detector["Status"] == "ENABLED",
            }
        else:
            evidence["guardduty"] = {"enabled": False, "compliant": False}

        # Check: AWS Config enabled
        recorders = self.config_svc.describe_configuration_recorders()
        evidence["config_recorder"] = {
            "enabled": len(recorders["ConfigurationRecorders"]) > 0,
            "compliant": len(recorders["ConfigurationRecorders"]) > 0,
        }

        return SOC2Evidence(
            control_id="CC7.2",
            control_name="Monitoring and Anomaly Detection",
            period_start=datetime.now(timezone.utc) - timedelta(days=90),
            period_end=datetime.now(timezone.utc),
            evidence=evidence,
            compliant=all(v.get("compliant", False) for v in evidence.values()),
        )

    def generate_audit_report(self) -> dict:
        """Generate a complete SOC 2 evidence report"""
        controls = [
            self.cc6_1_logical_access_controls(),
            self.cc7_2_monitoring_for_anomalies(),
            # Add more control checks...
        ]

        return {
            "report_generated_at": datetime.now(timezone.utc).isoformat(),
            "period": "2024-Q4",
            "controls": [
                {
                    "id":        c.control_id,
                    "name":      c.control_name,
                    "compliant": c.compliant,
                    "evidence":  c.evidence,
                }
                for c in controls
            ],
            "overall_compliant": all(c.compliant for c in controls),
        }
```

---

## Chapter 47: HIPAA Security Rule — Engineering Implementation

### 47.1 HIPAA Technical Safeguards

```python
# Python — HIPAA-compliant PHI (Protected Health Information) handling
import hashlib
import uuid
from dataclasses import dataclass
from enum import Enum
from typing import Optional
from datetime import datetime, timezone

class PHICategory(Enum):
    """HIPAA 18 de-identification safe harbor identifiers"""
    NAME           = "name"
    GEOGRAPHIC     = "geographic"          # Zip codes, addresses
    DATE           = "date"               # Dates related to individual
    PHONE          = "phone"
    FAX            = "fax"
    EMAIL          = "email"
    SSN            = "ssn"
    MRN            = "mrn"               # Medical record number
    HEALTH_PLAN    = "health_plan_number"
    ACCOUNT        = "account_number"
    CERT_LICENSE   = "cert_license"
    VEHICLE        = "vehicle_identifier"
    DEVICE         = "device_identifier"
    WEB_URL        = "web_url"
    IP_ADDRESS     = "ip_address"
    BIOMETRIC      = "biometric"
    PHOTO          = "full_face_photo"
    OTHER          = "other_unique_identifier"

@dataclass
class PHIField:
    category:    PHICategory
    value:       str
    encrypted:   bool = True
    de_identified: bool = False

class HIPAACompliantStorage:
    def __init__(self, encryption_service, audit_logger):
        self.encryption = encryption_service
        self.audit      = audit_logger

    def store_phi(
        self,
        patient_data: dict,
        storing_user_id: str,
        purpose: str,  # Must document the purpose for HIPAA minimum necessary rule
    ) -> str:
        """
        Store PHI with:
        1. Encryption at rest (§164.312(a)(2)(iv))
        2. Audit logging (§164.312(b))
        3. Access controls (§164.312(a)(1))
        """
        # Validate purpose is documented and allowed
        ALLOWED_PURPOSES = {
            "treatment", "payment", "healthcare_operations",
            "required_by_law", "research_with_waiver"
        }
        if purpose not in ALLOWED_PURPOSES:
            raise ValueError(f"PHI storage purpose not permitted: {purpose}")

        # Encrypt each PHI field individually (field-level encryption)
        encrypted_data = {}
        for field_name, value in patient_data.items():
            if value is not None:
                encrypted_data[field_name] = self.encryption.encrypt(
                    str(value).encode(),
                    associated_data=field_name.encode()  # Binds ciphertext to field
                )

        # Generate a de-identification token for research use
        phi_token = str(uuid.uuid4())

        # Audit log: every creation of PHI record
        self.audit.log_phi_event(
            event_type     = "phi_stored",
            user_id        = storing_user_id,
            phi_token      = phi_token,
            fields_stored  = list(patient_data.keys()),
            purpose        = purpose,
            timestamp      = datetime.now(timezone.utc),
        )

        return phi_token  # Return token; caller stores token, not raw data

    def access_phi(
        self,
        phi_token: str,
        accessing_user_id: str,
        fields_needed: list[str],
        purpose: str,
    ) -> dict:
        """
        Access PHI with minimum necessary principle (§164.514(d)):
        Only retrieve the specific fields needed for the stated purpose.
        """
        # Minimum necessary check
        allowed_fields = self._get_allowed_fields_for_purpose(purpose)
        unauthorized_fields = set(fields_needed) - set(allowed_fields)
        if unauthorized_fields:
            raise PermissionError(
                f"Purpose '{purpose}' does not authorize access to: {unauthorized_fields}"
            )

        # Retrieve and decrypt only requested fields
        stored_encrypted = self._retrieve_encrypted(phi_token)
        decrypted = {}
        for field in fields_needed:
            if field in stored_encrypted:
                decrypted[field] = self.encryption.decrypt(
                    stored_encrypted[field],
                    associated_data=field.encode()
                ).decode()

        # Audit log: every access to PHI (§164.312(b))
        self.audit.log_phi_event(
            event_type     = "phi_accessed",
            user_id        = accessing_user_id,
            phi_token      = phi_token,
            fields_accessed = fields_needed,
            purpose        = purpose,
            timestamp      = datetime.now(timezone.utc),
        )

        return decrypted

    def de_identify(self, patient_data: dict) -> dict:
        """
        Safe Harbor de-identification per §164.514(b):
        Remove all 18 PHI identifiers
        """
        REMOVE_FIELDS = {
            "name", "street_address", "city", "zip_code",
            "phone", "fax", "email", "ssn", "mrn",
            "health_plan_number", "account_number",
            "certificate_number", "vehicle_id", "device_id",
            "web_url", "ip_address", "biometric_id", "photo",
            "birth_date", "admission_date", "discharge_date", "death_date"
        }

        de_id = {}
        for key, value in patient_data.items():
            if key in REMOVE_FIELDS:
                continue  # Remove PHI field
            # Generalize dates to year only (safe harbor requirement for ages > 89)
            if key.endswith("_date") and isinstance(value, datetime):
                de_id[key] = value.year  # Only year
            # Generalize zip codes to first 3 digits
            elif key == "zip_code":
                de_id[key] = str(value)[:3] + "XX"
            else:
                de_id[key] = value

        return de_id

    def _get_allowed_fields_for_purpose(self, purpose: str) -> set[str]:
        FIELD_PERMISSIONS = {
            "treatment":          {"name", "mrn", "diagnosis", "medications", "allergies",
                                    "lab_results", "vital_signs", "phone"},
            "payment":            {"name", "dob", "insurance_id", "diagnosis_codes"},
            "healthcare_operations": {"mrn", "diagnosis_codes", "procedure_codes"},
            "research_with_waiver": set(),  # Must request specific approval
        }
        return FIELD_PERMISSIONS.get(purpose, set())
```

---

# PART 18 — ADVANCED SECURITY PATTERNS

---

## Chapter 48: Defense Against Advanced Attack Techniques

### 48.1 Timing Attack Prevention

```rust
// Rust — Constant-time operations to prevent timing side-channels
use subtle::{ConstantTimeEq, ConstantTimeLess};
use zeroize::Zeroize;

// UNSAFE: String comparison exits early on first mismatch
// An attacker can measure response time to guess bytes one at a time
fn verify_token_unsafe(provided: &str, expected: &str) -> bool {
    provided == expected  // Early exit leaks information!
}

// SAFE: Constant-time comparison — takes same time regardless of where mismatch is
fn verify_token_safe(provided: &[u8], expected: &[u8]) -> bool {
    // ConstantTimeEq from the `subtle` crate
    // Always compares ALL bytes, regardless of early mismatch
    bool::from(provided.ct_eq(expected))
}

// For HMAC verification — prevents length extension and timing attacks
use hmac::{Hmac, Mac};
use sha2::Sha256;

fn verify_hmac(key: &[u8], message: &[u8], provided_mac: &[u8]) -> bool {
    let mut mac = Hmac::<Sha256>::new_from_slice(key)
        .expect("HMAC can take key of any size");
    mac.update(message);

    // verify_slice uses constant-time comparison internally
    mac.verify_slice(provided_mac).is_ok()
}

// Sensitive data that zeroes itself when dropped
struct SecretKey {
    key_material: Zeroize<Vec<u8>>,
}

impl Drop for SecretKey {
    fn drop(&mut self) {
        self.key_material.zeroize();
        // Memory is zeroed before deallocation
        // Prevents key recovery from process memory dumps
    }
}
```

```python
# Python — Constant-time string comparison
import hmac

# UNSAFE
def compare_token_unsafe(provided: str, expected: str) -> bool:
    return provided == expected  # Early exit!

# SAFE — hmac.compare_digest is constant-time
def compare_token_safe(provided: str, expected: str) -> bool:
    return hmac.compare_digest(
        provided.encode('utf-8'),
        expected.encode('utf-8')
    )

# ALSO SAFE — but requires same length
import secrets
def compare_bytes_safe(a: bytes, b: bytes) -> bool:
    if len(a) != len(b):
        # Pad to same length before comparing — or return False after constant work
        # Returning immediately on length mismatch leaks length information
        # For tokens: use fixed-length output (SHA-256 digest, etc.)
        return False
    return secrets.compare_digest(a, b)
```

### 48.2 Memory Safety in Go — Common Security Pitfalls

```go
// Go — Memory and concurrency security patterns

package security

import (
    "crypto/rand"
    "sync"
    "unsafe"
)

// ─── Secure memory clearing ────────────────────────────────────────────────
// Go's GC may move objects, so zeroing before GC collection is not guaranteed.
// For sensitive data: use a finalizer and hope, or use OS-level secure memory.

type SecureBytes struct {
    data []byte
    once sync.Once
}

func NewSecureBytes(size int) *SecureBytes {
    b := make([]byte, size)
    rand.Read(b) // Initialize with random (not zero — overwrite with random before clear)
    sb := &SecureBytes{data: b}
    // Register finalizer to zero on GC
    runtime.SetFinalizer(sb, func(s *SecureBytes) {
        s.Destroy()
    })
    return sb
}

func (sb *SecureBytes) Destroy() {
    sb.once.Do(func() {
        // Overwrite with zeros
        for i := range sb.data {
            sb.data[i] = 0
        }
        // Use unsafe to prevent compiler from optimizing away the zeroing
        p := unsafe.Pointer(&sb.data[0])
        for i := 0; i < len(sb.data); i++ {
            *(*byte)(unsafe.Pointer(uintptr(p) + uintptr(i))) = 0
        }
        sb.data = nil
    })
}

// ─── Goroutine leak prevention in security contexts ───────────────────────
// Leaked goroutines can accumulate sensitive data in stack memory

func ProcessSensitiveData(ctx context.Context, data []byte) (result []byte, err error) {
    done := make(chan struct {
        result []byte
        err    error
    }, 1)

    go func() {
        defer func() {
            // Zero sensitive data when goroutine exits
            for i := range data {
                data[i] = 0
            }
        }()

        r, e := doProcessing(data)
        done <- struct{ result []byte; err error }{r, e}
    }()

    select {
    case res := <-done:
        return res.result, res.err
    case <-ctx.Done():
        // Context cancelled — goroutine will finish and clean up
        return nil, ctx.Err()
    }
}
```

### 48.3 Cross-Site Request Forgery (CSRF) — Complete Defense

```typescript
// TypeScript — CSRF protection for both session-based and token-based apps

// ─── Pattern 1: Double-Submit Cookie (stateless CSRF protection) ──────────
// Same-origin policy prevents attacker from reading your cookies
// So if the CSRF token in the cookie matches the one in the header, it's legitimate

function generateCSRFToken(): string {
    return crypto.randomBytes(32).toString('hex');
}

// On every response:
function setCSRFCookie(res: Response): string {
    const token = generateCSRFToken();
    res.cookie('csrf-token', token, {
        httpOnly: false,  // JavaScript must be able to READ this cookie to copy it
        secure:   true,
        sameSite: 'strict',
        path:     '/',
    });
    return token;
}

// CSRF validation middleware
function validateCSRF(req: Request, res: Response, next: NextFunction): void {
    // Skip for GET, HEAD, OPTIONS (safe methods)
    if (['GET', 'HEAD', 'OPTIONS'].includes(req.method)) {
        return next();
    }

    const cookieToken = req.cookies['csrf-token'];
    const headerToken = req.headers['x-csrf-token'] as string
        ?? req.body?._csrf;  // Also accept in request body

    if (!cookieToken || !headerToken) {
        res.status(403).json({ error: 'CSRF token missing' });
        return;
    }

    // Constant-time comparison
    if (!crypto.timingSafeEqual(
        Buffer.from(cookieToken),
        Buffer.from(headerToken)
    )) {
        res.status(403).json({ error: 'CSRF token mismatch' });
        return;
    }

    next();
}

// ─── Pattern 2: SameSite Cookie (modern, simpler) ─────────────────────────
// SameSite=Strict: cookie not sent on cross-origin requests
// Makes CSRF attacks impossible for modern browsers

function setSessionCookie(res: Response, sessionId: string): void {
    res.cookie('session', sessionId, {
        httpOnly: true,    // No JS access
        secure:   true,    // HTTPS only
        sameSite: 'strict', // Not sent on cross-origin requests = CSRF impossible
        path:     '/',
        maxAge:   3600_000,  // 1 hour
    });
}
// With SameSite=Strict, an attacker's page cannot trigger a state change
// because the session cookie is never sent to your server from their page.
```

```java
// Java — Spring Security CSRF with custom token repository
@Configuration
public class CSRFConfig {

    @Bean
    public SecurityFilterChain csrfFilterChain(HttpSecurity http) throws Exception {
        // For server-rendered apps: use CSRF with Lax SameSite + token
        http.csrf(csrf -> csrf
            .csrfTokenRepository(CookieCsrfTokenRepository.withHttpOnlyFalse())
            // Cookie-based: allows SPA to read and include in X-CSRF-TOKEN header
            .sessionAuthenticationStrategy(new NullAuthenticatedSessionStrategy())
        );

        // For REST APIs with JWT: disable CSRF (JWT in Authorization header is
        // already CSRF-safe because attacker cannot read the header via CORS)
        // http.csrf(csrf -> csrf.disable());

        return http.build();
    }
}
```

---

## Chapter 49: Secure Session Management

### 49.1 Session Security Patterns

```python
# Python — Production-grade session management
import secrets
import hashlib
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass

@dataclass
class Session:
    session_id:      str
    user_id:         str
    created_at:      datetime
    last_active_at:  datetime
    absolute_expiry: datetime  # Hard expiry regardless of activity
    ip_address:      str
    user_agent_hash: str       # Hash, not full UA string
    is_revoked:      bool = False

class SecureSessionManager:
    SESSION_COOKIE_NAME     = "__Secure-SessionId"
    SESSION_ID_BYTES        = 32      # 256 bits of entropy
    IDLE_TIMEOUT_MINUTES    = 30      # Session expires after 30min inactivity
    ABSOLUTE_TIMEOUT_HOURS  = 8       # Hard limit: 8 hours regardless of activity

    def __init__(self, store: SessionStore):
        self.store = store

    def create_session(
        self,
        user_id: str,
        ip_address: str,
        user_agent: str,
    ) -> tuple[str, Session]:
        """Create a new session. Returns (session_token, session)."""
        # Generate cryptographically secure session ID
        raw_token    = secrets.token_bytes(self.SESSION_ID_BYTES)
        session_id   = secrets.token_urlsafe(self.SESSION_ID_BYTES)

        # Store hash of token, not token itself
        # If database is breached, attacker cannot use the hash to authenticate
        token_hash = hashlib.sha256(raw_token).hexdigest()

        now = datetime.now(timezone.utc)
        session = Session(
            session_id      = token_hash,    # Store hash
            user_id         = user_id,
            created_at      = now,
            last_active_at  = now,
            absolute_expiry = now + timedelta(hours=self.ABSOLUTE_TIMEOUT_HOURS),
            ip_address      = ip_address,
            user_agent_hash = hashlib.sha256(user_agent.encode()).hexdigest()[:16],
        )

        self.store.save(session)
        return session_id, session  # Return raw token to client

    def validate_session(
        self,
        raw_token: str,
        ip_address: str,
        user_agent: str,
    ) -> Session | None:
        """Validate session and detect anomalies"""
        # Hash the provided token and look up
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        session = self.store.get(token_hash)

        if not session:
            return None

        now = datetime.now(timezone.utc)

        # Check revocation
        if session.is_revoked:
            return None

        # Check absolute expiry
        if now > session.absolute_expiry:
            self.store.delete(token_hash)
            return None

        # Check idle timeout
        idle_threshold = session.last_active_at + timedelta(minutes=self.IDLE_TIMEOUT_MINUTES)
        if now > idle_threshold:
            self.store.delete(token_hash)
            return None

        # Anomaly detection: IP change (optional, strict)
        if session.ip_address != ip_address:
            # Log suspicious IP change — could be legitimate (mobile roaming)
            # or session hijacking. Decide on risk tolerance:
            # Option A: Invalidate session (secure, annoying for mobile)
            # Option B: Require re-auth for sensitive actions (balance)
            self._log_session_anomaly(session.user_id, "ip_change", {
                "original_ip": session.ip_address,
                "new_ip":      ip_address,
            })

        # Refresh last active
        session.last_active_at = now
        self.store.update(session)

        return session

    def revoke_session(self, raw_token: str):
        """Revoke a specific session (logout)"""
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        session = self.store.get(token_hash)
        if session:
            session.is_revoked = True
            self.store.update(session)

    def revoke_all_sessions(self, user_id: str):
        """Revoke all sessions for a user (password change, account compromise)"""
        sessions = self.store.get_by_user(user_id)
        for session in sessions:
            session.is_revoked = True
            self.store.update(session)

    def rotate_session(self, old_token: str) -> str:
        """
        Session rotation after privilege change (login, sudo, etc.)
        Prevents session fixation attacks.
        """
        old_hash = hashlib.sha256(old_token.encode()).hexdigest()
        old_session = self.store.get(old_hash)

        if not old_session:
            raise ValueError("Invalid session")

        # Create new session with same user but new token
        new_token = secrets.token_urlsafe(self.SESSION_ID_BYTES)
        new_hash  = hashlib.sha256(new_token.encode()).hexdigest()

        new_session = Session(
            session_id      = new_hash,
            user_id         = old_session.user_id,
            created_at      = old_session.created_at,  # Preserve original creation
            last_active_at  = datetime.now(timezone.utc),
            absolute_expiry = old_session.absolute_expiry,
            ip_address      = old_session.ip_address,
            user_agent_hash = old_session.user_agent_hash,
        )

        # Atomic: delete old, create new
        self.store.delete(old_hash)
        self.store.save(new_session)

        return new_token

    def set_secure_cookie(self, response, token: str):
        """Set session cookie with all security attributes"""
        response.set_cookie(
            self.SESSION_COOKIE_NAME,
            token,
            max_age     = self.ABSOLUTE_TIMEOUT_HOURS * 3600,
            secure      = True,    # HTTPS only
            httponly    = True,    # No JS access
            samesite    = "Strict", # CSRF protection
            path        = "/",
            domain      = ".example.com",  # Include subdomains
        )
        # __Secure- prefix: browser rejects if not HTTPS + Secure attribute
```

---

## Chapter 50: Security Misconfiguration — The Hidden Risks

### 50.1 Common Misconfiguration Checklist

```yaml
# security-audit.yaml — automated misconfiguration detection
# Run as part of deployment verification

checks:
  - name: "Debug mode disabled in production"
    check: |
      if [ "$NODE_ENV" == "production" ] && grep -r "debug: true\|DEBUG=true" config/; then
        echo "FAIL: Debug mode enabled in production"
        exit 1
      fi

  - name: "Default credentials not present"
    check: |
      # Check for common default admin passwords in config
      if grep -rE "(password|secret|key)\s*[=:]\s*(admin|password|123456|test|default)" \
         config/ src/ --include="*.yaml" --include="*.json"; then
        echo "FAIL: Default credentials found"
        exit 1
      fi

  - name: "Directory listing disabled"
    check: |
      # Test web server returns 403 or 404 for directory without index
      STATUS=$(curl -s -o /dev/null -w "%{http_code}" $BASE_URL/static/)
      if [ "$STATUS" == "200" ]; then
        echo "FAIL: Directory listing enabled at /static/"
        exit 1
      fi

  - name: "Error messages don't expose internals"
    check: |
      # Test 404 response doesn't include stack traces
      RESPONSE=$(curl -s "$BASE_URL/nonexistent-endpoint-12345")
      if echo "$RESPONSE" | grep -qiE "(stack trace|at line|Exception|NullPointer)"; then
        echo "FAIL: Stack trace in error response"
        exit 1
      fi

  - name: "HTTP security headers present"
    check: |
      HEADERS=$(curl -s -I $BASE_URL/health)
      for HEADER in "X-Content-Type-Options" "Strict-Transport-Security" "X-Frame-Options"; do
        if ! echo "$HEADERS" | grep -qi "$HEADER"; then
          echo "FAIL: Missing security header: $HEADER"
          exit 1
        fi
      done

  - name: "Server version not disclosed"
    check: |
      HEADERS=$(curl -s -I $BASE_URL/health)
      if echo "$HEADERS" | grep -qi "^Server:"; then
        echo "FAIL: Server header exposes version: $(echo "$HEADERS" | grep -i "^Server:")"
        exit 1
      fi

  - name: "TLS version is 1.2 minimum"
    check: |
      if openssl s_client -connect $HOST:443 -tls1_1 < /dev/null 2>&1 | grep -q "handshake"; then
        echo "FAIL: TLS 1.1 still accepted"
        exit 1
      fi
```

---

## Chapter 51: The Complete Security Architecture Patterns Reference

### 51.1 Patterns by Use Case

```
PATTERN                         USE CASE                        TRADE-OFF
───────────────────────────────────────────────────────────────────────────────────────
API Key (rotating, hashed)      Machine-to-machine integration  Simple; no user context;
                                Public API with rate limiting    long-lived by default

Short-lived JWT + Refresh       User-facing APIs (mobile, SPA)  Stateless scalability;
Token                           Microservices                    revocation requires
                                                                 token blacklist or
                                                                 short TTL (<15min)

Opaque Session Tokens           Server-rendered web apps         Instant revocation;
(stored in Redis)               Enterprise apps with strict      requires session store
                                logout requirements

mTLS Service-to-Service         Zero-trust microservices         Strongest auth;
                                gRPC between services            certificate management
                                                                 overhead

API Gateway + JWT Validation    Public APIs with multiple         Centralizes auth;
                                upstream services                 single point of failure

PKCE OAuth2 Flow                Third-party OAuth integrations   Most secure for user auth;
                                Mobile and SPA apps              requires auth server

Webhook HMAC Signing            Incoming webhooks from partners  Lightweight; proves sender
                                (Stripe, GitHub, Twilio)         identity without TLS client
                                                                 cert

Signed URL (presigned S3)       Temporary file access           Time-limited; URL not
                                File upload/download             revocable before expiry;
                                                                 opaque to caller
```

### 51.2 Data Security Decision Tree

```
START: Does this data contain PII/PHI/PCI?
          │
    YES ──┤                    NO ──► Standard security practices
          │
          ▼
    Identify data classification:
    REGULATED (HIPAA/PCI) → Apply regulation-specific controls
    SENSITIVE (PII/business-critical) → Encryption at rest + access controls
          │
          ▼
    Encryption at rest?
    REQUIRED ──► AES-256-GCM via KMS/envelope encryption
          │
          ▼
    Field-level or database-level?
    FIELD LEVEL ──► Application-layer encryption (see PIIEncryption class)
                    Use when: compliance requires it, or DB admins shouldn't see data
    DB LEVEL ──────► Transparent Data Encryption (TDE)
                    Use when: compliance allows it; simpler to implement
          │
          ▼
    Access control required?
    YES ──► Row Level Security (RLS) in PostgreSQL
            OR application-layer ownership checks
            BOTH for defense in depth
          │
          ▼
    Audit access?
    YES (HIPAA, PCI, SOC 2) ──► Immutable audit log per access
    GDPR ──────────────────────► Log with purpose documentation
          │
          ▼
    Retention policy?
    DEFINE ──► Automated TTL + deletion job
               Verify deletion cascades (cache, backups, CDN, logs)
```

---

## Final Chapter: The Security-First Engineering Culture

### Building Security into the SDLC

Security cannot be retrofitted. It must be designed in from the first decision. The practices that distinguish security-first engineering teams:

```
PHASE             SECURITY-FIRST PRACTICE              COMMON ANTI-PATTERN
──────────────────────────────────────────────────────────────────────────────
Requirements      Threat model is a requirement         Security is "Phase 2"
                  Security acceptance criteria for
                  every feature

Design            Security architecture review          Architecture is
                  before coding starts                  reviewed after coding

Development       Security linters in IDE               Security checked only
                  (eslint-plugin-security, semgrep)     at PR review
                  Pre-commit hooks for secrets

Code Review       Security-aware reviewers on all       Only author reviews
                  PRs touching auth/crypto/data         security-sensitive code

Testing           Security test suite (injection,       Security tests only in
                  IDOR, broken auth) in unit tests      pen test phase

CI/CD             SAST + dependency scan gate           Manual scan quarterly
                  every commit; fail fast

Deployment        Automated misconfiguration check      Manual checklist
                  post-deploy; infrastructure           (forgotten under pressure)
                  as code security scan

Operations        Real-time security monitoring,        Incident response only
                  alert on auth anomalies,              after customer reports
                  automated incident response

Post-Incident     Blameless postmortem within 48h       Blame assignment;
                  Root cause in code/process             no systemic fix
                  not people
```

### The Security Principles, Revisited with Depth

```
1. ALL USER INPUT IS ADVERSARIAL UNTIL PROVEN SAFE
   Validate. Type-check. Constrain. Encode. Never pass through.

2. AUTHENTICATION ≠ AUTHORIZATION
   Knowing WHO someone is doesn't tell you WHAT they can do.
   Implement both. Test both. Test the boundary between them.

3. ENCRYPTION IS USELESS WITHOUT KEY MANAGEMENT
   The security of encrypted data is only as strong as key access control.
   AES-256 with a hard-coded key offers almost no protection.

4. SECRETS HAVE A LIFECYCLE
   Generate. Rotate. Audit access. Revoke. Never hard-code.

5. EVERY DEPENDENCY IS YOUR CODE
   npm install is running code from thousands of strangers.
   Audit. Pin. Monitor. Verify provenance.

6. YOUR LOGS ARE A SECURITY ASSET AND A SECURITY LIABILITY
   Log enough to detect and investigate incidents.
   Log nothing that would make a breach worse.

7. SECURITY TESTS ARE FIRST-CLASS TESTS
   An auth bypass that passes unit tests is a shipped vulnerability.
   Test the negative cases as rigorously as the happy path.

8. COMPLIANCE IS THE FLOOR, NOT THE CEILING
   PCI DSS, HIPAA, SOC 2 are minimum requirements.
   A compliant system can still be trivially breached.
   Security thinking extends far beyond checkbox compliance.

9. THE ADVERSARY ADAPTS
   AI systems, fraud detection, and anomaly detectors all face
   adversaries who learn. Build ongoing adversarial evaluation,
   not one-time pre-deployment checks.

10. SECURITY IS A PROPERTY OF THE SYSTEM, NOT A COMPONENT
    You cannot add a security box at the perimeter and call yourself secure.
    Security emerges from the composition of every decision:
    language choice, framework defaults, infrastructure configuration,
    deployment practices, team culture, incident response capability.
    It requires sustained engineering discipline, not a point-in-time product purchase.
```

---

*This is Part 3 and the conclusion of the Developer's Cybersecurity Mastery handbook. Covered: Mobile security (iOS Keychain/Biometrics/Certificate Pinning, Android Keystore/Biometric/Network Security Config, React Native), IoT security (MQTT with mTLS/HMAC, secure firmware update in C with ECDSA), Enterprise IAM (OAuth 2.1 Authorization Server, SAML 2.0, SCIM 2.0), Network security (security groups, DNS security, DDoS mitigation with sliding window rate limiting), SOC 2 evidence automation, HIPAA PHI handling with field-level encryption and minimum necessary principle, advanced patterns (timing attack prevention in Rust/Python/Go, memory safety, CSRF double-submit), secure session management with token hashing and anomaly detection, misconfiguration detection, comprehensive security architecture patterns, and the security-first engineering culture framework.*

---

## Complete Guide — Total Coverage Summary

```
PART 1:  Foundations, Threat Modeling, CIA Triad, Kill Chain, MITRE ATT&CK
PART 2:  Authentication, JWT security, OAuth 2.0, PKCE, Password hashing
PART 3:  Cryptography: AES-GCM, RSA, ECC, TLS 1.3, Envelope Encryption
PART 4:  OWASP Top 10: SQLi, XSS, SSRF, IDOR, Command Injection
PART 5:  Secure Coding: Java, Python, Go, Rust, TypeScript
PART 6:  Security Headers, CORS, Secrets Management, SAST in CI
PART 7:  API Security: REST, GraphQL, gRPC, WebSocket
PART 8:  Cloud Security: AWS IAM, S3, Terraform, Privilege Escalation
PART 9:  Container Security: Docker, Kubernetes RBAC, Network Policies, OPA
PART 10: DevSecOps: SAST, DAST, Dependency Scan, SBOM, Signing, SLSA
PART 11: AI Security: Prompt Injection, RAG Poisoning, Agent Sandboxing
PART 12: Zero Trust: Istio mTLS, Token Validation, Risk Scoring
PART 13: Database Security: RLS, Column Encryption, Audit Logging
PART 14: Mobile: iOS Keychain, Android Keystore, React Native, Certificate Pinning
PART 15: IoT: MQTT/mTLS, Firmware Verification, Embedded C security
PART 16: Enterprise IAM: OAuth Server, SAML 2.0, SCIM 2.0
PART 17: Network: Security Groups, DNS Security, DDoS Mitigation
PART 18: Compliance: SOC 2 automation, HIPAA PHI handling, PCI DSS
PART 19: Advanced: Timing Attacks, Memory Safety, CSRF, Session Management
PART 20: Security Architecture Patterns, Decision Trees, Engineering Culture
```
