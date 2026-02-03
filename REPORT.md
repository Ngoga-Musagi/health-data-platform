# Design Decisions & Trade-offs

## Dataset Choice

The WHO Global Health Observatory dataset was selected due to its authoritative coverage of health indicators across low- and middle-income countries and its realistic data quality challenges (nulls, duplicates, schema variability). It aligns with the health data platform scope and is publicly available without authentication.

## Architecture

The platform follows a layered architecture separating raw ingestion, transformation, analytics modeling, and ML workloads. This separation improves reliability, debuggability, and scalability. Each stage has clear inputs and outputs and can be evolved or scaled independently.

## Data Quality

Data validation is enforced during the transformation stage (null checks, duplicate checks) and again in the analytics layer via dbt tests on source columns. Failures block downstream execution and are clearly logged. This ensures that only validated data reaches the warehouse and analytics models.

## Analytics & ML

dbt provides a semantic analytics layer (source → staging → mart) that is consumed by a lightweight ML training job. The mart table `mart_country_life_expectancy` is analytics- and ML-feature-friendly. MLflow is used for experiment tracking (parameters, metrics, artifacts), enabling future extension to full MLOps (registry, retraining, deployment).

## Observability

All services log to stdout. Logs are centrally collected via Promtail and Loki and visualized in Grafana. This supports debugging and traceability across ingestion, transformation, analytics, and ML stages.

## Orchestration

A Makefile was selected as the primary orchestration mechanism to provide a simple, explicit, and dependency-aware execution flow that can be reused locally and in CI pipelines. The pipeline order is: ingest → transform → dbt run → dbt test → ML.

## Testing

A lightweight testing strategy was implemented: a unit test validates data quality logic (validation function), and an integration-style test verifies that data was successfully loaded into the warehouse after pipeline execution. This balances confidence in correctness with execution simplicity and CI/CD compatibility.

## Assumptions and Limitations

**Assumptions (trade-offs):** WHO GHO API is stable and publicly available; data is batch-only (no real-time requirement); analytics and ML can run on a single mart table; Docker Compose is sufficient for assessment/demo. We assume future production will use managed storage (S3, RDS) and Kubernetes.

**Limitations:** Single-node deployment (Docker Compose). No incremental processing; each run ingests and processes the full dataset. No access control or authentication on services. MLflow uses SQLite and local artifact storage (suitable for assessment; production would use a managed store).

## Scaling Strategy

- **Kubernetes deployment**: Each service becomes a workload (Jobs/CronJobs); orchestration via Argo Workflows or Step Functions.
- **Incremental ingestion**: Partition by date; only new partitions processed.
- **Partitioned warehouse tables**: By year or ingestion date for efficient queries.
- **Distributed ML**: Parallel training jobs; GPU nodes if required.
- **Cloud**: See DESIGN_APPENDIX.md for AWS (and optional GCP) mapping (S3, RDS, EKS, managed logging, etc.).

## Security Approach

- **Secrets:** Supplied via environment variables in the current setup; in production, use a secrets store (e.g. AWS Secrets Manager, HashiCorp Vault) and inject at runtime.
- **Transport and access:** TLS termination at ingress (future); role-based database access and least-privilege IAM for cloud deployment.
- **Network:** Private subnets for compute and data; security groups/network policies to restrict access by role.

## ML Evolution

- **Current:** Batch training jobs; MLflow for experiment tracking (parameters, metrics, artifacts); model artifacts in object storage.
- **Short-term:** Model registry (e.g. MLflow Model Registry); scheduled retraining via orchestration (CronJobs/Argo).
- **Medium-term:** Feature store; data/model drift detection; canary or shadow deployments for new models.
- **Long-term:** Online inference endpoints; automated rollback via model versioning; full lifecycle governance and A/B testing.
