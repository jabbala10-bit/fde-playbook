# 11 — Terraform IaC for FDE Deployments

> **Why this matters for FDEs:** Every GCP resource you create manually
> in the console will need to be recreated at the next client. Terraform
> makes your entire deployment reproducible, reviewable, and transferable.
> It also impresses clients: "here is the exact code that created
> everything you see" is a powerful trust signal.

---

## 1. Terraform Mental Model for FDEs

```
WITHOUT Terraform:
  FDE clicks through GCP console for 3 hours to set up a new project.
  Day 2: "Can you recreate this in our staging environment?"
  FDE: (internally panicking) "...sure, give me another 3 hours."
  Month 3: No one knows what was created, why, or how to change it safely.

WITH Terraform:
  FDE writes Terraform once → runs in 10 minutes on any GCP project.
  Day 2: "Can you recreate this in staging?"
  FDE: "terraform workspace new staging && terraform apply — done in 15 min."
  Month 3: Every resource has a code review trail. Changes are reviewed
           before applying. Drift is detected automatically.

THE FDE TERRAFORM PRINCIPLES:
  1. Everything is code. No manual console changes after Day 1.
  2. Remote state in GCS — never local state files.
  3. Modular: reusable modules for VPC, IAM, GKE, BigQuery.
  4. Workspaces or variable files for dev/staging/prod.
  5. State lock: prevent concurrent applies.
```

---

## 2. Project Structure — The FDE Terraform Repository

```
infrastructure/
├── environments/
│   ├── dev/
│   │   ├── main.tf          ← calls modules with dev-specific variables
│   │   ├── variables.tf
│   │   └── terraform.tfvars ← dev-specific values (not committed for prod)
│   ├── staging/
│   │   ├── main.tf
│   │   └── terraform.tfvars
│   └── prod/
│       ├── main.tf
│       └── terraform.tfvars
├── modules/
│   ├── project-setup/       ← GCP project, APIs, billing
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   └── outputs.tf
│   ├── networking/          ← VPC, subnets, firewall, NAT
│   ├── iam/                 ← service accounts, role bindings
│   ├── gke/                 ← GKE cluster, node pools
│   ├── bigquery/            ← datasets, tables, views
│   ├── gcs/                 ← buckets, lifecycle policies
│   ├── vpc-sc/              ← VPC Service Controls
│   ├── secret-manager/      ← secrets (values from env vars)
│   └── vertex-ai/           ← Vertex AI resources, endpoints
└── shared/
    ├── backend.tf           ← GCS backend configuration
    └── versions.tf          ← provider version pinning
```

---

## 3. The Landing Zone — Complete Terraform Bootstrap

### Backend Configuration (always set up first)
```hcl
# shared/backend.tf
# IMPORTANT: bootstrap this manually ONCE before using Terraform
# The bucket itself can't be created by Terraform (chicken-and-egg)

# Create the backend bucket manually:
# gcloud storage buckets create gs://[project-id]-tfstate \
#   --location=us-central1 \
#   --uniform-bucket-level-access \
#   --versioning

terraform {
  backend "gcs" {
    bucket = "${var.project_id}-tfstate"  # can't use variable in backend
    # Use: terraform init -backend-config="bucket=[project-id]-tfstate"
    prefix = "terraform/state"
  }
}
```

### Provider and Version Pinning
```hcl
# shared/versions.tf
terraform {
  required_version = ">= 1.5.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"   # pin major version, allow minor updates
    }
    google-beta = {
      source  = "hashicorp/google-beta"
      version = "~> 5.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

provider "google-beta" {
  project = var.project_id
  region  = var.region
}
```

### Project Setup Module
```hcl
# modules/project-setup/main.tf

# Enable required GCP APIs
resource "google_project_service" "apis" {
  for_each = toset([
    "compute.googleapis.com",
    "container.googleapis.com",       # GKE
    "bigquery.googleapis.com",
    "bigquerystorage.googleapis.com",
    "storage.googleapis.com",
    "secretmanager.googleapis.com",
    "cloudkms.googleapis.com",
    "aiplatform.googleapis.com",      # Vertex AI
    "artifactregistry.googleapis.com",
    "cloudtrace.googleapis.com",
    "monitoring.googleapis.com",
    "logging.googleapis.com",
    "iam.googleapis.com",
    "serviceusage.googleapis.com",
    "accesscontextmanager.googleapis.com",  # VPC SC
    "servicenetworking.googleapis.com",
    "dns.googleapis.com",
  ])

  project            = var.project_id
  service            = each.value
  disable_on_destroy = false  # don't disable APIs on terraform destroy
}

# Project-level IAM audit logging (required for compliance)
resource "google_project_iam_audit_config" "audit_all" {
  project = var.project_id
  service = "allServices"

  audit_log_config {
    log_type = "ADMIN_READ"
  }
  audit_log_config {
    log_type = "DATA_READ"
  }
  audit_log_config {
    log_type = "DATA_WRITE"
  }
}

# Org policy: prevent external IP on VMs
resource "google_project_organization_policy" "no_external_ip" {
  project    = var.project_id
  constraint = "compute.vmExternalIpAccess"

  list_policy {
    deny { all = true }
  }
}

# Org policy: restrict resource location to approved regions
resource "google_project_organization_policy" "resource_locations" {
  project    = var.project_id
  constraint = "gcp.resourceLocations"

  list_policy {
    allow {
      values = ["in:us-locations"]  # only US regions
    }
  }
}
```

---

## 4. GCS Module — Storage Buckets with Lifecycle

```hcl
# modules/gcs/main.tf

locals {
  buckets = {
    raw = {
      name   = "${var.project_id}-raw"
      purpose = "Raw/Bronze layer — immutable source data"
      versioning = true
    }
    silver = {
      name   = "${var.project_id}-silver"
      purpose = "Silver layer — cleaned data"
      versioning = false
    }
    artifacts = {
      name   = "${var.project_id}-artifacts"
      purpose = "ML model artifacts, dbt docs"
      versioning = true
    }
  }
}

resource "google_storage_bucket" "buckets" {
  for_each = local.buckets

  name          = each.value.name
  location      = var.region
  project       = var.project_id
  force_destroy = false  # NEVER delete a non-empty bucket accidentally

  uniform_bucket_level_access = true  # required for VPC SC
  public_access_prevention    = "enforced"  # no public URLs ever

  versioning {
    enabled = each.value.versioning
  }

  # Lifecycle rules — cost management
  lifecycle_rule {
    condition {
      age = 365  # after 1 year
    }
    action {
      type          = "SetStorageClass"
      storage_class = "NEARLINE"  # cheaper for infrequent access
    }
  }

  lifecycle_rule {
    condition {
      age = 730  # after 2 years
    }
    action {
      type          = "SetStorageClass"
      storage_class = "COLDLINE"  # even cheaper for rare access
    }
  }

  # For raw bucket: delete old non-current versions
  dynamic "lifecycle_rule" {
    for_each = each.value.versioning ? [1] : []
    content {
      condition {
        num_newer_versions = 3  # keep 3 versions, delete older
      }
      action {
        type = "Delete"
      }
    }
  }

  encryption {
    default_kms_key_name = var.kms_key_id  # CMEK
  }
}
```

---

## 5. BigQuery Module — Datasets and Tables

```hcl
# modules/bigquery/main.tf

# Create datasets (Bronze/Silver/Gold)
resource "google_bigquery_dataset" "datasets" {
  for_each = var.datasets

  dataset_id    = each.key
  friendly_name = each.value.friendly_name
  description   = each.value.description
  location      = var.region
  project       = var.project_id

  default_table_expiration_ms = lookup(each.value, "table_expiration_days", null) != null ? (
    each.value.table_expiration_days * 24 * 60 * 60 * 1000
  ) : null

  default_encryption_configuration {
    kms_key_name = var.kms_key_id
  }

  # Access controls
  dynamic "access" {
    for_each = lookup(each.value, "data_editors", [])
    content {
      role          = "WRITER"
      user_by_email = access.value
    }
  }

  dynamic "access" {
    for_each = lookup(each.value, "data_viewers", [])
    content {
      role          = "READER"
      user_by_email = access.value
    }
  }

  # Always allow BQ service account
  access {
    role           = "OWNER"
    special_group  = "projectOwners"
  }
}

# Variable definition for flexibility
variable "datasets" {
  type = map(object({
    friendly_name        = string
    description          = string
    table_expiration_days = optional(number)
    data_editors         = optional(list(string), [])
    data_viewers         = optional(list(string), [])
  }))
  default = {
    bronze_crm = {
      friendly_name = "Bronze CRM"
      description   = "Raw CRM data — immutable source layer"
    }
    silver_crm = {
      friendly_name = "Silver CRM"
      description   = "Cleaned and validated CRM data"
    }
    gold_analytics = {
      friendly_name = "Gold Analytics"
      description   = "Business-ready analytics tables"
    }
  }
}
```

---

## 6. Terraform Workflow — Daily FDE Commands

```bash
# ── INITIAL SETUP ─────────────────────────────────────────────────────────────

# Initialize (download providers, configure backend)
terraform init \
  -backend-config="bucket=${PROJECT_ID}-tfstate" \
  -backend-config="prefix=terraform/state"

# Create workspace per environment
terraform workspace new dev
terraform workspace new staging
terraform workspace new prod

# Switch to dev workspace
terraform workspace select dev

# ── DAILY WORKFLOW ────────────────────────────────────────────────────────────

# Always validate before plan
terraform validate

# Format code (do this before every commit)
terraform fmt -recursive

# Preview changes (ALWAYS run before apply)
terraform plan \
  -var-file="environments/dev/terraform.tfvars" \
  -out=tfplan  # save the plan

# Review the plan output carefully:
# + = resource will be CREATED
# ~ = resource will be MODIFIED (check what changes)
# - = resource will be DELETED (verify this is intentional!)
# -/+ = resource will be REPLACED (destroyed + recreated — can cause downtime)

# Apply the saved plan (uses exact plan from above — no surprises)
terraform apply tfplan

# ── PRODUCTION SAFETY ─────────────────────────────────────────────────────────

# In production, use -target to apply one resource at a time
terraform apply -target=module.gke.google_container_cluster.primary

# Check what Terraform thinks the current state is vs. reality
terraform show

# Detect drift (resources changed outside Terraform)
terraform plan -refresh-only

# Import an existing resource into Terraform state
terraform import module.bigquery.google_bigquery_dataset.datasets["silver_crm"] \
  "projects/${PROJECT_ID}/datasets/silver_crm"

# ── STATE MANAGEMENT ──────────────────────────────────────────────────────────

# List all resources in state
terraform state list

# Show details of a specific resource
terraform state show module.gke.google_container_cluster.primary

# Move resource to new address (after module refactoring)
terraform state mv \
  google_container_cluster.primary \
  module.gke.google_container_cluster.primary

# Remove resource from state WITHOUT destroying (use with caution)
terraform state rm module.iam.google_project_iam_member.pipeline_bq
```

---

## 7. Terraform for GCP — Common Gotchas

```
GOTCHA 1: Destroying a GCS bucket with data
  Solution: force_destroy = false (default) prevents this
  terraform destroy will fail if bucket has objects — intentional safety

GOTCHA 2: IAM policy replace vs. additive
  google_project_iam_policy    → replaces ALL project IAM (DANGEROUS)
  google_project_iam_binding   → replaces ONE role's members (risky)
  google_project_iam_member    → adds/removes ONE member (SAFEST)
  Always use google_project_iam_member for FDE work

GOTCHA 3: Service account key creation
  google_service_account_key   → creates a downloadable key (avoid!)
  Use Workload Identity instead — never create SA keys via Terraform
  If a legacy system requires it, store in Secret Manager immediately

GOTCHA 4: VPC SC and Terraform
  Terraform needs to call GCP APIs to manage VPC SC
  If VPC SC is enforced, Terraform's SA must be in an access level
  → Always add your Terraform SA to the access level before enforcing

GOTCHA 5: Concurrent applies
  Two engineers running terraform apply simultaneously = state corruption
  Solution: GCS backend automatically enables state locking
  If locked: check who locked it, wait, or unlock with:
  terraform force-unlock [LOCK_ID]  ← use with extreme caution

GOTCHA 6: Provider version drift
  A minor provider version bump can change resource behavior
  Solution: pin versions in required_providers with ~> (allows patches only)
  Run: terraform providers lock -platform=linux_amd64 to pin exact versions
```

---

## 8. The Full Landing Zone — Root Module

```hcl
# environments/prod/main.tf — the "entry point" for a full deployment

module "project_setup" {
  source     = "../../modules/project-setup"
  project_id = var.project_id
}

module "networking" {
  source     = "../../modules/networking"
  project_id = var.project_id
  region     = var.region
  depends_on = [module.project_setup]
}

module "iam" {
  source     = "../../modules/iam"
  project_id = var.project_id
  depends_on = [module.project_setup]
}

module "kms" {
  source     = "../../modules/kms"
  project_id = var.project_id
  region     = var.region
  depends_on = [module.project_setup]
}

module "gcs" {
  source     = "../../modules/gcs"
  project_id = var.project_id
  region     = var.region
  kms_key_id = module.kms.bigquery_key_id
  depends_on = [module.kms, module.project_setup]
}

module "bigquery" {
  source     = "../../modules/bigquery"
  project_id = var.project_id
  region     = var.region
  kms_key_id = module.kms.bigquery_key_id
  depends_on = [module.kms, module.project_setup]
}

module "gke" {
  source          = "../../modules/gke"
  project_id      = var.project_id
  region          = var.region
  vpc_name        = module.networking.vpc_name
  subnet_name     = module.networking.primary_subnet_name
  gke_node_sa     = module.iam.gke_node_sa_email
  depends_on      = [module.networking, module.iam]
}

module "vpc_sc" {
  source                 = "../../modules/vpc-sc"
  project_id             = var.project_id
  project_number         = var.project_number
  org_id                 = var.org_id
  authorized_network_cidr = var.corporate_vpn_cidr
  depends_on             = [module.project_setup]
}

# Output all important values
output "gke_cluster_name" { value = module.gke.cluster_name }
output "gke_connect_cmd" {
  value = "gcloud container clusters get-credentials ${module.gke.cluster_name} --region=${var.region} --project=${var.project_id}"
}
output "bq_datasets" { value = module.bigquery.dataset_ids }
output "gcs_buckets" { value = module.gcs.bucket_names }
```
