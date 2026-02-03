# Design Appendix

This document summarizes design considerations for production evolution, CI/CD, security, and MLOps. It is intended to stay within a concise length (max ~2 pages).

## High-Level Architecture

![High-Level Architecture](Architecture-c.png)

---

## Platform

### Kubernetes deployment approach

Each service is deployed as a Kubernetes workload (Deployments, Jobs, CronJobs) using Helm charts. Object storage and the database use managed services (e.g. S3, RDS). Pipeline order (ingest → transform → dbt → ML) is enforced by Argo Workflows or Step Functions with fail-fast behavior and central logging. EKS (or equivalent) runs ingestion, transformation, dbt, and ML jobs; MLflow runs on the cluster with an S3 artifact backend.

### Environment separation

Use separate dev, staging, and prod environments with isolated namespaces and databases. Config and secrets are environment-specific (different RDS instances, S3 buckets or prefixes). Feature branches target dev; the main branch promotes to staging and then to prod after approval and gates (tests, dbt tests).

---

## CI/CD & Automation

### How would you implement CI/CD for this platform?

- **On PR:** Lint (e.g. Ruff/Black), unit tests, and (where feasible) integration tests in CI; dbt tests against a test warehouse.
- **On merge:** Build and push Docker images (ingestion, transformer, dbt, ML) to a container registry.
- **Deploy:** GitOps (Argo CD or Flux) applies Kubernetes/Helm changes from Git; pipeline jobs are triggered by schedule or events.

### How would changes be tested and promoted safely?

- **Gates:** Unit and integration tests must pass before merge. dbt test runs in the pipeline; failures block promotion.
- **Promotion path:** Dev → staging (auto or on merge to main) → prod (manual approval or automated after staging validation). Staging runs the full pipeline against a copy of prod-like data.
- **Rollback:** Revert Git commits and let GitOps sync, or pin to previous image tags for jobs.

---

## Security

### Secrets

Secrets (DB credentials, API keys, MLflow credentials) are stored in a vault (e.g. AWS Secrets Manager, HashiCorp Vault) and injected at runtime into pods/jobs via environment variables or mounted files. No secrets in image or Git.

### Encryption

- **At rest:** S3 (SSE-KMS) and RDS encryption; object and DB encryption enabled by default.
- **In transit:** TLS for all external and internal service-to-service communication; ingress TLS termination.

### Access Control

Least-privilege IAM and Kubernetes RBAC; IRSA for EKS pods to access AWS services. Network policies and security groups restrict access by role. Audit logging for sensitive operations (DB, S3, model registry).

---

## MLOps

### Model versioning

Use MLflow Model Registry (or equivalent): each trained model is registered with a version and stage (Staging/Production). Versioning is tied to Git commit and pipeline run ID for reproducibility.

### Deployment

- **Batch:** Production model version is read from the registry by scheduled training/scoring jobs.
- **Online (evolution):** Serve via a dedicated inference service (e.g. Seldon, KServe, or SageMaker endpoints) that loads the promoted model version from the registry.

### Monitoring

Track inference latency, error rates, and (where applicable) feature and prediction distributions. Drift detection on inputs and outputs; alerts on degradation or threshold breaches. MLflow (and/or Prometheus/Grafana) for metrics and dashboards.

### Rollback

Pin the Model Registry to a previous production version and redeploy the inference service (or re-run batch jobs with the previous version). Automated rollback triggers when monitoring detects regression (e.g. error spike or drift).

---

**Cloud (e.g. AWS):** Production would map to EKS (orchestration), S3 (raw/store), RDS (warehouse), Secrets Manager, and managed logging (e.g. CloudWatch + Managed Grafana). Pipeline logic and security approach above apply; IRSA and private subnets for least-privilege access.
