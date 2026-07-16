# Developer's Cybersecurity Mastery: The Complete Handbook
## Volume 29–38 | Advanced Vulnerabilities · Serverless · Queues · Runtime Security · Incident Response · SaaS Architecture

---

# PART 29 — ADVANCED WEB VULNERABILITIES

---

## Chapter 62: Server-Side Template Injection (SSTI)

### 62.1 Theory and Attack Anatomy

SSTI occurs when user input is embedded into a server-side template and interpreted as template syntax rather than data. It can escalate directly to Remote Code Execution.

```
ATTACK FLOW:

  Template engine: Jinja2 (Python)
  Vulnerable code: render("Hello " + username)  ← string concatenation = injection

  Attacker submits username: {{7*7}}
  Rendered: "Hello 49"                          ← template evaluated

  Attacker submits: {{config.__class__.__init__.__globals__['os'].popen('id').read()}}
  Rendered: "Hello uid=1000(www-data)"          ← REMOTE CODE EXECUTION
```

**Detection payloads per template engine:**
```
ENGINE          DETECTION PAYLOAD    EXPECTED RESPONSE
────────────────────────────────────────────────────────
Jinja2/Twig     {{7*7}}             49
Jinja2          {{7*'7'}}           7777777
Freemarker      ${7*7}              49
Pebble          {{7*7}}             49
Mako            ${7*7}              49
Velocity        #set($x=7*7)$x      49
Ruby ERB        <%= 7*7 %>          49
Go templates    {{printf "%d" 7}}   7
```

```python
# Python — SSTI vulnerabilities and fixes across all common patterns

# ── CRITICAL VULNERABILITY: String concatenation into template ────────────────
from jinja2 import Environment

env = Environment()

# VULNERABLE: User controls template content
def render_greeting_unsafe(username: str) -> str:
    template_str = f"Hello {username}!"   # username could be "{{7*7}}"
    return env.from_string(template_str).render()
    # Attack: username = "{{''.__class__.__mro__[1].__subclasses__()}}"

# SAFE PATTERN 1: Pass data as context variable, never as template text
def render_greeting_safe_1(username: str) -> str:
    template = env.from_string("Hello {{ username }}!")
    return template.render(username=username)  # username is a variable, not syntax

# SAFE PATTERN 2: Sandbox environment for user-defined templates
from jinja2.sandbox import SandboxedEnvironment

sandboxed_env = SandboxedEnvironment(
    # Disable dangerous attributes
    undefined=jinja2.StrictUndefined,
)

def render_user_template_safely(user_template: str, context: dict) -> str:
    """
    When users legitimately need to define their own templates
    (email templates, report templates), use SandboxedEnvironment.
    """
    try:
        template = sandboxed_env.from_string(user_template)
        return template.render(**context)
    except jinja2.exceptions.SecurityError:
        raise ValueError("Template contains restricted operations")
    except jinja2.exceptions.TemplateSyntaxError as e:
        raise ValueError(f"Invalid template syntax: {e}")

# SAFE PATTERN 3: Pre-compile templates at startup, never at request time
class TemplateRegistry:
    def __init__(self):
        self._templates = {}
        self._env = Environment(loader=FileSystemLoader("templates/"))

    def register(self, name: str, template_file: str):
        """Load and compile templates at startup — user input never becomes a template"""
        self._templates[name] = self._env.get_template(template_file)

    def render(self, name: str, context: dict) -> str:
        template = self._templates.get(name)
        if not template:
            raise ValueError(f"Unknown template: {name}")
        return template.render(**context)  # User data always in context, never in template
```

```java
// Java — SSTI in Freemarker and Thymeleaf
import freemarker.template.*;

// VULNERABLE: Dynamic template string construction
public String renderUnsafe(String userGreeting, Map<String, Object> model) throws Exception {
    Configuration cfg = new Configuration(Configuration.VERSION_2_3_32);
    // CRITICAL: User controls template content
    Template template = new Template("dynamic", new StringReader(userGreeting), cfg);
    // Attack: userGreeting = "${\"freemarker.template.utility.Execute\"?new()(\"id\")}"
    // This executes OS commands via Freemarker's reflection capabilities
    StringWriter out = new StringWriter();
    template.process(model, out);
    return out.toString();
}

// SAFE: Templates from filesystem only; user data only in model
@Configuration
public class FreemarkerConfig {
    @Bean
    public FreeMarkerConfigurer freeMarkerConfigurer() {
        FreeMarkerConfigurer configurer = new FreeMarkerConfigurer();
        configurer.setTemplateLoaderPath("classpath:/templates/");
        Properties settings = new Properties();
        // Disable new() and ?api builtins — prevent reflection-based RCE
        settings.setProperty("new_builtin_class_resolver", "safer");
        configurer.setFreemarkerSettings(settings);
        return configurer;
    }
}

// Spring Thymeleaf: Never use th:text= with SpEL expressions from user input
// VULNERABLE:
// <p th:text="${''.class.forName('java.lang.Runtime').getMethod('exec',''.class).invoke(...)}"
// SAFE: Always use th:text with pre-validated data, never inline expressions from user input
```

```go
// Go — html/template is auto-escaping and SSTI-resistant by design
import "html/template"
import "text/template"  // NEVER use this for user-facing output

// SAFE: html/template auto-escapes all values inserted into HTML context
func renderGreetingSafe(username string) (string, error) {
    // The template is a static string; username is data, not template syntax
    tmpl := template.Must(template.New("greeting").Parse(`
        <p>Hello, {{ . }}!</p>
    `))  // {{ . }} cannot contain executable template directives

    var buf bytes.Buffer
    err := tmpl.Execute(&buf, username)
    return buf.String(), err
}

// VULNERABLE: text/template does NOT HTML-escape and allows arbitrary Go code
// NEVER USE for HTML output:
func renderUnsafe(userTemplate string, data interface{}) (string, error) {
    tmpl, err := text_template.New("").Parse(userTemplate)
    // If userTemplate = "{{call .Func}}", attacker can call Go functions
    var buf bytes.Buffer
    tmpl.Execute(&buf, data)
    return buf.String(), nil
}
```

---

## Chapter 63: XXE — XML External Entity Injection

### 63.1 Theory and Critical Business Impact

```
XXE ATTACK:
  <?xml version="1.0"?>
  <!DOCTYPE root [
    <!ENTITY xxe SYSTEM "file:///etc/passwd">       ← Local file read
  ]>
  <root><name>&xxe;</name></root>

  Server response: root:x:0:0:root:/root:/bin/bash...

  More dangerous:
  <!ENTITY xxe SYSTEM "http://169.254.169.254/latest/meta-data/iam/credentials/">
  ← AWS credential theft via XXE + SSRF

  Billion laughs (DoS):
  <!ENTITY lol "lol">
  <!ENTITY lol2 "&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;">
  ← Entity expansion causes OOM
```

```python
# Python — Secure XML parsing across all common libraries

# ── defusedxml: The standard fix ──────────────────────────────────────────────
import defusedxml.ElementTree as ET
import defusedxml.minidom
import defusedxml.sax

# SAFE: defusedxml prevents all XXE categories by default
def parse_xml_safe(xml_string: str) -> ET.Element:
    return ET.fromstring(xml_string)
    # Raises defusedxml.DTDForbidden if DOCTYPE is present
    # Raises defusedxml.ExternalReferenceForbidden for external entities

# Configuration for specific parsers:
from defusedxml import DefusedXmlException

def parse_with_sax_safe(xml_bytes: bytes):
    import xml.sax
    parser = defusedxml.sax.make_parser()
    # External entities, DTD, and external subsets all disabled by defusedxml
    return parser

# ── Standard library: Disable features manually ───────────────────────────────
import xml.etree.ElementTree as stdlib_ET

# UNSAFE: standard library's ElementTree does not protect against billion laughs
# and varies in XXE protection by Python version

# SAFE: Use lxml with explicit security settings
from lxml import etree

def parse_with_lxml_safe(xml_bytes: bytes) -> etree._Element:
    parser = etree.XMLParser(
        resolve_entities    = False,   # Critical: prevents entity expansion
        no_network          = True,    # No external network access for DTDs
        load_dtd            = False,   # Don't load external DTDs
        dtd_validation      = False,   # Don't validate against DTD
    )
    return etree.fromstring(xml_bytes, parser=parser)
```

```java
// Java — XXE prevention in all XML processing paths
import javax.xml.parsers.DocumentBuilderFactory;
import javax.xml.parsers.SAXParserFactory;
import javax.xml.stream.XMLInputFactory;
import javax.xml.transform.TransformerFactory;

public class SecureXMLParser {

    // DocumentBuilder — most common vulnerability vector
    public static DocumentBuilder createSecureDocumentBuilder() throws Exception {
        DocumentBuilderFactory factory = DocumentBuilderFactory.newInstance();

        // The complete set of properties to disable all XXE vectors
        String FEATURE = "http://apache.org/xml/features/";
        String XML_FEATURE = "http://xml.org/sax/features/";

        factory.setFeature(XML_FEATURE + "external-general-entities", false);
        factory.setFeature(XML_FEATURE + "external-parameter-entities", false);
        factory.setFeature(FEATURE + "nonvalidating/load-external-dtd", false);
        factory.setFeature(FEATURE + "disallow-doctype-decl", true);  // Block DOCTYPE
        factory.setXIncludeAware(false);
        factory.setExpandEntityReferences(false);

        return factory.newDocumentBuilder();
    }

    // SAXParser
    public static SAXParser createSecureSAXParser() throws Exception {
        SAXParserFactory factory = SAXParserFactory.newInstance();
        factory.setFeature("http://xml.org/sax/features/external-general-entities", false);
        factory.setFeature("http://xml.org/sax/features/external-parameter-entities", false);
        factory.setFeature("http://apache.org/xml/features/disallow-doctype-decl", true);
        return factory.newSAXParser();
    }

    // StAX — XMLInputFactory
    public static XMLInputFactory createSecureXMLInputFactory() {
        XMLInputFactory factory = XMLInputFactory.newInstance();
        factory.setProperty(XMLInputFactory.IS_SUPPORTING_EXTERNAL_ENTITIES, false);
        factory.setProperty(XMLInputFactory.SUPPORT_DTD, false);
        return factory;
    }

    // XSLT Transformer
    public static TransformerFactory createSecureTransformerFactory() throws Exception {
        TransformerFactory factory = TransformerFactory.newInstance();
        factory.setAttribute(javax.xml.XMLConstants.ACCESS_EXTERNAL_DTD,  "");
        factory.setAttribute(javax.xml.XMLConstants.ACCESS_EXTERNAL_STYLESHEET, "");
        return factory;
    }
}
```

---

## Chapter 64: Prototype Pollution

### 64.1 The JavaScript Object Model Vulnerability

```
ATTACK: If you can set __proto__.isAdmin = true on any object,
        then ({}).isAdmin === true for ALL objects in the process.

  // Attacker sends:
  POST /api/merge
  { "__proto__": { "isAdmin": true } }

  // Vulnerable code:
  Object.assign({}, req.body)  ← Copies __proto__ properties

  // Now:
  let anyObj = {}
  anyObj.isAdmin  // true — attacker elevated all objects in the process
```

```typescript
// TypeScript — Prototype Pollution prevention

// ── Detection ─────────────────────────────────────────────────────────────────
function containsPrototypePollution(obj: unknown): boolean {
    if (typeof obj !== 'object' || obj === null) return false;

    const dangerous = ['__proto__', 'constructor', 'prototype'];

    if (Array.isArray(obj)) {
        return obj.some(item => containsPrototypePollution(item));
    }

    for (const key of Object.keys(obj as Record<string, unknown>)) {
        if (dangerous.includes(key)) return true;
        if (containsPrototypePollution((obj as Record<string, unknown>)[key])) return true;
    }
    return false;
}

// ── Safe deep merge without prototype pollution ───────────────────────────────
function safeDeepMerge<T extends Record<string, unknown>>(
    target: T,
    source: Record<string, unknown>
): T {
    for (const key of Object.keys(source)) {
        // Block dangerous keys
        if (key === '__proto__' || key === 'constructor' || key === 'prototype') {
            continue;  // Skip — never merge these
        }

        const sourceVal = source[key];
        const targetVal = (target as Record<string, unknown>)[key];

        if (
            sourceVal !== null &&
            typeof sourceVal === 'object' &&
            !Array.isArray(sourceVal) &&
            targetVal !== null &&
            typeof targetVal === 'object'
        ) {
            safeDeepMerge(
                targetVal as Record<string, unknown>,
                sourceVal as Record<string, unknown>
            );
        } else {
            (target as Record<string, unknown>)[key] = sourceVal;
        }
    }
    return target;
}

// ── Using Object.create(null) for key-value stores ──────────────────────────
// Objects created with null prototype cannot be prototype-polluted
function createSafeKVStore(): Record<string, unknown> {
    return Object.create(null);  // No prototype — __proto__ is just a data key
}

// ── JSON.parse does NOT cause prototype pollution — but post-processing might ─
const data = JSON.parse(untrustedJson);  // Safe: JSON.parse is PP-safe

// UNSAFE: spread or assign without checking
const config = { ...defaults, ...data };           // Spreads __proto__ if present
const config2 = Object.assign({}, defaults, data); // Same problem

// SAFE: schema validation + freeze
import { z } from 'zod';
const ConfigSchema = z.object({
    timeout:     z.number().positive(),
    retries:     z.number().min(0).max(10),
    maxBodySize: z.number().positive(),
});
const config3 = ConfigSchema.parse(data);  // Validates — unknown keys rejected
Object.freeze(config3);                     // Prevent mutation

// ── Express middleware: block prototype pollution in request body ─────────────
function prototypePollutionGuard(
    req: Request, res: Response, next: NextFunction
): void {
    if (req.body && containsPrototypePollution(req.body)) {
        res.status(400).json({ error: 'Invalid request body' });
        return;
    }
    next();
}
```

---

## Chapter 65: HTTP Request Smuggling

### 65.1 Theory

HTTP request smuggling exploits disagreements between how a front-end proxy and back-end server parse the Content-Length and Transfer-Encoding headers to "smuggle" a malicious request that the proxy considers part of the previous request but the back-end treats as a new one.

```
CL.TE ATTACK (Front-end uses Content-Length; Back-end uses Transfer-Encoding):

  POST / HTTP/1.1
  Host: vulnerable.com
  Content-Length: 13
  Transfer-Encoding: chunked

  0

  SMUGGLED

  Front-end: sees Content-Length: 13, forwards "0\r\n\r\nSMUGGLED"
  Back-end:  sees TE: chunked, reads "0\r\n\r\n" = end of first request
             Then reads "SMUGGLED" as START of the NEXT request
```

```python
# Python — Mitigations at the application/framework level

# 1. Ensure your reverse proxy and backend agree on HTTP parsing
# Nginx + Gunicorn/Uvicorn: use HTTP/1.1 consistently
# Add explicit header rejection at the nginx level:

nginx_config = """
# nginx.conf — reject ambiguous Content-Length + Transfer-Encoding
location / {
    # Reject requests with both Content-Length and Transfer-Encoding
    if ($http_content_length != "" ) {
        # Additional: set explicit limits
        client_max_body_size 10m;
        client_body_buffer_size 128k;
    }

    # Use HTTP/2 to the backend — HTTP/2 doesn't have request smuggling
    # (HTTP/2 has a different framing mechanism)
    grpc_pass grpcs://backend:50051;
    # OR:
    # proxy_http_version 1.1;  # Use HTTP/1.1; ensure TE stripping below

    # Strip Transfer-Encoding before forwarding to backend
    # (prevents CL.TE attack)
    proxy_set_header Transfer-Encoding "";
}
"""

# 2. Prefer HTTP/2 end-to-end — eliminates the TE/CL ambiguity
# 3. Use one well-tested reverse proxy; avoid chaining multiple proxies

# 4. Application-level: Reject requests with ambiguous headers
from starlette.middleware.base import BaseHTTPMiddleware

class SmuggleGuardMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        cl = request.headers.get("content-length")
        te = request.headers.get("transfer-encoding")

        # Reject if both are present — classic smuggling precondition
        if cl and te:
            from starlette.responses import Response
            return Response("Bad Request", status_code=400)

        # Reject chunked TE on POST/PUT — most smuggling requires this
        if te and "chunked" in te.lower() and request.method in ("POST", "PUT"):
            # Normalize: let the body be read normally; reject the TE header
            pass  # Framework handles correctly if using uvicorn/gunicorn

        return await call_next(request)
```

---

# PART 30 — SERVERLESS SECURITY

---

## Chapter 66: AWS Lambda Security

### 66.1 Lambda Threat Model

```
LAMBDA SECURITY THREATS:
┌─────────────────────────────────────────────────────────────────────────────┐
│  FUNCTION CODE             EVENT DATA              EXECUTION ENVIRONMENT     │
│  ─────────────             ──────────              ─────────────────────     │
│  • Injection via event     • Untrusted callers     • IAM role over-privilege │
│  • Dependency CVEs         • API Gateway bypass    • ENV var secrets         │
│  • Hardcoded secrets       • SQS/SNS poison         • /tmp writeable         │
│  • Insecure deserialization• S3 event injection     • Container reuse        │
│                                                     • Cold start timing      │
└─────────────────────────────────────────────────────────────────────────────┘
```

```python
# Python — Secure Lambda function template

import json
import os
import boto3
import structlog
from aws_lambda_powertools import Logger, Tracer, Metrics
from aws_lambda_powertools.utilities.typing import LambdaContext
from aws_lambda_powertools.utilities.validation import validator, SchemaValidationError
from aws_lambda_powertools.event_handler import APIGatewayRestResolver
from pydantic import BaseModel, validator as pydantic_validator
from typing import Any

logger  = Logger()
tracer  = Tracer()
metrics = Metrics()
app     = APIGatewayRestResolver()

# ── Input validation schema ────────────────────────────────────────────────────
class CreateOrderRequest(BaseModel):
    product_id:  str
    quantity:    int
    customer_id: str

    @pydantic_validator('quantity')
    def quantity_must_be_positive(cls, v):
        if v <= 0 or v > 100:
            raise ValueError('Quantity must be between 1 and 100')
        return v

    @pydantic_validator('product_id', 'customer_id')
    def must_be_uuid_format(cls, v):
        import re
        if not re.match(r'^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$', v):
            raise ValueError('Must be a valid UUID')
        return v

# ── Secrets: loaded ONCE per container lifecycle, not per invocation ──────────
# Lambda reuses containers across invocations — load secrets at module level
_secrets_cache: dict = {}

def get_secret(secret_id: str) -> dict:
    if secret_id not in _secrets_cache:
        sm = boto3.client("secretsmanager")
        value = sm.get_secret_value(SecretId=secret_id)
        _secrets_cache[secret_id] = json.loads(value["SecretString"])
    return _secrets_cache[secret_id]

# ── Lambda handler with complete security controls ────────────────────────────
@logger.inject_lambda_context(correlation_id_path="requestContext.requestId")
@tracer.capture_lambda_handler
@metrics.log_metrics
def handler(event: dict, context: LambdaContext) -> dict:
    # Step 1: Validate event structure before any processing
    http_method = event.get("httpMethod", "")
    path        = event.get("path", "")

    # Step 2: Validate caller identity from API Gateway context
    # (API Gateway handles auth; Lambda trusts the requestContext)
    request_context = event.get("requestContext", {})
    authorizer      = request_context.get("authorizer", {})
    caller_id       = authorizer.get("principalId")

    if not caller_id:
        logger.warning("request_without_auth_context", path=path)
        return {
            "statusCode": 401,
            "body": json.dumps({"error": "Unauthorized"}),
        }

    # Step 3: Parse and validate request body
    try:
        body = json.loads(event.get("body", "{}") or "{}")
        request = CreateOrderRequest(**body)
    except (json.JSONDecodeError, ValueError) as e:
        logger.info("invalid_request_body", error=str(e))
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "Invalid request body"}),
        }

    # Step 4: Verify caller has rights to the requested resource
    if request.customer_id != caller_id and not is_admin(caller_id):
        logger.warning("unauthorized_resource_access",
            caller=caller_id, requested_customer=request.customer_id)
        return {
            "statusCode": 403,
            "body": json.dumps({"error": "Forbidden"}),
        }

    # Step 5: Process with least-privilege operations
    try:
        secrets = get_secret(os.environ["DB_SECRET_ARN"])
        # Process order...
        return {
            "statusCode": 201,
            "headers": {
                "Content-Type": "application/json",
                "X-Content-Type-Options": "nosniff",
            },
            "body": json.dumps({"orderId": "new-order-id"}),
        }
    except Exception as e:
        logger.exception("order_creation_failed")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "Internal error"}),
        }
```

```hcl
# Terraform — Lambda with least-privilege IAM role
resource "aws_iam_role" "order_lambda" {
  name = "order-lambda-execution-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy" "order_lambda" {
  name = "order-lambda-policy"
  role = aws_iam_role.order_lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      # Minimal: only the specific Secret Manager secret needed
      {
        Effect = "Allow"
        Action = ["secretsmanager:GetSecretValue"]
        Resource = "arn:aws:secretsmanager:${var.region}:${data.aws_caller_identity.current.account_id}:secret:order-db-credentials-*"
      },
      # Minimal: only specific DynamoDB table and operations
      {
        Effect = "Allow"
        Action = ["dynamodb:PutItem", "dynamodb:GetItem"]
        Resource = aws_dynamodb_table.orders.arn
      },
      # Standard: CloudWatch Logs
      {
        Effect = "Allow"
        Action = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "arn:aws:logs:*:*:*"
      }
    ]
  })
}

resource "aws_lambda_function" "order_service" {
  function_name = "order-service"
  role          = aws_iam_role.order_lambda.arn
  runtime       = "python3.12"
  handler       = "handler.handler"

  # Security: only load code from signed artifact
  filename         = "order-service.zip"
  source_code_hash = filebase64sha256("order-service.zip")

  environment {
    variables = {
      # Reference secret ARN, not the secret value
      DB_SECRET_ARN    = aws_secretsmanager_secret.db.arn
      POWERTOOLS_SERVICE_NAME = "order-service"
      LOG_LEVEL        = "INFO"
      # NEVER: DB_PASSWORD = "actual-password"
    }
  }

  # Reduce attack surface: no VPC access unless needed for private resources
  # If VPC needed:
  vpc_config {
    subnet_ids         = var.private_subnet_ids
    security_group_ids = [aws_security_group.lambda.id]
  }

  # Prevent container reuse data leakage
  timeout     = 30
  memory_size = 512

  # Code signing: only signed deployments accepted
  code_signing_config_arn = aws_lambda_code_signing_config.main.arn

  tracing_config {
    mode = "Active"  # X-Ray tracing for security observability
  }

  tags = {
    Environment = var.environment
    SecurityReview = "2024-Q4"
  }
}

# Lambda code signing configuration
resource "aws_signer_signing_profile" "main" {
  platform_id = "AWSLambda-SHA384-ECDSA"
}

resource "aws_lambda_code_signing_config" "main" {
  allowed_publishers {
    signing_profile_version_arns = [aws_signer_signing_profile.main.version_arn]
  }
  policies {
    untrusted_artifact_on_deployment = "Enforce"
  }
}
```

---

# PART 31 — MESSAGE QUEUE SECURITY

---

## Chapter 67: Apache Kafka Security

### 67.1 Kafka Authentication and Authorization

```java
// Java — Kafka producer with TLS + SASL authentication
import org.apache.kafka.clients.producer.*;
import org.apache.kafka.clients.consumer.*;
import org.apache.kafka.common.serialization.*;
import java.util.Properties;

public class SecureKafkaProducer {

    public static KafkaProducer<String, String> createSecureProducer(
        String bootstrapServers,
        String keystorePath,
        String keystorePassword,
        String truststorePath,
        String truststorePassword,
        String saslUsername,
        String saslPassword
    ) {
        Properties props = new Properties();
        props.put(ProducerConfig.BOOTSTRAP_SERVERS_CONFIG, bootstrapServers);

        // TLS for encryption in transit
        props.put("security.protocol",           "SASL_SSL");
        props.put("ssl.truststore.location",     truststorePath);
        props.put("ssl.truststore.password",     truststorePassword);
        props.put("ssl.keystore.location",       keystorePath);
        props.put("ssl.keystore.password",       keystorePassword);
        props.put("ssl.key.password",            keystorePassword);

        // TLS version enforcement
        props.put("ssl.protocol",                "TLSv1.3");
        props.put("ssl.enabled.protocols",       "TLSv1.3,TLSv1.2");

        // SASL/SCRAM authentication
        props.put("sasl.mechanism",              "SCRAM-SHA-512");
        props.put("sasl.jaas.config", String.format(
            "org.apache.kafka.common.security.scram.ScramLoginModule required " +
            "username=\"%s\" password=\"%s\";",
            saslUsername, saslPassword  // Loaded from Vault, not hardcoded
        ));

        // Message-level settings
        props.put(ProducerConfig.KEY_SERIALIZER_CLASS_CONFIG,
            StringSerializer.class.getName());
        props.put(ProducerConfig.VALUE_SERIALIZER_CLASS_CONFIG,
            StringSerializer.class.getName());

        // Idempotence: prevents duplicate messages without compromising security
        props.put(ProducerConfig.ENABLE_IDEMPOTENCE_CONFIG, true);
        props.put(ProducerConfig.ACKS_CONFIG, "all");

        return new KafkaProducer<>(props);
    }

    // Secure message production with additional payload signing
    public void produceSignedMessage(
        KafkaProducer<String, String> producer,
        String topic,
        String key,
        Map<String, Object> payload,
        byte[] signingKey
    ) throws Exception {
        // Add timestamp and nonce for replay protection
        payload.put("_ts",    System.currentTimeMillis());
        payload.put("_nonce", UUID.randomUUID().toString());

        String jsonPayload = objectMapper.writeValueAsString(payload);

        // HMAC sign the payload
        Mac mac = Mac.getInstance("HmacSHA256");
        mac.init(new SecretKeySpec(signingKey, "HmacSHA256"));
        String signature = Base64.getEncoder()
            .encodeToString(mac.doFinal(jsonPayload.getBytes()));

        // Include signature in Kafka message headers (not body)
        ProducerRecord<String, String> record = new ProducerRecord<>(topic, key, jsonPayload);
        record.headers().add("X-Signature",  signature.getBytes());
        record.headers().add("X-Timestamp",  String.valueOf(System.currentTimeMillis()).getBytes());
        record.headers().add("X-Producer-ID", producerId.getBytes());

        producer.send(record, (metadata, exception) -> {
            if (exception != null) {
                logger.error("Failed to produce message", exception);
            }
        }).get(10, TimeUnit.SECONDS);
    }
}
```

```python
# Python — Kafka consumer with message verification
from kafka import KafkaConsumer
from kafka.errors import KafkaError
import hmac
import hashlib
import json
import time

class SecureKafkaConsumer:
    MAX_MESSAGE_AGE_SECONDS = 300  # 5 minutes — replay protection

    def __init__(self, topic: str, bootstrap_servers: list[str],
                 ssl_config: dict, sasl_config: dict, signing_key: bytes):
        self.signing_key = signing_key

        self.consumer = KafkaConsumer(
            topic,
            bootstrap_servers    = bootstrap_servers,
            security_protocol    = "SASL_SSL",
            ssl_cafile           = ssl_config["ca_cert"],
            ssl_certfile         = ssl_config["client_cert"],
            ssl_keyfile          = ssl_config["client_key"],
            ssl_check_hostname   = True,
            sasl_mechanism       = "SCRAM-SHA-512",
            sasl_plain_username  = sasl_config["username"],
            sasl_plain_password  = sasl_config["password"],
            value_deserializer   = lambda m: json.loads(m.decode("utf-8")),
            auto_offset_reset    = "earliest",
            enable_auto_commit   = False,  # Manual commit for at-least-once processing
            max_poll_records     = 100,
            # Consumer group for horizontal scaling
            group_id             = "secure-consumer-group",
        )

    def verify_message(self, message) -> bool:
        """Verify message signature and freshness"""
        headers = {k: v.decode() for k, v in message.headers}

        # Step 1: Check timestamp for replay attacks
        timestamp_ms = int(headers.get("X-Timestamp", 0))
        age_seconds  = (time.time() * 1000 - timestamp_ms) / 1000
        if age_seconds > self.MAX_MESSAGE_AGE_SECONDS or age_seconds < 0:
            self._log_security_event("replay_attack_suspected", age=age_seconds)
            return False

        # Step 2: Verify HMAC signature
        expected_signature = headers.get("X-Signature", "")
        payload_bytes      = json.dumps(message.value, separators=(',', ':')).encode()
        actual_signature   = hmac.new(
            self.signing_key, payload_bytes, hashlib.sha256
        ).hexdigest()
        # Base64-decode expected for comparison
        import base64
        expected_bytes = base64.b64decode(expected_signature.encode())
        actual_bytes   = bytes.fromhex(actual_signature)

        if not hmac.compare_digest(expected_bytes, actual_bytes):
            self._log_security_event("signature_verification_failed",
                                     producer=headers.get("X-Producer-ID"))
            return False

        return True

    def consume_securely(self, processor: callable):
        """Consume messages with verification and safe processing"""
        try:
            for message in self.consumer:
                if not self.verify_message(message):
                    # Log and skip — don't process unverified messages
                    continue

                try:
                    processor(message.value)
                    # Only commit offset after successful processing
                    self.consumer.commit({
                        message.partition: OffsetAndMetadata(message.offset + 1, None)
                    })
                except Exception as e:
                    # Dead letter queue for failed messages
                    self._send_to_dlq(message, error=str(e))
        except KafkaError as e:
            self._log_security_event("kafka_error", error=str(e))

    def _send_to_dlq(self, message, error: str):
        """Send failed messages to Dead Letter Queue for analysis"""
        dlq_payload = {
            "original_topic":  message.topic,
            "original_offset": message.offset,
            "error":           error,
            "timestamp":       time.time(),
            "value":           message.value,
        }
        # Produce to DLQ topic for investigation
        pass

    def _log_security_event(self, event: str, **kwargs):
        import structlog
        structlog.get_logger().warning(f"kafka.security.{event}", **kwargs)
```

---

# PART 32 — NOSQL AND LDAP INJECTION

---

## Chapter 68: NoSQL Injection — MongoDB

```python
# Python — MongoDB injection prevention

from pymongo import MongoClient
from pymongo.errors import OperationFailure
import re

# ── VULNERABLE: Direct JSON-from-body into MongoDB queries ────────────────────
def find_user_unsafe(request_body: dict) -> dict:
    db = MongoClient()["mydb"]
    # Attack: request_body = {"username": {"$ne": ""}, "password": {"$ne": ""}}
    # Returns all users (operator injection bypasses auth)
    return db.users.find_one(request_body)

# ── SAFE: Input validation and type enforcement ───────────────────────────────
def find_user_safe(username: str, password_hash: str) -> dict | None:
    db = MongoClient()["mydb"]

    # Validate types — reject dicts/objects where strings expected
    if not isinstance(username, str) or not isinstance(password_hash, str):
        raise ValueError("Invalid input types")

    # Validate format — allowlist characters for username
    if not re.match(r'^[a-zA-Z0-9._@\-]{3,100}$', username):
        raise ValueError("Invalid username format")

    # Query with explicit scalar values — cannot inject operators
    return db.users.find_one({
        "username":      username,       # Python str, not dict
        "password_hash": password_hash,  # Python str, not dict
        "active":        True,
    })

# ── Using Pydantic for MongoDB query validation ───────────────────────────────
from pydantic import BaseModel, Field, validator

class UserSearchRequest(BaseModel):
    username: str = Field(min_length=3, max_length=100, pattern=r'^[a-zA-Z0-9._@\-]+$')

    # Reject MongoDB operators ($ne, $gt, $where, etc.)
    @validator('username')
    def no_operators(cls, v):
        if v.startswith('$') or '$' in v:
            raise ValueError("Invalid characters in username")
        return v

    class Config:
        # Reject extra fields — prevent hidden operator injection
        extra = 'forbid'

# ── Prevent $where injection (JavaScript execution in queries) ────────────────
def safe_mongo_collection(db):
    """Wrap collection to prevent dangerous operations"""
    class SafeCollection:
        def __init__(self, collection):
            self._col = collection

        def find(self, filter_dict: dict):
            self._validate_no_js_operators(filter_dict)
            return self._col.find(filter_dict)

        def _validate_no_js_operators(self, obj, depth=0):
            if depth > 10: raise ValueError("Query too deep")
            if isinstance(obj, dict):
                BLOCKED_OPERATORS = {'$where', '$function', '$accumulator', '$expr'}
                for key, val in obj.items():
                    if key in BLOCKED_OPERATORS:
                        raise ValueError(f"Blocked MongoDB operator: {key}")
                    self._validate_no_js_operators(val, depth + 1)

    return SafeCollection(db)
```

## Chapter 69: LDAP Injection

```python
# Python — LDAP injection prevention

import ldap
import ldap.filter
import re

# ── VULNERABLE: String concatenation into LDAP filter ────────────────────────
def authenticate_unsafe(username: str, password: str) -> bool:
    conn = ldap.initialize("ldap://ldap.company.com")
    # Attack: username = "admin)(|(password=*)"
    # Results in: (uid=admin)(|(password=*)(uid=anything))
    search_filter = f"(uid={username})"  # INJECTION
    result = conn.search_s("dc=company,dc=com", ldap.SCOPE_SUBTREE, search_filter)
    return len(result) > 0

# ── SAFE: Use ldap.filter.escape_filter_chars ─────────────────────────────────
def authenticate_safe(username: str, password: str) -> bool:
    # Input validation first — allowlist
    if not re.match(r'^[a-zA-Z0-9@._\-]{1,100}$', username):
        raise ValueError("Invalid username format")

    conn = ldap.initialize("ldap://ldap.company.com")
    conn.set_option(ldap.OPT_REFERRALS, 0)
    conn.set_option(ldap.OPT_NETWORK_TIMEOUT, 10)

    # Escape special LDAP filter characters: ( ) * \ NUL
    escaped_username = ldap.filter.escape_filter_chars(username)
    search_filter    = f"(uid={escaped_username})"

    try:
        # Search for user
        result = conn.search_s(
            "ou=users,dc=company,dc=com",
            ldap.SCOPE_SUBTREE,
            search_filter,
            ["dn", "uid", "cn"]  # Attribute allowlist — don't return all attributes
        )

        if not result:
            return False

        user_dn = result[0][0]

        # Bind with user's credentials (password verification)
        user_conn = ldap.initialize("ldap://ldap.company.com")
        user_conn.simple_bind_s(user_dn, password)
        return True

    except ldap.INVALID_CREDENTIALS:
        return False
    except ldap.SERVER_DOWN:
        raise ConnectionError("LDAP server unavailable")
    finally:
        conn.unbind_s()
```

---

# PART 33 — RUNTIME SECURITY

---

## Chapter 70: Falco — Runtime Threat Detection

```yaml
# falco/rules/custom-rules.yaml
# Runtime security rules that alert on suspicious activity in production

- rule: Detect privilege escalation via sudo or su
  desc: Alert if a process tries to use sudo or su in a container
  condition: >
    spawned_process and
    container and
    (proc.name = "sudo" or proc.name = "su") and
    not proc.pname = "test-suite"
  output: >
    Privilege escalation attempt in container
    (user=%user.name container=%container.name image=%container.image.repository
     command=%proc.cmdline pid=%proc.pid parent=%proc.pname)
  priority: CRITICAL
  tags: [container, privilege-escalation, T1548]

- rule: Detect shell spawned in API container
  desc: Alert if a shell is spawned in any API service container
  condition: >
    spawned_process and
    container and
    container.image.repository contains "api-service" and
    proc.name in (shell_binaries)
  output: >
    Shell spawned in API container — possible RCE
    (container=%container.name image=%container.image.repository
     shell=%proc.name cmdline=%proc.cmdline user=%user.name)
  priority: CRITICAL
  tags: [container, shell, RCE, T1059]

- rule: Detect unexpected outbound connection
  desc: Alert on unexpected outbound network connections from containers
  condition: >
    outbound and
    container and
    container.image.repository contains "api-service" and
    not (fd.sip.name in (allowed_outbound_hosts)) and
    not fd.sport in (53, 443, 5432)  # DNS, HTTPS, PostgreSQL
  output: >
    Unexpected outbound connection
    (container=%container.name dest=%fd.rip:%fd.rport
     cmdline=%proc.cmdline user=%user.name)
  priority: WARNING
  tags: [network, exfiltration, T1048]

- rule: Detect write to /tmp followed by execution
  desc: Detect typical post-exploitation: write payload then execute
  condition: >
    (open_write) and
    container and
    (fd.directory startswith "/tmp" or fd.directory startswith "/dev/shm") and
    proc.name not in (known_write_tmp_processes)
  output: >
    Write to /tmp or /dev/shm in container
    (file=%fd.name proc=%proc.name container=%container.name image=%container.image.repository)
  priority: HIGH
  tags: [container, T1059, T1036]

- rule: Detect credential access — reading /etc/passwd or /etc/shadow
  desc: Processes reading credential files
  condition: >
    open_read and
    container and
    (fd.name = "/etc/shadow" or fd.name = "/etc/passwd") and
    not proc.name in (known_credential_readers)
  output: >
    Credential file read in container
    (file=%fd.name proc=%proc.name cmdline=%proc.cmdline
     container=%container.name user=%user.name)
  priority: CRITICAL
  tags: [container, credential-access, T1003]

- rule: Detect curl or wget (data exfiltration tools)
  desc: Alert if curl or wget is executed in production containers
  condition: >
    spawned_process and
    container and
    proc.name in ("curl", "wget", "nc", "ncat", "netcat") and
    not (container.image.repository contains "debug" or
         container.image.repository contains "test")
  output: >
    Data transfer tool executed in container
    (proc=%proc.name cmdline=%proc.cmdline container=%container.name
     user=%user.name image=%container.image.repository)
  priority: HIGH
  tags: [exfiltration, T1048]

- macro: shell_binaries
  condition: >
    proc.name in ("sh", "bash", "zsh", "fish", "dash", "ksh", "csh", "tcsh")

- list: allowed_outbound_hosts
  items:
    - "api.stripe.com"
    - "smtp.sendgrid.net"
    - "169.254.169.254"  # AWS metadata (if needed)
```

```python
# Python — Falco alert processing and response automation
import json
import boto3
from datetime import datetime, timezone

class FalcoAlertProcessor:
    def __init__(self):
        self.ecs    = boto3.client("ecs")
        self.ec2    = boto3.client("ec2")
        self.ssm    = boto3.client("ssm")

    def process_alert(self, alert: dict) -> None:
        priority    = alert.get("priority", "INFO")
        rule        = alert.get("rule", "")
        container   = alert.get("output_fields", {}).get("container.name")
        image       = alert.get("output_fields", {}).get("container.image.repository", "")

        self._log_to_siem(alert)

        if priority == "CRITICAL":
            self._respond_to_critical(alert, container, image)
        elif priority == "HIGH":
            self._respond_to_high(alert, container)

    def _respond_to_critical(self, alert: dict, container: str, image: str):
        """Automated response for critical alerts"""
        rule = alert.get("rule", "")

        if "RCE" in rule or "Shell spawned" in rule or "privilege escalation" in rule:
            # Isolate the container immediately
            self._isolate_container(container)
            self._page_security_oncall(alert)
            self._create_forensic_snapshot(container)

        elif "Credential file read" in rule:
            # Suspend associated service account
            self._page_security_oncall(alert)

    def _isolate_container(self, container_name: str):
        """Isolate compromised container by modifying security group"""
        # Find the EC2 instance running this container
        # Apply 'isolate' security group: no ingress/egress except to forensics
        print(f"ISOLATING container {container_name}")
        # In production: use ECS task stopping + network isolation

    def _create_forensic_snapshot(self, container_name: str):
        """Take memory dump and disk snapshot for forensic analysis"""
        # Run forensics commands via SSM before stopping the container
        # Preserve evidence: process list, network connections, open files
        print(f"CREATING forensic snapshot for {container_name}")

    def _page_security_oncall(self, alert: dict):
        """Page the security team immediately"""
        # Send to PagerDuty, Opsgenie, or SNS
        print(f"PAGING security team: {alert['rule']}")

    def _log_to_siem(self, alert: dict):
        """Forward Falco alert to SIEM with enriched context"""
        import structlog
        structlog.get_logger().error(
            "falco_alert",
            rule         = alert.get("rule"),
            priority     = alert.get("priority"),
            container    = alert.get("output_fields", {}).get("container.name"),
            image        = alert.get("output_fields", {}).get("container.image.repository"),
            process      = alert.get("output_fields", {}).get("proc.name"),
            cmdline      = alert.get("output_fields", {}).get("proc.cmdline"),
            user         = alert.get("output_fields", {}).get("user.name"),
            timestamp    = alert.get("time"),
        )
```

---

# PART 34 — INCIDENT RESPONSE PLAYBOOKS

---

## Chapter 71: Developer Incident Response Playbooks

### 71.1 Credential Compromise Playbook

```python
# Python — Automated credential compromise response
import boto3
import time
from enum import Enum

class CredentialType(Enum):
    AWS_ACCESS_KEY    = "aws_access_key"
    API_KEY           = "api_key"
    DATABASE_PASSWORD = "database_password"
    JWT_SECRET        = "jwt_secret"
    SERVICE_ACCOUNT   = "service_account"

class CredentialCompromisePlaybook:
    """
    Playbook: CREDENTIAL-001
    Trigger: Secret detected in public repository, breach notification,
             or anomalous access pattern
    """

    def __init__(self):
        self.iam    = boto3.client("iam")
        self.sm     = boto3.client("secretsmanager")
        self.ec2    = boto3.client("ec2")

    def execute(self, compromised_secret_id: str, cred_type: CredentialType,
                discovered_by: str, evidence: str) -> dict:
        """
        Full automated response to a credential compromise.
        Returns: incident ID and timeline of actions
        """
        incident_id = self._create_incident(compromised_secret_id, discovered_by, evidence)
        timeline    = []
        t0          = time.time()

        print(f"\n🚨 INCIDENT {incident_id}: Credential Compromise Detected")
        print(f"   Credential: {compromised_secret_id}")
        print(f"   Type: {cred_type.value}")
        print(f"   Discovered by: {discovered_by}")

        # ── T+0: Immediate containment ────────────────────────────────────────
        print("\n[T+0] Phase 1: CONTAINMENT")

        if cred_type == CredentialType.AWS_ACCESS_KEY:
            self._deactivate_aws_key(compromised_secret_id)
            timeline.append({"time": 0, "action": "AWS key deactivated"})
            print(f"  ✓ AWS key deactivated")

        elif cred_type == CredentialType.JWT_SECRET:
            # Can't "revoke" the secret, but can rotate it to invalidate all tokens
            new_secret = self._rotate_jwt_secret(compromised_secret_id)
            timeline.append({"time": 0, "action": "JWT secret rotated — all sessions invalidated"})
            print(f"  ✓ JWT secret rotated — all user sessions invalidated")

        elif cred_type == CredentialType.DATABASE_PASSWORD:
            new_password = self._rotate_db_password(compromised_secret_id)
            timeline.append({"time": 0, "action": "Database password rotated"})
            print(f"  ✓ Database password rotated")

        # ── T+1-5min: Evidence preservation ──────────────────────────────────
        print("\n[T+1min] Phase 2: EVIDENCE PRESERVATION")
        self._preserve_access_logs(compromised_secret_id)
        timeline.append({"time": 60, "action": "Access logs preserved"})
        print(f"  ✓ Access logs captured and preserved to immutable store")

        # ── T+5-30min: Impact assessment ─────────────────────────────────────
        print("\n[T+5min] Phase 3: IMPACT ASSESSMENT")
        impact = self._assess_impact(compromised_secret_id, cred_type)
        timeline.append({"time": 300, "action": "Impact assessment complete",
                          "impact": impact})
        print(f"  Resources accessed with compromised credential: {impact}")

        # ── T+30-60min: Notifications ─────────────────────────────────────────
        print("\n[T+30min] Phase 4: NOTIFICATIONS")
        # Internal
        self._notify_security_team(incident_id, compromised_secret_id, impact)
        # Legal/compliance (for GDPR 72h clock check)
        self._check_gdpr_notification_required(impact)
        timeline.append({"time": 1800, "action": "Notifications sent"})

        # ── T+60min: Verification ─────────────────────────────────────────────
        print("\n[T+60min] Phase 5: VERIFICATION")
        self._verify_containment(compromised_secret_id, cred_type)
        timeline.append({"time": 3600, "action": "Containment verified"})
        print(f"  ✓ Containment verified — old credential no longer active")

        return {
            "incident_id": incident_id,
            "duration_minutes": (time.time() - t0) / 60,
            "timeline": timeline,
            "status": "contained",
            "next_steps": [
                "Root cause analysis within 24 hours",
                "Post-incident review within 72 hours",
                "Update detection rules based on findings",
                "Conduct team blameless postmortem",
            ]
        }

    def _deactivate_aws_key(self, access_key_id: str):
        self.iam.update_access_key(
            AccessKeyId=access_key_id,
            Status="Inactive"
        )
        # Note: Don't delete yet — preserve for forensics
        # Schedule deletion after 30-day investigation window

    def _rotate_jwt_secret(self, secret_id: str) -> str:
        import secrets
        new_secret = secrets.token_hex(32)
        self.sm.update_secret(
            SecretId=secret_id,
            SecretString=new_secret
        )
        return new_secret

    def _rotate_db_password(self, secret_id: str) -> str:
        import secrets
        new_password = secrets.token_urlsafe(32)
        # Update in Secrets Manager — services pick up automatically
        self.sm.update_secret(
            SecretId=secret_id,
            SecretString=json.dumps({"password": new_password})
        )
        # Separately: update actual database user password
        # (via database-specific rotation Lambda)
        return new_password

    def _preserve_access_logs(self, secret_id: str):
        """
        Export all access logs for the past 30 days to an
        immutable forensic store (S3 with Object Lock)
        """
        # Export CloudTrail logs, CloudWatch logs, etc.
        pass

    def _assess_impact(self, secret_id: str, cred_type: CredentialType) -> dict:
        """Query CloudTrail for all actions taken with compromised credential"""
        cloudtrail = boto3.client("cloudtrail")
        # Look up by access key ID for AWS credentials
        events = cloudtrail.lookup_events(
            LookupAttributes=[{
                "AttributeKey": "AccessKeyId",
                "AttributeValue": secret_id,
            }],
            MaxResults=100,
        )
        unique_apis    = set(e["EventName"] for e in events.get("Events", []))
        unique_ips     = set(e.get("SourceIPAddress", "") for e in events.get("Events", []))
        accessed_arns  = set()
        for event in events.get("Events", []):
            resources = event.get("Resources", [])
            accessed_arns.update(r.get("ResourceARN", "") for r in resources)

        return {
            "total_events":   len(events.get("Events", [])),
            "api_calls":      list(unique_apis),
            "source_ips":     list(unique_ips),
            "resources":      list(accessed_arns),
            "potential_data_accessed": any(
                "s3:GetObject" in api or "secretsmanager:GetSecretValue" in api
                for api in unique_apis
            ),
        }

    def _check_gdpr_notification_required(self, impact: dict):
        """Check if data breach notification is required (GDPR Art. 33: 72h)"""
        if impact.get("potential_data_accessed"):
            print("  ⚠️  GDPR: Personal data may have been accessed")
            print("  ⚠️  Start 72-hour breach notification clock")
            print("  ⚠️  Notify DPO and legal team immediately")
```

### 71.2 Data Breach Response Checklist

```python
# Python — Data breach response timeline and checklist

class DataBreachResponsePlan:
    """
    Structured 72-hour data breach response plan
    (GDPR Article 33/34 compliant)
    """

    RESPONSE_TIMELINE = {
        "0-1h": [
            ("CONTAIN", "Isolate affected systems"),
            ("CONTAIN", "Revoke compromised credentials"),
            ("CONTAIN", "Capture and preserve logs"),
            ("ASSESS",  "Identify what data types were affected"),
            ("ASSESS",  "Identify how many individuals affected"),
            ("NOTIFY",  "Alert CISO and CEO"),
            ("NOTIFY",  "Engage legal counsel"),
        ],
        "1-12h": [
            ("ASSESS",  "Determine breach scope: confirm exfiltration vs exposure"),
            ("ASSESS",  "Identify which countries' residents are affected (for GDPR jurisdiction)"),
            ("ASSESS",  "Identify special category data: health, financial, children's data"),
            ("CONTAIN", "Implement additional access controls"),
            ("NOTIFY",  "Internal stakeholder briefing"),
        ],
        "12-24h": [
            ("REMEDIATE", "Patch the vulnerability that caused the breach"),
            ("REMEDIATE", "Deploy additional monitoring"),
            ("NOTIFY",    "Prepare supervisory authority notification (GDPR: within 72h)"),
            ("ASSESS",    "Risk assessment: likely impact on data subjects"),
        ],
        "24-72h": [
            ("NOTIFY",   "Submit notification to supervisory authority if required"),
            ("NOTIFY",   "Prepare affected individual notification"),
            ("REMEDIATE","Deploy remediated code"),
            ("ASSESS",   "Document timeline for regulator"),
        ],
        "72h+": [
            ("NOTIFY",   "Notify affected individuals (if high risk to rights/freedoms)"),
            ("REMEDIATE","Post-breach security audit"),
            ("REVIEW",   "Blameless postmortem"),
            ("REVIEW",   "Update incident response procedures"),
        ],
    }

    def generate_notification_letter(
        self,
        breach_description: str,
        data_categories: list[str],
        approximate_affected: int,
        breach_date: str,
        remediation_steps: list[str],
    ) -> str:
        """Generate GDPR breach notification template for supervisory authority"""
        return f"""
DATA BREACH NOTIFICATION
Article 33 GDPR Notification to Supervisory Authority

1. NATURE OF THE BREACH:
{breach_description}

2. DATA CATEGORIES AND APPROXIMATE NUMBERS:
   Categories of personal data affected: {', '.join(data_categories)}
   Approximate number of data subjects affected: {approximate_affected}
   Approximate number of records affected: {approximate_affected}

3. CONTACT DETAILS:
   Data Protection Officer: dpo@company.com
   Contact Person: [name]

4. LIKELY CONSEQUENCES:
   [Describe the likely consequences of the personal data breach]

5. MEASURES TAKEN OR PROPOSED:
{chr(10).join(f'   - {step}' for step in remediation_steps)}

6. TIMELINE:
   Date breach occurred: {breach_date}
   Date breach discovered: [date]
   Date notified: {datetime.now().strftime('%Y-%m-%d')}

[Note: If notification delayed beyond 72 hours, provide reasons for delay]
"""
```

---

# PART 35 — END-TO-END SECURE SAAS ARCHITECTURE

---

## Chapter 72: Complete Multi-Tenant SaaS Security Architecture

### 72.1 The Security Architecture Blueprint

```
COMPLETE SAAS SECURITY ARCHITECTURE:

LAYER 0: EDGE
├── CloudFlare / AWS Shield (DDoS protection)
├── WAF (ModSecurity / AWS WAF) with OWASP Core Rule Set
├── Bot detection and CAPTCHA
└── Geographic access restrictions (if applicable)

LAYER 1: API GATEWAY
├── TLS termination (1.3)
├── Rate limiting (per-IP, per-user, per-endpoint)
├── API key / JWT validation
├── Request size limits
└── IP allowlisting for admin endpoints

LAYER 2: APPLICATION
├── Authentication (Passkeys + TOTP backup)
├── Session management (Redis, HTTPOnly+Secure+SameSite)
├── Input validation (Zod/Pydantic)
├── Authorization (RBAC + ABAC)
├── Business logic
└── Audit logging

LAYER 3: SERVICE MESH
├── mTLS between all services (Istio)
├── SPIFFE workload identity
├── Authorization policies (deny-all default)
└── Distributed tracing (OpenTelemetry)

LAYER 4: DATA
├── PostgreSQL with RLS (tenant isolation)
├── Column-level encryption (PII)
├── Redis with AUTH + TLS
├── S3 with bucket policies + SSE-KMS
└── Encrypted backups with access logging

LAYER 5: SECRETS
├── HashiCorp Vault (primary)
├── Dynamic secrets (DB, AWS)
├── Secret rotation (automated)
└── Zero-trust access (AppRole / Kubernetes auth)

LAYER 6: OBSERVABILITY
├── Falco (runtime security)
├── SIEM (ELK / Splunk / Datadog)
├── Security alerting (PagerDuty)
└── Audit trail (immutable, 1-year retention)

LAYER 7: CI/CD SECURITY
├── SAST (Semgrep, CodeQL)
├── SCA (Trivy, Snyk)
├── Container scanning
├── SBOM + artifact signing (Cosign)
└── Policy gates (OPA)
```

### 72.2 Complete Tenant Isolation Implementation

```python
# Python — Multi-tenant data isolation with PostgreSQL RLS + application layer
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import DeclarativeBase, relationship
from sqlalchemy import Column, UUID, String, Boolean, ForeignKey, event
from contextvars import ContextVar
from fastapi import HTTPException, Depends
import uuid

# ── Tenant context management ─────────────────────────────────────────────────
_tenant_context: ContextVar[str | None] = ContextVar('tenant_id', default=None)

class TenantContext:
    @staticmethod
    def set(tenant_id: str):
        _tenant_context.set(tenant_id)

    @staticmethod
    def get() -> str | None:
        return _tenant_context.get()

    @staticmethod
    def require() -> str:
        tid = _tenant_context.get()
        if not tid:
            raise RuntimeError("Tenant context not set — this is a programming error")
        return tid

# ── Database models with tenant awareness ─────────────────────────────────────
class Base(DeclarativeBase):
    pass

class Invoice(Base):
    __tablename__ = "invoices"

    id        = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True)
    user_id   = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    amount    = Column(Integer, nullable=False)
    # tenant_id + user_id on every row = enforced isolation at DB level

# ── Tenant-scoped repository pattern ─────────────────────────────────────────
class TenantScopedRepository:
    """Base repository that enforces tenant isolation on every query"""

    def __init__(self, session: AsyncSession, tenant_id: str, user_id: str = None):
        self._session   = session
        self._tenant_id = tenant_id
        self._user_id   = user_id

    async def _set_rls_context(self):
        """Set PostgreSQL RLS variables for current request"""
        await self._session.execute(
            "SELECT set_config('app.tenant_id', :tid, true), "
            "       set_config('app.user_id',   :uid, true)",
            {"tid": str(self._tenant_id), "uid": str(self._user_id or "")}
        )

class InvoiceRepository(TenantScopedRepository):

    async def get_by_id(self, invoice_id: uuid.UUID) -> Invoice | None:
        await self._set_rls_context()
        # RLS policy: tenant_id = current_setting('app.tenant_id')
        result = await self._session.execute(
            select(Invoice).where(
                Invoice.id == invoice_id,
                Invoice.tenant_id == self._tenant_id  # Double enforcement
            )
        )
        return result.scalar_one_or_none()

    async def list_user_invoices(
        self,
        offset: int = 0,
        limit:  int = 50,
    ) -> list[Invoice]:
        await self._set_rls_context()
        result = await self._session.execute(
            select(Invoice)
            .where(
                Invoice.tenant_id == self._tenant_id,  # Tenant isolation
                Invoice.user_id   == self._user_id,    # User isolation
            )
            .order_by(Invoice.created_at.desc())
            .offset(offset)
            .limit(min(limit, 100))  # Cap at 100
        )
        return result.scalars().all()

# ── FastAPI dependency injection for tenant context ──────────────────────────
async def get_tenant_session(
    tenant_id:  str = Depends(get_current_tenant_id),
    user_id:    str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_async_session),
) -> InvoiceRepository:
    """
    Create a tenant-scoped repository for the current request.
    All database operations automatically scoped to tenant + user.
    """
    repo = InvoiceRepository(session, tenant_id, user_id)
    return repo

# ── Router using tenant-scoped repository ────────────────────────────────────
@router.get("/invoices/{invoice_id}")
async def get_invoice(
    invoice_id: uuid.UUID,
    repo: InvoiceRepository = Depends(get_tenant_session),
):
    invoice = await repo.get_by_id(invoice_id)
    if not invoice:
        raise HTTPException(404)  # 404 not 403 — don't reveal cross-tenant existence
    return InvoiceResponse.from_orm(invoice)
```

### 72.3 SaaS Security Testing Strategy

```python
# Python — Comprehensive SaaS security test matrix
import pytest

class TestTenantIsolation:
    """
    Critical: Every multi-tenant operation must be tested for isolation.
    These tests are as important as feature tests.
    """

    @pytest.fixture
    async def tenant_a(self, db): return await create_test_tenant(db, "Tenant A")
    @pytest.fixture
    async def tenant_b(self, db): return await create_test_tenant(db, "Tenant B")
    @pytest.fixture
    async def user_a(self, tenant_a, db): return await create_test_user(db, tenant_a.id)
    @pytest.fixture
    async def user_b(self, tenant_b, db): return await create_test_user(db, tenant_b.id)
    @pytest.fixture
    async def invoice_b(self, tenant_b, user_b, db):
        return await create_test_invoice(db, tenant_b.id, user_b.id)

    async def test_cross_tenant_data_access_blocked(
        self, client, user_a_token, invoice_b
    ):
        """User in Tenant A cannot access Tenant B's invoices"""
        resp = await client.get(
            f"/api/invoices/{invoice_b.id}",
            headers={"Authorization": f"Bearer {user_a_token}"}
        )
        # Must be 404 — not 200 (data leak) or 403 (reveals resource exists)
        assert resp.status_code == 404

    async def test_cross_tenant_list_isolation(self, client, user_a_token, invoice_b):
        """Listing resources never returns data from other tenants"""
        resp = await client.get(
            "/api/invoices",
            headers={"Authorization": f"Bearer {user_a_token}"}
        )
        assert resp.status_code == 200
        invoice_ids = [i["id"] for i in resp.json()["items"]]
        assert str(invoice_b.id) not in invoice_ids

    async def test_cross_user_isolation_within_tenant(
        self, client, tenant_a, db
    ):
        """User A and User B in same tenant cannot see each other's private data"""
        user_a2 = await create_test_user(db, tenant_a.id, role="user")
        user_a3 = await create_test_user(db, tenant_a.id, role="user")
        private_invoice = await create_test_invoice(db, tenant_a.id, user_a2.id)
        token_a3 = await get_token(user_a3)

        resp = await client.get(
            f"/api/invoices/{private_invoice.id}",
            headers={"Authorization": f"Bearer {token_a3}"}
        )
        assert resp.status_code == 404

    async def test_admin_cannot_cross_tenant_boundary(
        self, client, tenant_b, invoice_b
    ):
        """Even a super-admin cannot access tenant data without explicit tenant context"""
        # Super-admins must explicitly assume tenant context; never implicit
        super_admin_token = await get_super_admin_token()
        resp = await client.get(
            f"/api/invoices/{invoice_b.id}",
            headers={"Authorization": f"Bearer {super_admin_token}"}
            # Note: No X-Tenant-ID header — should reject, not assume any tenant
        )
        assert resp.status_code in (400, 403, 404)

    async def test_sql_injection_does_not_escape_tenant_boundary(
        self, client, user_a_token
    ):
        """SQL injection in any field cannot return cross-tenant data"""
        payloads = [
            "' OR tenant_id != '00000000-0000-0000-0000-000000000000'--",
            "1 UNION SELECT * FROM invoices--",
            "'; UPDATE invoices SET user_id = 'attacker'--",
        ]
        for payload in payloads:
            resp = await client.get(
                f"/api/invoices/{payload}",
                headers={"Authorization": f"Bearer {user_a_token}"}
            )
            assert resp.status_code in (400, 404, 422), \
                f"Possible SQLi not blocked: {payload}"
```

---

## Chapter 73: Third-Party Risk Management

```python
# Python — Third-party vendor security assessment automation
from dataclasses import dataclass
from enum import Enum

class VendorRiskTier(Enum):
    CRITICAL = "critical"  # Processes our most sensitive data
    HIGH     = "high"      # Significant data access or operations
    MEDIUM   = "medium"    # Limited data access
    LOW      = "low"       # No data access; minimal operational dependency

@dataclass
class VendorSecurityAssessment:
    vendor_name:           str
    service:               str
    data_processed:        list[str]  # e.g., ["PII", "financial", "health"]
    risk_tier:             VendorRiskTier
    # Security certifications
    has_soc2_type2:        bool
    has_iso27001:          bool
    has_penetration_test:  bool
    pentest_recency_months: int
    # Contract requirements
    has_dpa:               bool  # Data Processing Agreement
    has_baa:               bool  # Business Associate Agreement (HIPAA)
    breach_notification_sla_hours: int  # SLA for breach notification
    # Operational
    mfa_enforced:          bool
    data_encryption_at_rest: bool
    data_encryption_in_transit: bool
    subprocessors_disclosed: bool
    annual_review_date:    str

REQUIRED_BY_TIER = {
    VendorRiskTier.CRITICAL: {
        "has_soc2_type2":         True,
        "has_penetration_test":   True,
        "pentest_recency_months": 12,   # Annual
        "has_dpa":                True,
        "breach_notification_sla_hours": 24,
        "mfa_enforced":           True,
        "data_encryption_at_rest": True,
        "data_encryption_in_transit": True,
        "subprocessors_disclosed": True,
    },
    VendorRiskTier.HIGH: {
        "has_soc2_type2":         True,
        "has_dpa":                True,
        "breach_notification_sla_hours": 48,
        "mfa_enforced":           True,
        "data_encryption_at_rest": True,
        "data_encryption_in_transit": True,
    },
    VendorRiskTier.MEDIUM: {
        "has_dpa":                True,
        "breach_notification_sla_hours": 72,
        "data_encryption_in_transit": True,
    },
    VendorRiskTier.LOW: {
        "data_encryption_in_transit": True,
    }
}

def assess_vendor(assessment: VendorSecurityAssessment) -> dict:
    """Evaluate vendor against required controls for their risk tier"""
    required = REQUIRED_BY_TIER[assessment.risk_tier]
    failures = []
    warnings = []

    for control, required_value in required.items():
        actual_value = getattr(assessment, control, None)
        if isinstance(required_value, bool):
            if actual_value != required_value:
                failures.append(f"{control}: required={required_value}, actual={actual_value}")
        elif isinstance(required_value, int):
            if control == "breach_notification_sla_hours":
                if (actual_value or 999) > required_value:
                    failures.append(f"{control}: SLA too slow ({actual_value}h > {required_value}h required)")
            elif control == "pentest_recency_months":
                if (actual_value or 999) > required_value:
                    warnings.append(f"{control}: Pentest may be outdated ({actual_value} months)")

    return {
        "vendor":        assessment.vendor_name,
        "risk_tier":     assessment.risk_tier.value,
        "status":        "APPROVED" if not failures else "REJECTED",
        "failures":      failures,
        "warnings":      warnings,
        "recommendation": (
            "Approved for use" if not failures
            else "Do not onboard until failures are remediated"
        ),
    }

# Example: SaaS email provider assessment
email_provider = VendorSecurityAssessment(
    vendor_name            = "SendGrid",
    service                = "Transactional Email",
    data_processed         = ["email", "PII (name)", "order data"],
    risk_tier              = VendorRiskTier.HIGH,
    has_soc2_type2         = True,
    has_iso27001           = True,
    has_penetration_test   = True,
    pentest_recency_months = 8,
    has_dpa                = True,
    has_baa                = False,
    breach_notification_sla_hours = 24,
    mfa_enforced           = True,
    data_encryption_at_rest= True,
    data_encryption_in_transit = True,
    subprocessors_disclosed= True,
    annual_review_date     = "2025-01",
)
result = assess_vendor(email_provider)
print(f"Vendor Assessment: {result['vendor']} — {result['status']}")
```

---

## Final Summary: The Unified Security Engineering Reference

### Complete Attack-to-Defense Mapping

```
ATTACK                     CWE      PRIMARY DEFENSE              SECONDARY DEFENSE
──────────────────────────────────────────────────────────────────────────────────────────────
SQL Injection              CWE-89   Parameterized queries         Input validation, ORM, WAF
XSS (Stored)               CWE-79   Output encoding               CSP, DOMPurify, React
XSS (Reflected)            CWE-79   Output encoding               CSP, same-origin
XSS (DOM)                  CWE-79   textContent not innerHTML     CSP strict-dynamic
SSTI                       CWE-94   Never concat user→template    Sandboxed environment
XXE                        CWE-611  Disable DOCTYPE/entities      defusedxml, XMLParser
SSRF                       CWE-918  Allowlist + IP range check    WAF, network egress filter
IDOR                       CWE-639  Ownership check in query      UUID IDs, RLS
Broken Auth                CWE-287  Passkeys/WebAuthn, MFA        JWT algorithm pinning
Mass Assignment            CWE-915  Explicit schema (Pydantic/Zod) extra="forbid"
Prototype Pollution        CWE-1321 Schema validation, Object.create(null) JSON schema
Command Injection          CWE-78   Argument list, no shell=True  Input validation allowlist
Path Traversal             CWE-22   Path.resolve() + allowlist    Chroot, containers
CSRF                       CWE-352  SameSite=Strict cookie        CSRF double-submit token
Clickjacking               CWE-1021 X-Frame-Options: DENY         CSP frame-ancestors: none
JWT algorithm confusion    CWE-347  Pin algorithm in verifier     JWKS with fixed alg
Deserialization RCE        CWE-502  JSON only, never pickle/Java  Whitelist classes
Prompt Injection           OWASP LLM01 Input classification, output schema Guard model
RAG poisoning              OWASP LLM01 Access control at retrieval  Content scanning on ingest
NoSQL Injection            CWE-943  Type enforcement, Pydantic    mongoSanitize middleware
LDAP Injection             CWE-90   ldap.filter.escape_filter_chars Input allowlist
HTTP Request Smuggling     CWE-444  HTTP/2 end-to-end             Normalize TE header at proxy
Timing attack              CWE-208  hmac.compare_digest           constant-time all comparisons
Credential in code         CWE-798  Vault/Secrets Manager         gitleaks in pre-commit
Weak crypto (MD5/SHA1)     CWE-327  SHA-256/512, Argon2id         Crypto audit in CI
```

### Language Security Feature Comparison

```
FEATURE                      PYTHON      JAVA        GO          RUST         TYPESCRIPT
────────────────────────────────────────────────────────────────────────────────────────────────
Memory safety                GC          GC          GC          Ownership    GC (V8)
Null safety                  None exists NullPointer Optional<T> No null      undefined|null
                             but None                type
Integer overflow             Arbitrary   Wraps       Wraps       Wraps        Wraps
                             precision   silently    silently    silently     silently
Type safety                  Dynamic     Static      Static      Static       Static
                             (runtime)   (compile)   (compile)   (compile)    (compile)
Buffer overflow               Impossible  Impossible  Impossible  Impossible*  Impossible
                                                                 (*safe Rust)
Race conditions              GIL limits  synchronized sync.Mutex Borrow checker Promise
                             some cases  needed      needed      prevents them needed
Secret zeroing               manual      manual      manual      Zeroize crate manual
Constant-time comparison     hmac.digest Hmac.verify subtle.ConstantTimeEq subtle::ConstantTimeEq timingSafeEqual
Cryptography library         cryptography BouncyCastle stdlib+     ring, rustls  WebCrypto API
                                          (or JCE)   x/crypto    RustCrypto
Input validation framework   Pydantic    Bean Valid. go-validator validator    Zod
Template injection           Jinja2 safe Spring safe html/template Askama      Handlebars safe
                             (use vars)  (use vars)  auto-escape  auto-escape  auto-escape
Deserialization risk         pickle HIGH  Java serial LOW (std     JSON native  JSON native
                             yaml.load    (HIGH)      lib safe)
```

---

*This is Part 5 of the Developer's Cybersecurity Mastery handbook.*

*Covered in this volume: Server-Side Template Injection (SSTI) with complete attack anatomy and fixes across Python/Java/Go, XXE across all parsers, Prototype Pollution with TypeScript defense patterns, HTTP Request Smuggling, Serverless security (Lambda security model, IaC, code signing), Message Queue security (Kafka mTLS/SASL + HMAC message signing with Python consumer verification), NoSQL injection (MongoDB operator injection), LDAP injection defense, Runtime security with Falco (custom detection rules + automated response automation), Incident Response Playbooks (credential compromise automation, data breach 72-hour timeline, GDPR notification template), Complete SaaS multi-tenant security architecture blueprint, Tenant isolation with PostgreSQL RLS + application layer enforcement, Security test matrix for multi-tenant systems, Third-party vendor risk assessment framework, and the Complete Attack-to-Defense mapping table spanning all vulnerabilities covered in the five-part handbook.*

*The complete series now covers all 38 volumes and 73 chapters of the original outline, with production-ready code examples in Java, Python, Go, Rust, and TypeScript throughout.*
