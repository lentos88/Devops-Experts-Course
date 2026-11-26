# Kubernetes - Week 4

Kubernetes homework from the DevOps Experts course: persistent storage (PV/PVC), ConfigMaps, CronJobs with a sidecar, and liveness and readiness probes.

## Environment
- Kubernetes in Docker Desktop (kind mode, node `desktop-control-plane`), managed with `kubectl` from PowerShell
- Namespace `class4`

## Assignment 4: Storage, configuration and probes for an Nginx deployment

### Task 1: Storage (PersistentVolume and PersistentVolumeClaim)

**File:** [task1-storage.yaml](task1-storage.yaml): a 2Gi PV (`hostPath`), a 1Gi PVC, and an Nginx Deployment that mounts the PVC at `/usr/share/nginx/html`.

```bash
kubectl apply -f task1-storage.yaml
kubectl get pv nginx-pv                    # STATUS: Bound
kubectl get pvc nginx-pv-claim             # STATUS: Bound, CAPACITY: 2Gi
kubectl describe pod -l app=nginx-task     # Mounts: /usr/share/nginx/html from task-pv-storage

# Write a sample file to the mounted volume
kubectl exec -it deployment/nginx-deployment -- sh
cd /usr/share/nginx/html/
echo 1 > index.html
cat index.html
exit

# Check persistence: delete the pod, the Deployment creates a new one
kubectl get pods -l app=nginx-task
kubectl delete pod nginx-deployment-756b8df8fb-sdw9g
kubectl get pods -l app=nginx-task          # new pod ...-m6vcw, same ReplicaSet hash (756b8df8fb)
kubectl exec deployment/nginx-deployment -- cat /usr/share/nginx/html/index.html   # 1
```
**Result:** The file survived the pod deletion. It is stored on the PV, not inside the container.

**Notes:**
- The PVC requested 1Gi but is bound to the whole 2Gi PV: binding is one-to-one.
- `storageClassName: manual` on both the PV and the PVC makes the PVC bind to my PV. Without it, the default StorageClass (`standard` in kind) would provision a new PV automatically.

### Task 2: ConfigMap

**File:** [task2-configmap.yaml](task2-configmap.yaml): a ConfigMap with two keys (`APP_ENV`, `APP_OWNER`) and the same Nginx Deployment from Task 1, now loading the ConfigMap as environment variables with `envFrom`. I used the environment-variables option (mounting a config file was optional).

```bash
# Step 1: only the ConfigMap in the file
kubectl apply -f task2-configmap.yaml          # configmap/nginx-config created
kubectl get configmaps
kubectl describe configmaps nginx-config       # APP_ENV: homework_4, APP_OWNER: yelena_zamansky

# Step 2: envFrom added to the Deployment in the same file
kubectl apply -f task2-configmap.yaml          # configmap unchanged, deployment configured
kubectl get pods -l app=nginx-task             # new pod ...-7658487848-mrcz4 (new ReplicaSet)

# Check that the data from Task 1 is still on the PV after the pod was recreated
kubectl exec -it deployment/nginx-deployment -- sh
cat /usr/share/nginx/html/index.html           # 1
exit

# Check the environment variables loaded from the ConfigMap
kubectl exec deployment/nginx-deployment -- printenv APP_ENV APP_OWNER   # homework_4, yelena_zamansky
```
**Result:** The ConfigMap values were loaded as environment variables. Adding `envFrom` changed the pod template, so the Deployment created a new ReplicaSet. The file from Task 1 was still on the PV in the new pod.

**Note:** Environment variables are read only when the container starts. If the ConfigMap changes later, the running pod keeps the old values until it is restarted (`kubectl rollout restart deployment/nginx-deployment`).

### Task 3: CronJob with a sidecar

**File:** [task3-cronjob.yaml](task3-cronjob.yaml): a PV and PVC for the logs, and a CronJob that runs every minute (`* * * * *`). Each run creates a pod with two containers that share an `emptyDir` volume:
- `date-time` writes the current date to `/logs/date.log` (`emptyDir`)
- `log-sidecar` appends that file to `/pv-logs/date.log` (the PV)

```bash
# Part 1: CronJob that writes the date to a log file every minute
kubectl apply -f task3-cronjob.yaml                 # cronjob.batch/date-time-cronjob created
kubectl get cronjob date-time-cronjob
kubectl get pods                                    # a new pod every minute, 0/1 Completed
kubectl logs date-time-cronjob-29912443-bvfv2       # Sun Nov 15 12:43:01 UTC 2026 (one line)
# Each pod has only one line: the log file is inside the container and is lost when the pod ends.

# Part 2: sidecar writes the logs to a persistent volume
# Added PV + PVC for the logs
kubectl apply -f task3-cronjob.yaml                 # pv created, pvc created, cronjob unchanged
kubectl get pv cron-logs-pv                         # Bound
kubectl get pvc cron-logs-pvc                       # Bound

# Added a shared emptyDir volume and a sidecar container to the CronJob pod
kubectl apply -f task3-cronjob.yaml                 # cronjob configured
kubectl get pods                                    # date-time-cronjob pods: 0/2 Completed
kubectl logs date-time-cronjob-29912698-98pmw -c log-sidecar   # 2 lines
kubectl logs date-time-cronjob-29912703-kp9h9 -c log-sidecar   # 7 lines

# Stop the CronJob after the test
kubectl delete cronjob date-time-cronjob
```

**Result:** In Part 1 each pod showed one line. In Part 2 the log file on the PV grows with every run (2 lines, then 7 lines). `0/2 Completed` is the normal state for a finished Job pod: both containers exited.

**Notes:**
- `emptyDir` shares files between containers in the same pod and is deleted with the pod; the PV keeps the data across runs.
- A Job's pods must end, so `restartPolicy` is `OnFailure` (not `Always`).
- `sleep 5` in the sidecar is a simple way to let the main container finish writing first.

### Task 4: Liveness probe

**File:** [task4-liveness-probe.yaml](task4-liveness-probe.yaml): the Deployment from Task 2 with a liveness probe: `httpGet /healthz` on port 80, `initialDelaySeconds: 5`, `periodSeconds: 10`, `failureThreshold: 3`.

Nginx has no built-in `/healthz`, so I created a `healthz` file on the PV for Nginx to serve.

```bash
# Create the health check file on the PV (before adding the probe)
kubectl exec -it deployment/nginx-deployment -- sh
echo ok > /usr/share/nginx/html/healthz
exit

# Add the liveness probe
kubectl apply -f task4-liveness-probe.yaml     # configmap unchanged, deployment configured
kubectl get pods -l app=nginx-task             # new pod ...-f7f6d557f-swp8w
kubectl describe pod -l app=nginx-task         # Liveness: http-get http://:80/healthz delay=5s period=10s #failure=3, Restart Count: 0

# Test: make the probe fail
kubectl exec deployment/nginx-deployment -- rm /usr/share/nginx/html/healthz
kubectl get pods -l app=nginx-task -w          # RESTARTS 3, 4, CrashLoopBackOff, 5, 6
kubectl describe pod -l app=nginx-task
# Unhealthy  Liveness probe failed: HTTP probe failed with statuscode: 404
# Killing    Container task-pv-container failed liveness probe, will be restarted
# BackOff    Back-off restarting failed container

# Recover: apply the Task 2 version (no probe), recreate healthz, apply the probe again
kubectl apply -f ..\Task2\task2-configmap.yaml   # pod ...-7658487848-... (the Task 2 ReplicaSet again)
kubectl exec -it deployment/nginx-deployment -- sh
echo ok > /usr/share/nginx/html/healthz
exit
kubectl apply -f task4-liveness-probe.yaml     # pod ...-f7f6d557f-... (the Task 4 ReplicaSet again)
kubectl describe pod -l app=nginx-task         # Restart Count: 0
```

**Result:** When `/healthz` returned 404, Kubernetes restarted the container, as required.

**What I learned:**
- Restarts did not fix the problem: the file was deleted from the PV, and a restart doesn't bring data back. A liveness probe helps when the process is stuck; when the problem is in the data or an external dependency, it only causes a CrashLoopBackOff loop.
- Going back to the same pod template reused the old ReplicaSet (same hash). Kubernetes keeps old ReplicaSets, which is what makes `kubectl rollout undo` possible.
- In a real setup `/healthz` would be served by the app itself (for Nginx: a `location /healthz` in the config, which can be loaded from a ConfigMap), not by a file on a volume.

### Task 5: Readiness probe

**File:** [task5-readiness-probe.yaml](task5-readiness-probe.yaml): the Deployment from Task 4 with a readiness probe: `tcpSocket` on port 80, `initialDelaySeconds: 30` to simulate a slow startup.

```bash
kubectl apply -f task5-readiness-probe.yaml    # configmap unchanged, deployment configured
kubectl get pods -l app=nginx-task
# new pod ...-545477cc86-qlxr8   0/1  Running  (not ready yet)
# old pod ...-f7f6d557f-v4cxd    1/1  Running  (still serving)
kubectl get pods -l app=nginx-task             # after ~30s: new pod 1/1, old pod removed, 0 restarts
kubectl describe pod -l app=nginx-task         # Readiness: tcp-socket :80 delay=30s period=10s
```

**Result:** During the 30-second delay the new pod was `Running` but `0/1`, and the old pod kept serving. Kubernetes removed the old pod only after the new one became Ready, with no restarts.

**Liveness vs. readiness:** a failed liveness probe restarts the container; a failed readiness probe only stops traffic to the pod (it is removed from the Service endpoints). Readiness is what makes a rolling update safe.

## Issues & fixes

**(Task 1) `kubectl exec -it nginx-deployment --sh` and `kubectl delete pod nginx-deployment`: "unknown flag: --sh", "pods "nginx-deployment" not found"**

`--` must be followed by a space: it separates kubectl's own flags from the command to run in the container. And `nginx-deployment` is the Deployment name, not a pod name. `exec` accepts `deployment/nginx-deployment`; `delete pod` needs the real pod name from `kubectl get pods`.

**(Task 2) `kubectl exec deployment/nginx-deployment -- sh` returned immediately**

Without `-it` there is no stdin and no terminal, so the shell exits right away. `-i` keeps stdin open, `-t` allocates a terminal. One-off commands (`printenv`, `cat`) don't need it.

**(Task 3) My new CronJob overwrote `hello-cronjob` from class**

I first used the same name, so `kubectl apply` printed `cronjob.batch/hello-cronjob configured` and replaced the class CronJob instead of creating a new one. `apply` identifies an object by kind + name + namespace. Fix: renamed mine to `date-time-cronjob`.