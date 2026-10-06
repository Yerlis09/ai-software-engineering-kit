# Stack — Kubernetes

> Kit file — managed by `ai-project update`. Generic rules live in `rules/`; this file only adds Kubernetes-specific guidance.

Team platform: **RKE clusters, two environments — Staging and Prod**. The same immutable image tag is deployed to Staging, validated, then promoted to Prod. See `stacks/docker/README.md`, `stacks/ci-cd/README.md`, `agents/12-devops.md`, `agents/13-observability.md`.

## Recommended tooling

- `kubectl`, Helm 3 **or** Kustomize (one per project, not both mixed ad hoc).
- Validation: `kubeconform` (schema), `kube-linter` or Polaris / Checkov (best practices), `helm lint`.
- Secrets: Sealed Secrets (`kubeseal`) or External Secrets Operator (backed by a vault).
- Optional GitOps: Argo CD / Fleet (Rancher) watching the git.netsf.fr repository.

## Project structure

```
deploy/
  base/                 # Deployment, Service, ConfigMap, HPA, PDB, NetworkPolicy, ServiceAccount
    kustomization.yaml
  overlays/
    staging/            # namespace <app>-staging, replicas, resources, image tag, ingress host
    prod/               # namespace <app>-prod, higher replicas/limits, prod host
# or with Helm: chart/ + values.yaml, values-staging.yaml, values-prod.yaml
```

## Conventions

- One namespace per application and environment (`<app>-staging`, `<app>-prod`); labels `app.kubernetes.io/name`, `version`, `part-of`.
- **Image tags are immutable** (git SHA / semver); never `latest`. `imagePullPolicy: IfNotPresent`. Promotion = same tag (or digest) in the prod overlay.
- **Resources**: always set `requests` (scheduling) and memory `limits`; CPU limits per team policy (avoid aggressive CPU throttling).
- **Probes**: `readinessProbe` (ready to receive traffic), `livenessProbe` (deadlock detection only; cheap, no dependency checks), `startupProbe` for slow starts.
- **Rolling updates**: `maxUnavailable: 0`, `maxSurge: 1` (or 25%); graceful shutdown with `terminationGracePeriodSeconds` and a short `preStop` sleep so endpoints drain.
- **HPA** on CPU/memory or custom metrics; **PodDisruptionBudget** (`minAvailable: 1` or `maxUnavailable: 1`) for every multi-replica workload; replicas ≥ 2 in Prod with pod anti-affinity/topology spread.
- **ConfigMaps** for non-secret configuration; **Secrets** for credentials, mounted as env or files.
- Database migrations run as a `Job` (or Helm hook) before the new Deployment rolls out.
- Rollback: `kubectl rollout undo deployment/<name> -n <ns>` (or `helm rollback`), then fix forward in git.

## Security

- **Never commit plain `Secret` manifests** (base64 is not encryption). Use Sealed Secrets or External Secrets; no `.env` files with credentials.
- `securityContext`: `runAsNonRoot: true`, `runAsUser: 10001`, `readOnlyRootFilesystem: true`, `allowPrivilegeEscalation: false`, `capabilities.drop: ["ALL"]`, `seccompProfile.type: RuntimeDefault`. Mount `emptyDir` for `/tmp` if needed.
- **NetworkPolicies**: default-deny ingress (and egress where feasible) per namespace, then allow only required flows (ingress controller → app, app → DB).
- Dedicated `ServiceAccount` per app, `automountServiceAccountToken: false` unless the API is needed; minimal RBAC.
- Enforce Pod Security Admission `restricted` on app namespaces; deploy tokens scoped to a single namespace.

## Performance

- Right-size requests from observed usage (metrics-server / Prometheus); revisit after load tests.
- Set HPA min/max replicas sensibly; ensure readiness gates traffic until warm.
- Spread replicas across nodes (`topologySpreadConstraints`).

## Testing

- Render and validate manifests in CI: `kustomize build overlays/staging | kubeconform -strict` and a linter.
- Deploy to Staging, run smoke tests, then manual approval before promoting to Prod.
- Periodically test rollback and pod disruption (drain a node in Staging).

## Pitfalls

- `latest` tags or rebuilding images per environment.
- Liveness probes that check the database (cascading restarts during a DB blip).
- Missing requests/limits → noisy neighbours, OOMKills, evictions.
- Plain Secrets in git; secrets in ConfigMaps.
- Single replica without PDB in Prod; no graceful shutdown handling.

## Example

```yaml
apiVersion: apps/v1
kind: Deployment
metadata: { name: api, labels: { app.kubernetes.io/name: api } }
spec:
  replicas: 2
  selector: { matchLabels: { app.kubernetes.io/name: api } }
  strategy: { type: RollingUpdate, rollingUpdate: { maxUnavailable: 0, maxSurge: 1 } }
  template:
    metadata: { labels: { app.kubernetes.io/name: api } }
    spec:
      automountServiceAccountToken: false
      securityContext: { runAsNonRoot: true, runAsUser: 10001, seccompProfile: { type: RuntimeDefault } }
      containers:
        - name: api
          image: registry.example.internal/team/api:3f2c1ab   # immutable tag, set by overlay
          ports: [{ containerPort: 8000 }]
          envFrom: [{ configMapRef: { name: api-config } }, { secretRef: { name: api-secrets } }]
          resources: { requests: { cpu: 100m, memory: 256Mi }, limits: { memory: 512Mi } }
          readinessProbe: { httpGet: { path: /readyz, port: 8000 }, periodSeconds: 5 }
          livenessProbe: { httpGet: { path: /healthz, port: 8000 }, periodSeconds: 10, failureThreshold: 3 }
          startupProbe: { httpGet: { path: /healthz, port: 8000 }, failureThreshold: 30, periodSeconds: 2 }
          securityContext:
            readOnlyRootFilesystem: true
            allowPrivilegeEscalation: false
            capabilities: { drop: ["ALL"] }
          volumeMounts: [{ name: tmp, mountPath: /tmp }]
      volumes: [{ name: tmp, emptyDir: {} }]
```
