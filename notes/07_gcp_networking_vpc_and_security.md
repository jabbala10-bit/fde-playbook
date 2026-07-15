# 07 — GCP Networking, VPC & Security Architecture

> **Why this matters for FDEs:** Every enterprise client deployment starts
> with a networking conversation. "Where does the data go? Who can see it?
> How is it encrypted?" If you can't answer these questions confidently,
> you will lose the trust of the client's security team in the first week.
> This file covers the full GCP networking stack for enterprise deployments.

---

## 1. GCP Network Architecture — The Mental Model

```
┌────────────────────────────────────────────────────────────────────────┐
│                        GCP PROJECT                                    │
│                                                                        │
│  ┌─────────────────────────────────────────────────────────────────┐  │
│  │                    VPC NETWORK (global)                        │  │
│  │                                                                 │  │
│  │  ┌─────────────────┐    ┌─────────────────┐                   │  │
│  │  │  Subnet (us-c1) │    │  Subnet (eu-w1) │                   │  │
│  │  │  10.10.0.0/24   │    │  10.20.0.0/24   │                   │  │
│  │  │                 │    │                 │                   │  │
│  │  │  GKE Cluster    │    │  GKE Cluster    │                   │  │
│  │  │  Cloud Run      │    │  Compute VMs    │                   │  │
│  │  └─────────────────┘    └─────────────────┘                   │  │
│  │                                                                 │  │
│  │  Private Google Access ────────────────────────────────────►  │  │
│  │  (reach BigQuery, GCS, Vertex without internet)               │  │
│  └─────────────────────────────────────────────────────────────────┘  │
│                                                                        │
│  VPC Service Controls Perimeter ─────────────────────────────────►   │
│  (prevents data exfiltration even by authorized users)                │
└────────────────────────────────────────────────────────────────────────┘
```

### Key Concepts
```
VPC (Virtual Private Cloud):
  - A private, isolated network within GCP
  - GLOBAL: one VPC spans all regions (unlike AWS where VPCs are regional)
  - Contains SUBNETS which are regional
  - Contains FIREWALL RULES (stateful, applied at instance level)

Subnet:
  - A regional IP address range within a VPC
  - All resources in a subnet are in the same region
  - Can have SECONDARY RANGES for GKE pods/services

Private Google Access:
  - Allows VMs WITHOUT public IP to reach Google APIs (BigQuery, GCS, etc.)
  - CRITICAL for enterprise: keeps data off the public internet
  - Enable on each subnet: --enable-private-ip-google-access

Cloud NAT:
  - Allows VMs without public IP to initiate outbound internet connections
  - For downloading packages, calling external APIs
  - LOG all NAT traffic for security audit
```

---

## 2. Building the Enterprise VPC — Step by Step

### Terraform: Full VPC Setup
```hcl
# File: terraform/modules/networking/main.tf

# ── VPC Network ──────────────────────────────────────────────────────────────
resource "google_compute_network" "vpc" {
  name                    = "${var.project_id}-vpc"
  auto_create_subnetworks = false  # ALWAYS false for enterprise deployments
                                    # auto subnets create uncontrolled ranges
  routing_mode            = "GLOBAL"
  project                 = var.project_id
}

# ── Subnets ───────────────────────────────────────────────────────────────────
resource "google_compute_subnetwork" "primary" {
  name          = "${var.project_id}-subnet-primary"
  ip_cidr_range = "10.10.0.0/20"      # 4094 usable IPs
  region        = var.region
  network       = google_compute_network.vpc.id
  project       = var.project_id

  # Required for GKE:
  secondary_ip_range {
    range_name    = "pods"
    ip_cidr_range = "192.168.0.0/18"  # 16382 pod IPs
  }
  secondary_ip_range {
    range_name    = "services"
    ip_cidr_range = "192.168.64.0/18" # 16382 service IPs
  }

  private_ip_google_access = true  # Reach Google APIs without public IP

  log_config {
    aggregation_interval = "INTERVAL_5_SEC"
    flow_sampling        = 0.5        # log 50% of flows (cost/visibility balance)
    metadata             = "INCLUDE_ALL_METADATA"
  }
}

# ── Cloud Router + NAT (for outbound internet without public IPs) ─────────────
resource "google_compute_router" "router" {
  name    = "${var.project_id}-router"
  region  = var.region
  network = google_compute_network.vpc.id
}

resource "google_compute_router_nat" "nat" {
  name                               = "${var.project_id}-nat"
  router                             = google_compute_router.router.name
  region                             = var.region
  nat_ip_allocate_option             = "AUTO_ONLY"
  source_subnetwork_ip_ranges_to_nat = "ALL_SUBNETWORKS_ALL_IP_RANGES"

  log_config {
    enable = true
    filter = "ERRORS_ONLY"  # log failed NAT (possible data exfiltration attempts)
  }
}

# ── Firewall Rules ─────────────────────────────────────────────────────────────
# Default DENY ALL ingress (GCP default is already deny-all ingress)
# Only allow what is explicitly needed

# Allow internal VPC traffic
resource "google_compute_firewall" "allow_internal" {
  name    = "${var.project_id}-allow-internal"
  network = google_compute_network.vpc.name
  project = var.project_id

  allow {
    protocol = "tcp"
    ports    = ["0-65535"]
  }
  allow {
    protocol = "udp"
    ports    = ["0-65535"]
  }
  allow {
    protocol = "icmp"
  }

  source_ranges = [
    "10.10.0.0/20",    # primary subnet
    "192.168.0.0/18",  # pod range
    "192.168.64.0/18"  # service range
  ]

  priority = 1000
}

# Allow SSH from IAP (Identity-Aware Proxy) only — NO direct SSH from internet
resource "google_compute_firewall" "allow_iap_ssh" {
  name    = "${var.project_id}-allow-iap-ssh"
  network = google_compute_network.vpc.name
  project = var.project_id

  allow {
    protocol = "tcp"
    ports    = ["22"]
  }
  # IAP uses this specific range to tunnel SSH connections
  source_ranges = ["35.235.240.0/20"]
  target_tags   = ["iap-ssh-enabled"]  # only apply to tagged instances
}

# Deny all other ingress (explicit deny for clarity and audit)
resource "google_compute_firewall" "deny_all_ingress" {
  name     = "${var.project_id}-deny-all-ingress"
  network  = google_compute_network.vpc.name
  project  = var.project_id
  priority = 65534  # lowest priority — catch-all

  deny {
    protocol = "all"
  }
  source_ranges = ["0.0.0.0/0"]
}
```

---

## 3. IAM — Identity and Access Management

### The Principle of Least Privilege — In Practice

```
WRONG: Give "Project Editor" to the CI/CD service account
RIGHT: Give ONLY the specific roles the service actually needs

WRONG: Give "BigQuery Admin" to the data analyst
RIGHT: Give "BigQuery Data Viewer" on specific datasets +
       "BigQuery Job User" at project level

WRONG: Use your personal account in Terraform for production
RIGHT: Use a dedicated Terraform service account with a custom role
       containing only what Terraform needs

THE FDE CHECKLIST FOR IAM AT EVERY ENGAGEMENT:
□ No human accounts have Owner or Editor roles in production
□ Service accounts have only the roles they need for their function
□ No service account keys are generated (use Workload Identity instead)
□ All IAM changes are made via Terraform (no manual console changes)
□ All IAM changes trigger a notification to the security team
```

### Terraform: IAM Bindings
```hcl
# File: terraform/modules/iam/main.tf

# ── Service Accounts ──────────────────────────────────────────────────────────
resource "google_service_account" "pipeline_sa" {
  account_id   = "pipeline-runner"
  display_name = "Data Pipeline Runner"
  description  = "Used by Cloud Composer/Airflow to run dbt + Spark jobs"
  project      = var.project_id
}

resource "google_service_account" "gke_workload_sa" {
  account_id   = "gke-workload"
  display_name = "GKE Workload Identity SA"
  description  = "Kubernetes workloads use this SA via Workload Identity"
  project      = var.project_id
}

# ── Role Bindings (least privilege) ──────────────────────────────────────────
# Pipeline SA: needs to read raw data, write to silver/gold, run BQ jobs
resource "google_project_iam_member" "pipeline_bq_dataeditor" {
  project = var.project_id
  role    = "roles/bigquery.dataEditor"    # read+write tables (not delete)
  member  = "serviceAccount:${google_service_account.pipeline_sa.email}"
}

resource "google_project_iam_member" "pipeline_bq_jobuser" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"       # run BQ jobs (separate from data access)
  member  = "serviceAccount:${google_service_account.pipeline_sa.email}"
}

resource "google_project_iam_member" "pipeline_gcs_objectviewer" {
  project = var.project_id
  role    = "roles/storage.objectViewer"   # read-only on GCS
  member  = "serviceAccount:${google_service_account.pipeline_sa.email}"
}

# Dataset-level permissions (more granular than project-level)
resource "google_bigquery_dataset_iam_member" "bronze_readonly" {
  dataset_id = "bronze_crm"
  role       = "roles/bigquery.dataViewer"  # read-only on bronze
  member     = "serviceAccount:${google_service_account.pipeline_sa.email}"
}

resource "google_bigquery_dataset_iam_member" "silver_editor" {
  dataset_id = "silver_crm"
  role       = "roles/bigquery.dataEditor"  # read+write on silver
  member     = "serviceAccount:${google_service_account.pipeline_sa.email}"
}

# ── Workload Identity (GKE pods use SA without a key file) ──────────────────
# Bind GKE Kubernetes SA to GCP SA
resource "google_service_account_iam_member" "workload_identity_binding" {
  service_account_id = google_service_account.gke_workload_sa.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "serviceAccount:${var.project_id}.svc.id.goog[default/my-ksa]"
  # format: [gcp-project].svc.id.goog[k8s-namespace/k8s-service-account-name]
}
```

---

## 4. Private Google Access — Keeping Data Off the Internet

```
Without Private Google Access:
  VM → internet → google.com → BigQuery API
  ← This exposes data to the public internet!

With Private Google Access:
  VM → Google's internal network → BigQuery API
  ← Data never leaves Google's network. Required for enterprise compliance.

How to verify it's working:
  gcloud compute instances describe my-vm --zone=us-central1-a \
    | grep -i "privateIpGoogleAccess"
  Should return: privateIpGoogleAccess: true
```

### Private Service Connect — For Connecting to External Services
```hcl
# Some services (Cloud SQL, Vertex AI) require Private Service Connect
# for fully private connectivity

resource "google_compute_global_address" "psc_range" {
  name          = "psc-ip-range"
  purpose       = "VPC_PEERING"
  address_type  = "INTERNAL"
  prefix_length = 16
  network       = google_compute_network.vpc.id
}

resource "google_service_networking_connection" "psc_connection" {
  network                 = google_compute_network.vpc.id
  service                 = "servicenetworking.googleapis.com"
  reserved_peering_ranges = [google_compute_global_address.psc_range.name]
}
```

---

## 5. Shared VPC — Multi-Project Enterprise Architecture

Large enterprise deployments use **Shared VPC** to centralize networking
while allowing multiple projects to share the same network infrastructure.

```
┌─────────────────────────────────────────────────────────────┐
│                    HOST PROJECT                              │
│    (owns the VPC, subnets, firewall rules, VPN gateways)    │
│                                                             │
│    VPC: corp-shared-vpc                                     │
│    Subnet: prod-subnet-us-c1 (10.10.0.0/20)                │
│    Subnet: dev-subnet-us-c1  (10.20.0.0/20)                │
└─────────────────────────────────────────────────────────────┘
              ↑                         ↑
              │ Shared VPC              │ Shared VPC
              │ access                  │ access
┌─────────────────────────┐  ┌─────────────────────────┐
│  SERVICE PROJECT A      │  │  SERVICE PROJECT B      │
│  (data-engineering)     │  │  (ml-workloads)         │
│  GKE Cluster            │  │  Vertex AI              │
│  Cloud Composer         │  │  Cloud Run              │
│  BigQuery               │  │  BigQuery               │
└─────────────────────────┘  └─────────────────────────┘
```

```hcl
# Grant service project access to host project's VPC
resource "google_compute_shared_vpc_service_project" "service_project_a" {
  host_project    = var.host_project_id
  service_project = var.service_project_a_id
}

# Grant network user role to service project's default SA
resource "google_project_iam_member" "service_project_network_user" {
  project = var.host_project_id
  role    = "roles/compute.networkUser"
  member  = "serviceAccount:${var.service_project_a_number}@cloudservices.gserviceaccount.com"
}
```

---

## 6. Encryption at Rest and In Transit

```
GCP DEFAULT ENCRYPTION (you get this automatically):
  - All data at rest: AES-256 encryption using Google-managed keys
  - All data in transit: TLS 1.2+ between GCP services and your clients

FOR REGULATED INDUSTRIES — Customer-Managed Encryption Keys (CMEK):
  - Client controls their OWN keys in Cloud KMS
  - Google cannot decrypt their data even with a legal order
  - Required for: HIPAA, certain financial regulations, government contracts
```

```hcl
# Terraform: Set up CMEK for BigQuery and GCS

# Create a Cloud KMS key ring
resource "google_kms_key_ring" "keyring" {
  name     = "${var.project_id}-keyring"
  location = var.region
}

# Create a crypto key (auto-rotates every 90 days)
resource "google_kms_crypto_key" "bq_key" {
  name            = "bigquery-encryption-key"
  key_ring        = google_kms_key_ring.keyring.id
  rotation_period = "7776000s"  # 90 days in seconds
  purpose         = "ENCRYPT_DECRYPT"
}

# Grant BigQuery permission to use the key
resource "google_kms_crypto_key_iam_member" "bq_encrypt" {
  crypto_key_id = google_kms_crypto_key.bq_key.id
  role          = "roles/cloudkms.cryptoKeyEncrypterDecrypter"
  member        = "serviceAccount:bq-${var.project_number}@bigquery-encryption.iam.gserviceaccount.com"
}

# Use CMEK for BigQuery dataset
resource "google_bigquery_dataset" "silver" {
  dataset_id = "silver_crm"
  location   = var.region

  default_encryption_configuration {
    kms_key_name = google_kms_crypto_key.bq_key.id
  }
}
```

---

## 7. Security Checklist — Pre-Production Gate

Run this checklist before any client system goes live:

```
NETWORK SECURITY:
□ All VMs have no public IP addresses
□ Private Google Access enabled on all subnets
□ Firewall: deny-all ingress is the default; only necessary ports opened
□ SSH access only via IAP (no direct 0.0.0.0/0 rule on port 22)
□ VPC Flow Logs enabled (audit trail for network activity)
□ Cloud NAT logs enabled (detect unexpected outbound connections)

IAM SECURITY:
□ No service account keys in use (use Workload Identity for GKE)
□ No Owner/Editor roles for human users in production
□ No service account has roles beyond what it needs
□ IAM changes managed via Terraform (version controlled)
□ Organization Policy: "iam.disableServiceAccountKeyCreation" enforced

DATA SECURITY:
□ All sensitive datasets have CMEK or confirmed Google-managed key is acceptable
□ PII data identified and documented in the Data Dictionary
□ DLP (Data Loss Prevention) scan scheduled for PII discovery
□ BigQuery row-level security in place for multi-tenant datasets
□ Audit logs (BigQuery audit, GCS audit) enabled and exported

VULNERABILITY:
□ Container images scanned for CVEs (Artifact Registry scanning enabled)
□ All package dependencies pinned to specific versions
□ Secret values stored in Secret Manager (not in code or environment variables)
□ No credentials or keys in Git history
□ Binary Authorization enabled for GKE (only signed images run)
```
