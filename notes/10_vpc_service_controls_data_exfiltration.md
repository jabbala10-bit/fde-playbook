# 10 — VPC Service Controls & Data Exfiltration Prevention

> **Why this matters for FDEs:** Every regulated enterprise client will ask
> "how do we know our data can't leave our environment?" VPC Service Controls
> (VPC SC) is the GCP answer. It's also one of the most misunderstood
> services — misconfigured VPC SC is the #1 cause of mysterious 403 errors
> in enterprise GCP deployments. Know it cold.

---

## 1. The Data Exfiltration Threat Model

```
WITHOUT VPC SERVICE CONTROLS:

  Malicious insider with BigQuery access:
  [Client's BigQuery data] ──EXPORT──► [Personal GCS bucket in another project]
  ← This is ALLOWED by default! IAM only controls who can READ,
    not where data can be COPIED TO.

  Compromised service account:
  [Vertex AI Model] ──trains on──► [Client's data]
  [Attacker] ──exfiltrates via──► [Cloud Logging, Cloud Storage export]

WITH VPC SERVICE CONTROLS:
  A "perimeter" wraps your GCP resources.
  Data can only move WITHIN the perimeter.
  Any attempt to copy data OUTSIDE the perimeter → DENIED with 403.
  Even the project OWNER cannot copy data outside without modifying the perimeter.
```

---

## 2. VPC Service Controls Concepts

```
┌──────────────────────────────────────────────────────────────────────┐
│                    VPC SC ARCHITECTURE                              │
│                                                                      │
│  ACCESS POLICY (org-level container)                                │
│  └── SERVICE PERIMETER (wraps one or more GCP projects)             │
│       ├── PROTECTED RESOURCES (BigQuery, GCS, Vertex AI, etc.)      │
│       │   Data inside these resources cannot leave the perimeter     │
│       │                                                              │
│       ├── ACCESS LEVELS (define WHO can access from outside)         │
│       │   - Corporate IP ranges                                      │
│       │   - Specific service accounts                                │
│       │   - Device policies (Chrome Enterprise cert)                 │
│       │                                                              │
│       └── INGRESS/EGRESS RULES (controlled exceptions)              │
│           - "Allow Cloud Composer to call BigQuery"                  │
│           - "Allow external Looker to read from BQ"                  │
└──────────────────────────────────────────────────────────────────────┘

KEY TERMS:
  Service Perimeter: the security boundary (like a firewall for data)
  Protected Service: GCP API restricted within the perimeter
  Access Level: conditions under which external access is allowed
  Ingress Rule: allows traffic FROM outside the perimeter INTO it
  Egress Rule: allows traffic FROM inside the perimeter to go OUT
  Dry Run Mode: logs what WOULD be blocked without actually blocking
               (use this FIRST before enforcing — saves you from 403 chaos)
```

---

## 3. Creating a Service Perimeter — Terraform

```hcl
# File: terraform/modules/vpc_sc/main.tf

# Step 1: Create an Access Policy (org-level, created once)
resource "google_access_context_manager_access_policy" "policy" {
  parent = "organizations/${var.org_id}"
  title  = "${var.client_name} Data Protection Policy"
}

# Step 2: Define Access Levels (who can access from outside)
resource "google_access_context_manager_access_level" "corporate_access" {
  parent = "accessPolicies/${google_access_context_manager_access_policy.policy.name}"
  name   = "accessPolicies/${google_access_context_manager_access_policy.policy.name}/accessLevels/corporate_network"
  title  = "Corporate Network Access"

  basic {
    conditions {
      # Allow access from corporate IP ranges
      ip_subnetworks = [
        "203.0.113.0/24",    # corporate office
        "198.51.100.0/24"    # VPN exit node
      ]
      # Optionally: require specific device policy
      device_policy {
        require_corp_owned = true
        os_constraints {
          os_type = "DESKTOP_CHROME_OS"
        }
      }
    }
  }
}

# Also allow access from specific service accounts (for pipeline SAs)
resource "google_access_context_manager_access_level" "pipeline_sa_access" {
  parent = "accessPolicies/${google_access_context_manager_access_policy.policy.name}"
  name   = "accessPolicies/${google_access_context_manager_access_policy.policy.name}/accessLevels/pipeline_service_accounts"
  title  = "Pipeline Service Account Access"

  basic {
    conditions {
      members = [
        "serviceAccount:pipeline-runner@${var.project_id}.iam.gserviceaccount.com",
        "serviceAccount:vertex-ai@${var.project_id}.iam.gserviceaccount.com"
      ]
    }
  }
}

# Step 3: Create the Service Perimeter
resource "google_access_context_manager_service_perimeter" "data_perimeter" {
  parent = "accessPolicies/${google_access_context_manager_access_policy.policy.name}"
  name   = "accessPolicies/${google_access_context_manager_access_policy.policy.name}/servicePerimeters/data_perimeter"
  title  = "Data Protection Perimeter"

  # START IN DRY RUN MODE — logs violations without blocking
  # Change to "PERIMETER_TYPE_REGULAR" to enforce after testing
  perimeter_type = "PERIMETER_TYPE_REGULAR"

  spec {
    # Projects inside the perimeter
    resources = [
      "projects/${var.project_number}",
    ]

    # GCP services restricted within the perimeter
    # Data cannot leave these services outside the perimeter
    restricted_services = [
      "bigquery.googleapis.com",
      "storage.googleapis.com",
      "aiplatform.googleapis.com",
      "dataflow.googleapis.com",
      "composer.googleapis.com",
      "secretmanager.googleapis.com",
      "cloudkms.googleapis.com",
    ]

    # Access levels that can access from OUTSIDE the perimeter
    access_levels = [
      google_access_context_manager_access_level.corporate_access.name,
    ]

    # INGRESS RULES: allow specific external → internal traffic
    ingress_policies {
      ingress_from {
        # Allow Looker (external BI tool) to query BigQuery
        identities = ["serviceAccount:looker-sa@looker-project.iam.gserviceaccount.com"]
        sources {
          access_level = google_access_context_manager_access_level.corporate_access.name
        }
      }
      ingress_to {
        resources = ["projects/${var.project_number}"]
        operations {
          service_name = "bigquery.googleapis.com"
          method_selectors {
            method = "BigQueryRead.ReadSession"
          }
          method_selectors {
            method = "BigQueryRead.ReadRows"
          }
        }
      }
    }

    # EGRESS RULES: allow specific internal → external traffic
    egress_policies {
      egress_from {
        # Allow pipeline SA to write to an external monitoring project
        identities = [
          "serviceAccount:pipeline-runner@${var.project_id}.iam.gserviceaccount.com"
        ]
      }
      egress_to {
        # Only allow writing to metrics, not data
        resources = ["projects/${var.monitoring_project_number}"]
        operations {
          service_name = "monitoring.googleapis.com"
          method_selectors {
            method = "*"  # all monitoring methods
          }
        }
      }
    }
  }

  # Enable dry-run (use_explicit_dry_run_spec = true to enable dry run mode)
  # spec above is the ENFORCED config
  # use_explicit_dry_run_spec = true  # uncomment for dry-run testing
}
```

---

## 4. Dry Run Mode — Safe Testing Before Enforcement

```bash
# ALWAYS use dry run mode before enforcing VPC SC
# Dry run logs what WOULD be blocked without actually blocking anything

# Step 1: Deploy perimeter in dry-run mode
# In Terraform, set: use_explicit_dry_run_spec = true
# and put your config under dry_run_spec instead of spec

# Step 2: Monitor dry-run violations in Cloud Logging
gcloud logging read \
  'protoPayload.metadata."@type"="type.googleapis.com/google.cloud.audit.VpcServiceControlAuditMetadata"
   AND protoPayload.metadata.resourceName!=""' \
  --project=${PROJECT_ID} \
  --format=json \
  --limit=100 | python3 -c "
import json, sys
logs = json.load(sys.stdin)
for log in logs:
    meta = log.get('protoPayload', {}).get('metadata', {})
    print(f\"Service: {meta.get('resourceName', 'N/A')}\")
    print(f\"Principal: {log.get('protoPayload', {}).get('authenticationInfo', {}).get('principalEmail', 'N/A')}\")
    print(f\"Would block: {meta.get('violationReason', 'N/A')}\")
    print('---')
"

# Step 3: For each violation, decide:
#   a) Add an ingress/egress rule to allow this traffic (legitimate)
#   b) Confirm it SHOULD be blocked (data exfiltration attempt or misconfiguration)

# Step 4: After 2-3 weeks of dry run with no unexpected violations:
# Change perimeter_type to "PERIMETER_TYPE_REGULAR" and deploy

# COMMON LEGITIMATE VIOLATIONS TO ADD RULES FOR:
# - Cloud Composer calling BigQuery (add ingress rule for composer SA)
# - Looker/Tableau reading BigQuery (add ingress rule for BI tool SA)
# - Dataflow writing to GCS (add ingress/egress rules for Dataflow SA)
# - Monitoring/alerting writing metrics externally (add egress rule)
```

---

## 5. Debugging VPC SC 403 Errors

The most common FDE pain point: "Why am I getting 403 PERMISSION_DENIED?"
It could be IAM or VPC SC. Here's how to tell:

```bash
# Step 1: Check Cloud Audit Logs for the specific error
gcloud logging read \
  'resource.type="audited_resource"
   AND protoPayload.status.code=7
   AND severity=ERROR' \
  --project=${PROJECT_ID} \
  --freshness=1h \
  --format=json | python3 -c "
import json, sys
for log in json.load(sys.stdin):
  proto = log.get('protoPayload', {})
  meta = proto.get('metadata', {})
  print('Principal:', proto.get('authenticationInfo', {}).get('principalEmail'))
  print('Method:', proto.get('methodName'))
  print('Resource:', proto.get('resourceName'))
  print('VPC SC violation:', 'vpcServiceControlViolation' in str(meta))
  print('IAM denied reason:', proto.get('status', {}).get('message'))
  print('---')
"

# Step 2: Determine if it's IAM or VPC SC
# IAM error: "Permission denied: caller does not have permission X on Y"
# VPC SC error: logs will contain "vpcServiceControlViolation"

# Step 3: For VPC SC violations, check which rule was violated
# The log will show: "violationReason", "accessState", "perimeter"

# COMMON VPC SC VIOLATION PATTERNS:
# 1. "ACCESS_POLICY_NOT_MET": principal doesn't match any access level
#    Fix: Add the principal's SA to an access level

# 2. "RESOURCES_NOT_IN_SAME_PERIMETER": cross-project data copy attempted
#    Fix: Add both projects to the same perimeter, or add an ingress/egress rule

# 3. "NO_MATCHING_ACCESS_LEVEL": request came from outside allowed IP range
#    Fix: Add the IP to the access level, or use a VPN/bastion host

# 4. Service account is in the perimeter but calling service is not
#    Fix: Add the calling GCP service to ingress_policies
```

---

## 6. VPC SC + Shared VPC — The Complex Enterprise Pattern

When using Shared VPC (see File 07) with VPC SC:

```
┌─────────────────────────────────────────────────────────────┐
│                     SERVICE PERIMETER                       │
│                                                             │
│  ┌──────────────────────┐  ┌──────────────────────────┐    │
│  │   HOST PROJECT       │  │   SERVICE PROJECT         │    │
│  │   (VPC owner)        │  │   (BigQuery, GCS owner)   │    │
│  │                      │  │                           │    │
│  │   Shared VPC         │  │   BigQuery datasets       │    │
│  │   Subnet             │◄─┤   GCS buckets             │    │
│  │   Firewall rules     │  │   Vertex AI               │    │
│  └──────────────────────┘  └──────────────────────────┘    │
│                                                             │
│  Both projects must be in the SAME perimeter               │
│  or you'll get VPC SC violations on cross-project calls    │
└─────────────────────────────────────────────────────────────┘
```

```hcl
# Add ALL projects (host + service) to the perimeter
spec {
  resources = [
    "projects/${var.host_project_number}",
    "projects/${var.service_project_a_number}",
    "projects/${var.service_project_b_number}",
  ]
  # ... rest of perimeter config
}
```

---

## 7. VPC SC Checklist — Enterprise Deployment

```
BEFORE DEPLOYING VPC SC:
□ Inventory ALL service accounts that will access protected resources
□ Identify ALL external services that need access (Looker, CI/CD, monitoring)
□ Map all data flows: what calls what, from where
□ Deploy in DRY RUN mode first — non-negotiable

DURING DRY RUN PHASE (minimum 2 weeks):
□ Review violation logs daily
□ Categorize each violation: legitimate access or actual threat
□ For legitimate: add ingress/egress rules
□ For threats: document and report to client security team
□ Zero new violations for 5 consecutive days before enforcing

AFTER ENFORCEMENT:
□ Monitor for 403 errors in application logs
□ Set up Cloud Monitoring alert for VPC SC violation rate > 0
□ Document all ingress/egress exceptions with business justification
□ Quarterly review: remove stale ingress/egress rules
□ IAM + VPC SC audit: check for over-permissioned access levels

GOTCHAS TO AVOID:
✗ Don't add "allUsers" to access levels (defeats the purpose)
✗ Don't add entire domains to access levels (too broad)
✗ Don't forget to add Cloud Composer's SA to access levels
✗ Don't mix projects from different security contexts in one perimeter
✗ Don't skip dry-run mode (always results in production 403s)
```
