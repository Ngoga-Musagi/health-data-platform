# Design Appendix

This document summarizes design considerations for production evolution, CI/CD, security, MLOps, and cloud deployment (AWS). It is intended to stay within a concise, assessment-friendly length (max ~2 pages).

---

## Platform Evolution (Kubernetes)

Each service would be deployed as a Kubernetes workload (Deployments, Jobs, CronJobs) with Helm charts. Object storage and databases would use managed services (e.g. S3, RDS on AWS). Orchestration would enforce pipeline order (ingest → transform → dbt → ML) via Argo Workflows or AWS Step Functions, with fail-fast behavior and central logging.

---

## Environment Separation

Separate dev, staging, and prod environments using isolated namespaces and databases. Config and secrets would be environment-specific (e.g. different RDS instances, S3 buckets, or prefixes). Feature branches could target dev; main branch promotes to staging and then prod after approval.

---

## CI/CD

- **Lint and tests on PR**: Unit tests and (where feasible) integration tests run in CI; dbt tests can run against a test warehouse.
- **Build images on merge**: Docker images for ingestion, transformer, dbt, and ML built and pushed to a registry.
- **Deploy via GitOps**: Kubernetes manifests (or Helm values) updated from Git; Argo CD or equivalent applies changes.
- **dbt tests gate promotion**: dbt test runs in pipeline; failures block promotion to production analytics.

---

## Security

- **Secrets**: Stored in a vault (e.g. AWS Secrets Manager, HashiCorp Vault); injected at runtime into pods or jobs.
- **Encryption**: Data at rest (S3, RDS) and in transit (TLS); use of KMS where applicable.
- **Network**: Private subnets for compute and data stores; security groups / network policies restrict access by role.
- **Access**: Least-privilege IAM and RBAC; audit logging for sensitive operations.

---

## MLOps Evolution

- **Current**: Batch training jobs; MLflow experiment tracking; model artifacts stored in object storage.
- **Short-term**: Model registry (e.g. MLflow Model Registry); scheduled retraining via orchestration.
- **Medium-term**: Feature store (e.g. SageMaker Feature Store); drift detection; canary deployments.
- **Long-term**: Online inference endpoints; automated rollback via model versioning; full lifecycle governance.

---

## Cloud Deployment (AWS)

### Overview

The local Docker Compose–based platform represents a single-node development environment. In a production AWS deployment, the platform would be migrated to managed and container-native AWS services to improve scalability, reliability, security, and operational efficiency.

### AWS Service Mapping

| Platform Component        | AWS Service                | Rationale                                              |
|---------------------------|----------------------------|--------------------------------------------------------|
| Docker Compose            | Amazon EKS                 | Managed Kubernetes for orchestration and scaling      |
| MinIO (Object Storage)    | Amazon S3                  | Durable, scalable raw data storage                     |
| PostgreSQL                | Amazon RDS (PostgreSQL)    | Managed relational warehouse                           |
| Ingestion Service         | EKS Job / CronJob          | Stateless batch ingestion                              |
| Transformation & DQ      | EKS Job                    | Isolated, repeatable data processing                   |
| dbt Analytics             | EKS Job                    | Deterministic analytics builds                         |
| ML Training               | EKS Job                    | Scalable batch ML workloads                            |
| MLflow                    | EKS + S3 backend           | Experiment tracking and artifact storage               |
| Loki / Promtail           | CloudWatch + Fluent Bit    | Managed centralized logging                            |
| Grafana                   | Amazon Managed Grafana     | Secure visualization layer                             |

### AWS Architecture (Logical View)

```
WHO GHO API
   ↓
EKS Job (Ingestion)
   ↓
Amazon S3 (Raw Zone)
   ↓
EKS Job (Transform + Data Quality)
   ↓
Amazon RDS (PostgreSQL Warehouse)
   ↓
dbt (EKS Job)
   ↓
ML Training Job
   ↓
MLflow (Artifacts in S3)

Logs → Fluent Bit → CloudWatch → Managed Grafana
```

### Orchestration & Workflow (AWS)

Pipeline execution would be orchestrated using **Argo Workflows** (on EKS) or **AWS Step Functions**. The workflow enforces: **Ingest → Transform & Data Quality → dbt → ML Training**. Failures at any stage halt downstream execution and are logged centrally.

### Security (AWS)

- **IAM Roles for Service Accounts (IRSA)**: Each Kubernetes Job runs with least-privilege access to S3, RDS, and MLflow.
- **AWS Secrets Manager**: Database credentials and MLflow secrets injected at runtime.
- **Encryption**: S3 (SSE-KMS); RDS (encryption at rest); TLS in transit.
- **Network**: Private subnets for EKS and RDS; security groups restrict access by service role.

### Scalability (AWS)

- **Horizontal scaling**: Multiple ingestion or transformation jobs can run in parallel.
- **Data**: Raw data partitioned by ingestion date in S3; warehouse tables partitioned by year.
- **Compute**: EKS auto-scaling node groups; GPU-enabled nodes for ML if required.

### Observability (AWS)

- **Logs**: Fluent Bit → CloudWatch Logs; queried via Amazon Managed Grafana.
- **Metrics**: Kubernetes metrics via CloudWatch Container Insights.
- **Alerting**: CloudWatch alarms on job failures and latency.

### Why AWS Managed Services

Managed AWS services reduce operational overhead, improve reliability, and provide built-in security and scalability. This allows the platform team to focus on data quality, analytics, and ML value delivery rather than infrastructure maintenance.


