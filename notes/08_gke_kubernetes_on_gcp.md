# 08 — GKE: Kubernetes on GCP for FDE Deployments

> **Why this matters for FDEs:** GKE is where your production AI agents,
> APIs, and pipeline workers live. You must be able to provision a
> private GKE cluster, deploy workloads with Workload Identity, debug
> failing pods, and scale under load — all without needing a DevOps
> engineer standing next to you.

---

## 1. GKE Architecture — The Mental Model

```
┌─────────────────────────────────────────────────────────────────────┐
│                        GKE CLUSTER                                 │
│                                                                     │
│  CONTROL PLANE (Google-managed, hidden from you)                   │
│  ─────────────────────────────────────────────────────────────────  │
│  kube-apiserver  etcd  kube-scheduler  kube-controller-manager     │
│                                                                     │
│  NODE POOLS (you manage these — these are GCE VMs)                 │
│  ─────────────────────────────────────────────────────────────────  │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐ │
│  │  Node (n1-std-4) │  │  Node (n1-std-4) │  │  Node (n1-std-4) │ │
│  │  ┌────────────┐  │  │  ┌────────────┐  │  │  ┌────────────┐  │ │
│  │  │ Pod: agent │  │  │  │ Pod: api   │  │  │  │ Pod: worker│  │ │
│  │  └────────────┘  │  │  └────────────┘  │  │  └────────────┘  │ │
│  │  ┌────────────┐  │  │                  │  │  ┌────────────┐  │ │
│  │  │ Pod: agent │  │  │                  │  │  │ Pod: worker│  │ │
│  │  └────────────┘  │  │                  │  │  └────────────┘  │ │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
```

### GKE vs. Cloud Run vs. Vertex AI Agent Engine

```
┌──────────────────┬──────────────────────┬──────────────────────────┐
│ Factor           │ GKE                  │ Cloud Run               │
├──────────────────┼──────────────────────┼──────────────────────────┤
│ Control          │ Full k8s control     │ Opinionated/limited      │
│ Stateful apps    │ ✓ StatefulSets       │ ✗ Stateless only         │
│ Long-running     │ ✓ Always-on pods     │ ✓ Min instances > 0      │
│ GPU workloads    │ ✓ GPU node pools     │ ✗ No GPU support         │
│ Complexity       │ High                 │ Low                      │
│ Cost             │ Pay for nodes 24/7   │ Pay per request          │
│ Use for          │ Agents, ML serving,  │ APIs, webhooks,          │
│                  │ complex pipelines    │ event handlers           │
└──────────────────┴──────────────────────┴──────────────────────────┘

Vertex AI Agent Engine (for ADK agents specifically):
→ Managed runtime for Google ADK agents
→ Auto-scaling, no cluster management
→ Best choice when using Google ADK (see File 14)
→ Use GKE when you need more control or non-ADK frameworks
```

---

## 2. Provisioning a Private GKE Cluster — Terraform

```hcl
# File: terraform/modules/gke/main.tf

resource "google_container_cluster" "primary" {
  name     = "${var.project_id}-gke"
  location = var.region       # regional cluster = 3 control plane replicas
  project  = var.project_id

  # Use a separately managed node pool (remove default)
  remove_default_node_pool = true
  initial_node_count       = 1

  # PRIVATE CLUSTER: no public endpoint for nodes or control plane
  private_cluster_config {
    enable_private_nodes    = true   # nodes have no public IPs
    enable_private_endpoint = false  # keep public endpoint for kubectl access
                                      # set to true for fully air-gapped (needs VPN)
    master_ipv4_cidr_block  = "172.16.0.0/28"  # control plane internal range
  }

  # Master authorized networks: only allow kubectl from specific IPs
  master_authorized_networks_config {
    cidr_blocks {
      cidr_block   = var.authorized_network_cidr  # e.g., your VPN/bastion IP
      display_name = "corporate-vpn"
    }
  }

  # Networking
  network    = var.vpc_name
  subnetwork = var.subnet_name
  ip_allocation_policy {
    cluster_secondary_range_name  = "pods"      # from subnet secondary ranges
    services_secondary_range_name = "services"
  }

  # Workload Identity: allows pods to use GCP service accounts without key files
  workload_identity_config {
    workload_pool = "${var.project_id}.svc.id.goog"
  }

  # Enable Binary Authorization (only run signed container images)
  binary_authorization {
    evaluation_mode = "PROJECT_SINGLETON_POLICY_ENFORCE"
  }

  # Logging and monitoring
  logging_config {
    enable_components = ["SYSTEM_COMPONENTS", "WORKLOADS"]
  }
  monitoring_config {
    enable_components = ["SYSTEM_COMPONENTS"]
    managed_prometheus { enabled = true }  # GKE Managed Prometheus
  }

  # Security
  enable_shielded_nodes = true

  addons_config {
    http_load_balancing { disabled = false }
    gce_persistent_disk_csi_driver_config { enabled = true }
  }
}

# ── Node Pool ─────────────────────────────────────────────────────────────────
resource "google_container_node_pool" "primary_nodes" {
  name       = "${var.project_id}-node-pool"
  location   = var.region
  cluster    = google_container_cluster.primary.name
  project    = var.project_id

  # Auto-scaling: min 2 nodes, max 10 per zone
  autoscaling {
    min_node_count  = 2
    max_node_count  = 10
    location_policy = "BALANCED"  # spread across zones
  }

  node_config {
    machine_type = "n2-standard-4"   # 4 vCPU, 16GB RAM
    disk_size_gb = 100
    disk_type    = "pd-ssd"

    # Workload Identity: pods authenticate as this GCP service account
    service_account = var.gke_node_sa_email
    oauth_scopes = [
      "https://www.googleapis.com/auth/cloud-platform"  # full GCP access controlled by IAM
    ]

    workload_metadata_config {
      mode = "GKE_METADATA"  # Required for Workload Identity
    }

    shielded_instance_config {
      enable_secure_boot          = true
      enable_integrity_monitoring = true
    }

    labels = {
      environment = var.environment
      managed-by  = "terraform"
    }
  }

  management {
    auto_repair  = true
    auto_upgrade = true
  }

  upgrade_settings {
    max_surge       = 1
    max_unavailable = 0  # zero-downtime upgrades
  }
}

# ── GPU Node Pool (for ML inference) ─────────────────────────────────────────
resource "google_container_node_pool" "gpu_nodes" {
  name    = "${var.project_id}-gpu-pool"
  count   = var.enable_gpu_nodes ? 1 : 0  # optional
  cluster = google_container_cluster.primary.name

  autoscaling {
    min_node_count = 0   # scale to zero when no GPU workloads
    max_node_count = 4
  }

  node_config {
    machine_type = "n1-standard-8"
    guest_accelerator {
      type  = "nvidia-tesla-t4"
      count = 1
      gpu_driver_installation_config {
        gpu_driver_version = "LATEST"
      }
    }

    # GPU nodes need a taint so only GPU workloads land here
    taint {
      key    = "nvidia.com/gpu"
      value  = "present"
      effect = "NO_SCHEDULE"
    }
  }
}
```

---

## 3. Workload Identity — The Secure Way to Access GCP

**Never use service account key files in Kubernetes.** Use Workload Identity.

```bash
# Step 1: Create the GCP Service Account (done in IAM Terraform)
gcloud iam service-accounts create gke-workload \
  --project=my-project

# Step 2: Give it the permissions the pod needs
gcloud projects add-iam-policy-binding my-project \
  --member="serviceAccount:gke-workload@my-project.iam.gserviceaccount.com" \
  --role="roles/bigquery.dataEditor"

# Step 3: Create a Kubernetes Service Account
kubectl create serviceaccount my-ksa --namespace=default

# Step 4: Bind the K8s SA to the GCP SA
gcloud iam service-accounts add-iam-policy-binding \
  gke-workload@my-project.iam.gserviceaccount.com \
  --role="roles/iam.workloadIdentityUser" \
  --member="serviceAccount:my-project.svc.id.goog[default/my-ksa]"

# Step 5: Annotate the K8s SA with the GCP SA email
kubectl annotate serviceaccount my-ksa \
  --namespace=default \
  iam.gke.io/gcp-service-account=gke-workload@my-project.iam.gserviceaccount.com
```

```yaml
# Pod manifest: use the annotated service account
apiVersion: v1
kind: Pod
metadata:
  name: my-agent
  namespace: default
spec:
  serviceAccountName: my-ksa   # ← this pod authenticates as gke-workload GCP SA
  containers:
  - name: agent
    image: us-central1-docker.pkg.dev/my-project/my-repo/agent:v1.0
    # No key files needed — the pod automatically gets GCP credentials
    env:
    - name: GOOGLE_CLOUD_PROJECT
      value: "my-project"
```

---

## 4. Deploying an AI Agent to GKE — Full Manifest Set

```yaml
# ── Namespace ────────────────────────────────────────────────────────────────
apiVersion: v1
kind: Namespace
metadata:
  name: ai-agents
  labels:
    environment: production

---
# ── ConfigMap: non-sensitive configuration ──────────────────────────────────
apiVersion: v1
kind: ConfigMap
metadata:
  name: agent-config
  namespace: ai-agents
data:
  PROJECT_ID: "my-gcp-project"
  LOCATION: "us-central1"
  BQ_DATASET: "gold_analytics"
  LOG_LEVEL: "INFO"
  MAX_CONCURRENT_SESSIONS: "100"

---
# ── Deployment ───────────────────────────────────────────────────────────────
apiVersion: apps/v1
kind: Deployment
metadata:
  name: customer-support-agent
  namespace: ai-agents
  labels:
    app: customer-support-agent
    version: v1.0
spec:
  replicas: 3
  selector:
    matchLabels:
      app: customer-support-agent
  template:
    metadata:
      labels:
        app: customer-support-agent
        version: v1.0
    spec:
      serviceAccountName: my-ksa  # Workload Identity
      containers:
      - name: agent
        image: us-central1-docker.pkg.dev/my-project/agents/support-agent:v1.0
        ports:
        - containerPort: 8080

        envFrom:
        - configMapRef:
            name: agent-config

        env:
        # Secret from Secret Manager via kubernetes-external-secrets or direct mount
        - name: ANTHROPIC_API_KEY
          valueFrom:
            secretKeyRef:
              name: api-keys
              key: anthropic-key

        resources:
          requests:
            memory: "512Mi"
            cpu: "250m"
          limits:
            memory: "2Gi"
            cpu: "1000m"

        # Health checks — CRITICAL for production
        readinessProbe:
          httpGet:
            path: /health
            port: 8080
          initialDelaySeconds: 10
          periodSeconds: 5
          failureThreshold: 3

        livenessProbe:
          httpGet:
            path: /health
            port: 8080
          initialDelaySeconds: 30
          periodSeconds: 30
          failureThreshold: 3

      # Security context — run as non-root
      securityContext:
        runAsNonRoot: true
        runAsUser: 1000
        fsGroup: 2000

---
# ── Service ───────────────────────────────────────────────────────────────────
apiVersion: v1
kind: Service
metadata:
  name: customer-support-agent
  namespace: ai-agents
spec:
  selector:
    app: customer-support-agent
  ports:
  - port: 80
    targetPort: 8080
  type: ClusterIP  # internal only; expose via Ingress or Load Balancer

---
# ── HorizontalPodAutoscaler ───────────────────────────────────────────────────
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: customer-support-agent-hpa
  namespace: ai-agents
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: customer-support-agent
  minReplicas: 2
  maxReplicas: 20
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
```

---

## 5. Debugging Pods — Field Playbook

```bash
# ── The FDE Pod Debugging Sequence ───────────────────────────────────────────

# 1. Get pod status
kubectl get pods -n ai-agents
# STATUS meanings:
# Running      → pod is up (check logs if behavior is wrong)
# Pending      → can't be scheduled (resource constraints, node selector)
# CrashLoopBackOff → container keeps crashing (check logs)
# OOMKilled    → out of memory (increase memory limit)
# ImagePullBackOff → can't pull image (check image name, registry auth)
# Error        → container exited with non-zero (check logs)

# 2. Describe the pod for events and state
kubectl describe pod customer-support-agent-abc123 -n ai-agents
# Look at: Events section at the bottom — this shows exactly what went wrong

# 3. Get logs
kubectl logs customer-support-agent-abc123 -n ai-agents
kubectl logs customer-support-agent-abc123 -n ai-agents --previous  # last crashed instance
kubectl logs -f customer-support-agent-abc123 -n ai-agents           # follow live

# 4. Exec into the running container
kubectl exec -it customer-support-agent-abc123 -n ai-agents -- /bin/sh
# Inside: test connectivity, check env vars, run debug scripts

# 5. Check resource usage
kubectl top pods -n ai-agents        # CPU and memory usage
kubectl top nodes                     # node-level resource usage

# 6. Check events at namespace level
kubectl get events -n ai-agents --sort-by='.lastTimestamp'

# ── Common Issues and Fixes ───────────────────────────────────────────────────

# CrashLoopBackOff: container exits immediately
# → Check logs for application error
# → Verify environment variables are set correctly
# → Verify the container image is correct
kubectl logs customer-support-agent-abc123 -n ai-agents --previous

# Pending: pod can't be scheduled
# → Check node resources (kubectl describe nodes | grep -A5 "Allocated")
# → Check if nodeSelector/tolerations match available nodes
# → Check if PVC is stuck (if using persistent storage)
kubectl describe pod stuck-pod -n ai-agents | grep -A20 "Events:"

# OOMKilled: Out of Memory
# → Increase memory limit in the Deployment spec
# → Profile the application to find memory leaks
kubectl describe pod oom-pod | grep "OOMKilled"
# Then update the Deployment:
kubectl set resources deployment customer-support-agent \
  --limits=memory=4Gi --requests=memory=1Gi -n ai-agents

# ImagePullBackOff: can't pull container image
# → Verify image name and tag are correct
# → Check if Artifact Registry is in the same project
# → Verify node SA has roles/artifactregistry.reader
kubectl describe pod imagepull-pod | grep -A5 "Events:"
```

---

## 6. Secrets Management — Never Use Plain ConfigMaps for Secrets

```bash
# Option 1: Kubernetes Secrets (base64 encoded, not encrypted at rest by default)
# Fine for non-sensitive config; NOT for API keys in enterprise environments

# Option 2: GCP Secret Manager + Kubernetes External Secrets Operator (RECOMMENDED)
# Secrets live in GCP Secret Manager; ESO syncs them into K8s secrets

# Install External Secrets Operator:
helm repo add external-secrets https://charts.external-secrets.io
helm install external-secrets external-secrets/external-secrets \
  -n external-secrets-system \
  --create-namespace

# Create a SecretStore pointing to GCP Secret Manager:
cat <<EOF | kubectl apply -f -
apiVersion: external-secrets.io/v1beta1
kind: SecretStore
metadata:
  name: gcp-secret-store
  namespace: ai-agents
spec:
  provider:
    gcpsm:
      projectID: my-gcp-project
      auth:
        workloadIdentity:
          clusterLocation: us-central1
          clusterName: my-cluster
          serviceAccountRef:
            name: my-ksa  # the K8s SA with Workload Identity configured
EOF

# Create an ExternalSecret that maps GCP secrets to K8s secrets:
cat <<EOF | kubectl apply -f -
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: api-keys
  namespace: ai-agents
spec:
  refreshInterval: 1h    # re-sync every hour
  secretStoreRef:
    name: gcp-secret-store
    kind: SecretStore
  target:
    name: api-keys        # name of the K8s secret to create
  data:
  - secretKey: anthropic-key      # key in the K8s secret
    remoteRef:
      key: ANTHROPIC_API_KEY      # name in GCP Secret Manager
  - secretKey: openai-key
    remoteRef:
      key: OPENAI_API_KEY
EOF
```

---

## 7. GKE Checklist — Before Going Live

```
CLUSTER CONFIGURATION:
□ Private cluster enabled (nodes have no public IPs)
□ Workload Identity enabled (no service account key files)
□ Binary Authorization enforced (only signed images)
□ Network Policy enabled (pod-to-pod traffic control)
□ Managed Prometheus enabled for metrics
□ Cluster autoscaler enabled with appropriate min/max

WORKLOAD CONFIGURATION:
□ All pods run as non-root user
□ Resource requests AND limits set on all containers
□ Liveness and readiness probes configured
□ HPA configured for variable-load services
□ PodDisruptionBudget configured for critical services
□ Rollout strategy: maxSurge=1, maxUnavailable=0 (zero-downtime deploys)

SECURITY:
□ Secrets from Secret Manager via External Secrets Operator
□ No sensitive values in ConfigMaps or environment variables
□ Network policies restrict pod-to-pod communication
□ Container images scanned for CVEs in Artifact Registry
□ Namespace-level RBAC (not cluster-admin for application service accounts)

OBSERVABILITY:
□ All applications write structured JSON logs to stdout
□ Cloud Logging receives logs via GKE managed logging
□ Dashboards created in Cloud Monitoring for CPU/memory/error rate
□ Alerting policies for: pod crash rate, OOM, HPA at max replicas
```
