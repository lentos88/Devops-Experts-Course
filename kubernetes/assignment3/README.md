# Kubernetes - Week 3

Kubernetes homework from the DevOps Experts course: Deployments and NodePort Services, imperative (kubectl) vs. declarative (YAML) deployment, resource requests and limits, environment variables and port-forwarding.

## Environment
- Kubernetes in Docker Desktop (kind mode, node `desktop-control-plane`), managed with `kubectl` from PowerShell
- A dedicated namespace per lesson (`class3` for Assignment 3)
- In kind mode a NodePort is not reachable from Windows, so I accessed the apps with `kubectl port-forward`

## Assignment 3: Superset and Airflow

**Task:** Deploy Apache Superset with `kubectl`, expose it, delete it and re-create it from a YAML file. Add Airflow to the same YAML, then add resources and an `APPLICATION` environment variable to both pods.

**Files:** [superset.yaml](superset.yaml): Deployment + NodePort Service for each app

### Tasks 1–4: imperative (kubectl commands)

```bash
# Tasks 1–2: create and inspect
kubectl create deployment superset --image=amancevice/superset:6.1.0
kubectl get pods
kubectl describe pod superset

# Task 3: expose from outside the cluster
kubectl expose deployment superset --type=NodePort --port=8088
kubectl get svc superset                 # 8088:32074/TCP
kubectl describe service superset        # Endpoints: 10.244.0.10:8088
kubectl port-forward svc/superset 4444:8088   # the app did not respond

# Troubleshooting
kubectl logs superset-5b8448c68f-5s9c5 --tail 30   # Refusing to start due to insecure SECRET_KEY
kubectl set env deployment/superset SUPERSET_SECRET_KEY=<secret-key>
kubectl get pods             # a new pod: superset-f674bcc8f-2qdg2
kubectl port-forward svc/superset 4444:8088   # 500 Internal Server Error
kubectl exec -it deployment/superset -- superset-init   # creates the admin user and the DB tables
kubectl port-forward svc/superset 4444:8088   # http://localhost:4444

# Task 4: delete
kubectl delete deployment superset
kubectl delete service superset
kubectl get deployment,svc,pods
```
**Result**: Superset UI opened on localhost:4444 and I logged in with the admin user created by superset-init.

### Tasks 5–7: declarative (YAML)
```bash
# Task 5: Superset from a YAML file
kubectl apply -f superset.yaml            # deployment configured, service created
kubectl get deployment                    # superset 0/1
kubectl describe service superset         # Selector: name=superset, Endpoints: <empty>
# fixed the Service selector to app: superset
kubectl apply -f superset.yaml            # deployment unchanged, service configured
kubectl get pods                          # CrashLoopBackOff
kubectl logs superset-f674bcc8f-8fxsl --previous --tail 40   # Pending database migrations
kubectl exec -it deployment/superset -- superset-init

# Task 6: check both resources
kubectl get pods                          # Running
kubectl get deployment                    # superset 1/1
kubectl get svc superset                  # 8088:32202/TCP
kubectl describe service superset         # Selector: app=superset, Endpoints: 10.244.0.13:8088
kubectl port-forward svc/superset 4444:8088   # http://localhost:4444

# Task 7: Airflow added to the same YAML
kubectl apply -f superset.yaml            # error: line 17: mapping values are not allowed
kubectl apply -f superset.yaml            # superset unchanged, airflow created
kubectl get pods -w
kubectl get svc airflow                   # 8080:30322/TCP
kubectl port-forward svc/airflow 5555:8080    # http://localhost:5555
```
**Result:** `apply` only changes what differs from the cluster: after the selector fix only the Service was `configured`, and when Airflow was added Superset stayed `unchanged` while the Airflow resources were `created`. Both UIs opened in the browser.

### Tasks 8–9: resources and environment variables

| | Requests | Limits (required) | Limits (final) |
|---|---|---|---|
| CPU | `250m` (¼ core) | `500m` (½ core) | `500m` |
| Memory | `250Mi` | `500Mi` | `1Gi` |

```bash
# Task 8: resources (requests 250m/250Mi, limits 500m/500Mi) and the APPLICATION env var
kubectl apply -f superset.yaml      # superset configured, airflow configured
kubectl get pods -w                 # both pods: OOMKilled -> CrashLoopBackOff
kubectl describe pod airflow-5df8d947b9-ktp88    # Last State: OOMKilled, Exit Code: 137
kubectl describe pod superset-65d9686f7-8269n    # Last State: OOMKilled, Exit Code: 137
# raised the memory limit to 1Gi
kubectl apply -f superset.yaml       # new pods for both apps, Running

# Task 9: check the APPLICATION variable
kubectl exec deployment/airflow -- printenv APPLICATION    # airflow
kubectl exec deployment/superset -- printenv APPLICATION   # superset
kubectl exec -it airflow-6dd665c467-sqw8k -- bash
echo $APPLICATION                                          # airflow
kubectl exec -it superset-7f98b88755-fb558 -- bas  # failed: Superset was OOMKilled again
```
**Result:** The APPLICATION variable is set in both pods. With the required 500Mi memory limit both apps were OOMKilled, so I raised the limit to 1Gi. Airflow then ran stably; Superset was still OOMKilled after a few minutes.

> **Note:** In the YAML in this repo, `SUPERSET_SECRET_KEY` is a placeholder (`CHANGE_ME`); replace it with your own random key before applying (e.g. `openssl rand -base64 42`). For this homework it was a plain environment variable; in a real setup it belongs in a Kubernetes Secret.

### Bonus
- Opened both apps in the browser with `port-forward` (Superset on 4444, Airflow on 5555).
- **Superset** is an open-source BI platform for exploring data and building charts and dashboards on top of SQL databases. **Airflow** schedules and monitors data pipelines, defined in Python as DAGs.

## Issues & fixes

**Superset: "Refusing to start due to insecure SECRET_KEY"**
Found with `kubectl logs`. Superset will not run with its default secret key. Fix: set `SUPERSET_SECRET_KEY` (`kubectl set env`, later in the YAML).

**Superset: 500 Internal Server Error, then `CrashLoopBackOff` with "Pending database migrations"**
The metadata database had no tables. Fix: `kubectl exec -it deployment/superset -- superset-init`. I had to run it again after re-creating Superset from the YAML: the metadata DB is SQLite inside the container, with no volume, so a new pod starts with an empty database.

**Service with an empty `Endpoints` list**
`kubectl describe service` showed `Selector: name=superset` and no endpoints. The pods are labeled `app=superset`, so the Service matched nothing. Fix: changed the selector to `app: superset`.

**`kubectl apply`: "error converting YAML to JSON: mapping values are not allowed in this context"**
Wrong indentation (a `value:` line was not aligned under its `- name:`). Fix: aligned the keys; YAML structure is defined by indentation only.

**Pods OOMKilled (exit code 137) with a 500Mi memory limit**
`kubectl describe pod` showed `Reason: OOMKilled`, `Exit Code: 137` (128 + 9, SIGKILL). Both apps need more than 500Mi. Fix: raised the memory limit to `1Gi`. Airflow then ran with 0 restarts; Superset was still OOMKilled after a few minutes, so it needs even more memory.

**`port-forward svc/<pod-name>`: "services ... not found"**
I passed the pod name. `svc/` expects the Service name: `kubectl port-forward svc/superset 4444:8088`.

**Pod showed `Running` / `Ready: True`, but the app did not respond**
Only the gunicorn master process was alive; the workers kept exiting (seen in `kubectl logs`). Kubernetes checks only that the main process is running, not that the app serves requests. Lesson: `Running` ≠ healthy. This is what readiness and liveness probes are for (Assignment 4).


