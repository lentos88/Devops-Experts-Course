# Assignment 5 - Helm

Helm charts end to end: building a custom chart, values and upgrades, rollbacks, publishing to Docker Hub (OCI), subcharts with a toggle, and installing a third-party chart from ArtifactHub.

**Environment:** WSL2 Ubuntu 24.04, minikube, Helm v4, namespace `class5`.

```
assignment5/
└── myapi/
    ├── Chart.yaml
    ├── values.yaml
    ├── values-staging.yaml
    ├── charts/
    │   └── worker/          # local subchart (Exercise 4)
    └── templates/
        ├── deployment.yaml
        ├── _helpers.tpl
        └── NOTES.txt
```

---

## Exercise 1 - Build and explore your first chart

```bash
helm create myapi
cd myapi
code .
```

**Changes:**

| File | Change |
|---|---|
| `Chart.yaml` | `version: 0.2.0`, `appVersion: "2.5.0"` |
| `values.yaml` | `image: httpd:alpine`, `replicaCount: 4`, new value `team: backend` |
| `templates/deployment.yaml` | pod template label `team: {{ .Values.team }}` |
| `templates/_helpers.tpl` | new label in `myapi.labels`: `app.kubernetes.io/chartVersion: {{ .Chart.Version \| quote }}` |
| `templates/NOTES.txt` | `This release is managed by the {{ .Values.team }} team.` |

The `team` label was added to the **pod template labels only**, not to the selector. A Deployment's selector is immutable. Changing it would break `helm upgrade`.

```bash
helm template myapi ./  # render locally, nothing is sent to the cluster
helm lint ./
helm install myapi ./ --dry-run
helm install myapi ./   # NOTES message is printed
kubectl get pods 
kubectl get pods -l team=backend # pods carry team=backend
helm list
helm status myapi
```

**Q: What is the difference between `version` and `appVersion`?**
- `version` is the version of the **chart**, meaning the packaging: templates, values and structure. It must be bumped on every chart change.
- `appVersion` is the version of the **application** the chart deploys. In this chart it is also the default image tag when `image.tag` is empty.
- They change independently. In Exercise 4 the chart went from 0.2.0 to 0.3.0 (new subchart), while `appVersion` stayed at 2.5.0.

---

## Exercise 2 - Values, upgrades and rollbacks

`values-staging.yaml` (inside the chart folder):
```yaml
replicaCount: 6
team: staging
```

```bash
helm upgrade myapi ./myapi -f myapi/values-staging.yaml                     # 6 replicas, team=staging
helm upgrade myapi ./myapi -f myapi/values-staging.yaml --set replicaCount=2  # 2 replicas, team=staging
helm get all myapi
helm get manifest myapi --revision 3
helm get values myapi      # user-supplied values only
helm get values myapi --all # computed values (everything merged)
helm history myapi
kubectl get secrets 
helm rollback myapi 1   # back to 4 replicas, team=backend
```

**Q: Which value wins, `-f` or `--set`?**
`--set` wins. The precedence is `values.yaml` < `-f file` < `--set`, and the last, most specific source overrides the earlier ones. Result: `replicaCount=2` comes from `--set`, and `team=staging` comes from the file, because `--set` didn't touch it.

**Q: How do the active values differ from the YAML files?**
The YAML files are only the input on my disk. The active values are the result of merging them, and they are stored **in the cluster** with the release. `helm get values` shows only what I supplied (`-f` / `--set`), and `--all` shows the full merged result. If I edit a file after installing, nothing changes in the cluster until I run `upgrade` again.

**Q: Where does Helm store revisions?**
As Kubernetes Secrets in the release's namespace, one per revision: `sh.helm.release.v1.myapi.v1`, `.v2`, and so on.

**Rollback:** `helm rollback myapi 1` doesn't go back in time. It creates a **new** revision with the configuration of revision 1. The old revisions are marked `superseded`.

---

## Exercise 3 - Publish and consume the chart

```bash
helm package ./myapi                                              # -> myapi-0.2.0.tgz
helm registry login registry-1.docker.io -u yelenazamansky         # token entered interactively, never saved in files
helm push myapi-0.2.0.tgz oci://registry-1.docker.io/yelenazamansky

# prove it's really published: pull into another folder
cd ~/helm-pull-test
helm pull oci://registry-1.docker.io/yelenazamansky/myapi --version 0.2.0 --untar

helm uninstall myapi
helm list               # myapi is gone
kubectl get secrets -l owner=helm,name=myapi   # its revision secrets are gone too

# reinstall from Docker Hub (not from the local folder), overriding replicas
helm upgrade -i myapi oci://registry-1.docker.io/yelenazamansky/myapi --version 0.2.0 --set replicaCount=3

helm get values myapi          # replicaCount: 3
kubectl get pods               # 3 pods
```

- The package name `myapi-0.2.0.tgz` comes from `name` + `version` in `Chart.yaml`.
- The **digest** printed by `push` and `pull` is the same. That proves it's the identical artifact.
- `helm uninstall` also deletes the release's revision secrets, so the history starts over from revision 1.

---

## Exercise 4 - Subchart with a toggle

```bash
cd myapi
cd charts
helm create worker
```

**Worker subchart (`charts/worker`):**
- `values.yaml`: `image: busybox:latest`, `replicaCount: 1`, `livenessProbe: {}` and `readinessProbe: {}`.
- `templates/deployment.yaml`: added `command: ["sh", "-c", "while true; do echo worker is running; sleep 30; done"]`.

**Why the extra changes?** busybox has no long-running process, so without a command the container exits immediately and goes into CrashLoopBackOff. It also has no HTTP server, so the default HTTP probes from `helm create` would fail.

**Wiring into the parent:**

`myapi/Chart.yaml` (chart version bumped to `0.3.0`):
```yaml
dependencies:
  - name: worker
    version: 0.1.0
    condition: worker.enabled
```
`myapi/values.yaml`:
```yaml
worker:
  enabled: true
```

Helm automatically renders any chart inside `charts/`. The `condition` is what makes it possible to turn it off.

```bash
cd ..
helm dependency update ./   # "did not declare a repository. Assuming it exists in the charts directory"
cd ..
helm dependency list ./myapi   # worker  0.1.0  unpacked
helm upgrade -i myapi ./myapi
kubectl get pods               # 4 x myapi + 1 x myapi-worker
```

**Toggle test:**
```bash
helm upgrade myapi ./myapi --set worker.enabled=false   # worker pod terminated
helm upgrade myapi ./myapi --reset-values    # worker back
kubectl get pods 
```

**Finding: `helm upgrade` carries over values.**
After the first upgrade only 3 `myapi` pods were running, even though `values.yaml` says 4. `helm get values myapi` showed `replicaCount: 3`, left over from the `--set` in Exercise 3. When `helm upgrade` runs **without** any `-f`/`--set`, Helm reuses the previous user-supplied values. Fix: pass values explicitly, or use `--reset-values`. After that, `helm get values` returned `null` and 4 pods were running.

---

## Exercise 5 - Installing from ArtifactHub

Chart: **kube-prometheus-stack** (prometheus-community), a monitoring stack with Prometheus, Grafana, Alertmanager, the Prometheus Operator, node-exporter and kube-state-metrics.

```bash
kubectl create ns monitoring
kubectl config set-context --current --namespace=monitoring
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm install my-kube-prometheus-stack prometheus-community/kube-prometheus-stack --version 93.6.1
kubectl get pods
helm list -A     # releases in monitoring, class5 and default
```

- Namespace names allow only lowercase letters, digits and `-`. `class5_5` would be rejected.
- `2/2` and `3/3` in READY mean pods with sidecar containers.
- `alertmanager-...-0` and `prometheus-...-0` are StatefulSets. node-exporter is a DaemonSet, one pod per node.
- Installing from a repo doesn't put files in the working directory. The chart goes to Helm's cache (`~/.cache/helm/repository`), and the release state lives in the cluster.

**Cleanup:**
```bash
helm uninstall my-kube-prometheus-stack
kubectl get crd | grep monitoring.coreos.com  # 10 CRDs are still there
kubectl get crd -o name | grep monitoring.coreos.com | xargs kubectl delete
kubectl config set-context --current --namespace=class5
kubectl delete ns monitoring
```

`helm uninstall` does **not** remove CRDs. Deleting a CRD deletes every custom resource of that type in the whole cluster, so Helm leaves that decision to the operator. I verified that nothing else used them and removed them manually.

---

## Key takeaways

- **Chart vs release:** the chart is the package; a release is one installed instance of it in a namespace.
- **Precedence:** `values.yaml` < `-f` < `--set`.
- **Values live in the cluster**, not in my files. `helm get values` shows what is actually active.
- **`helm upgrade` without values reuses the previous ones.** To be predictable, I pass values explicitly or use `--reset-values`.
- **Rollback = a new revision.** History is kept as Secrets.
- **Subcharts in `charts/` are always rendered.** A `condition` makes them optional.
- **`helm uninstall` leaves CRDs behind.** Cleaning them up is a manual, deliberate step.
