# Docker – Week 2

Docker homework from the DevOps Experts course: building images, running containers, Docker Compose, multi-stage builds and volumes.

## Environment
- WSL 2 (Ubuntu 24.04) with Docker Engine

- Docker Hub login with a Personal Access Token (not a password):
```bash
docker login -u yelenazamansky
```
## Assignment 1: Building Docker Images
**Task:** Build an image from `python:3.9-slim` with Flask installed, running a script that prints the user name (Computer account), and push it to Docker Hub.

**Files:** [Dockerfile](assignment1/Dockerfile), [getUser.py](assignment1/getUser.py)

```bash
cd assignment1
python3 getUser.py   # yelena (on the host)
docker build --network host -t python-flask-app:latest .
docker run --rm python-flask-app:latest # root (inside the container)
docker tag python-flask-app:latest yelenazamansky/python-flask-app:latest
docker push yelenazamansky/python-flask-app:latest
```
**Result:** On the host the script prints `yelena`; inside the container it prints `root`.
The container has its own users, isolated from the host.

**Docker Hub:** https://hub.docker.com/r/yelenazamansky/python-flask-app

## Assignment 2: Running Containers
**Task:** Run a container from the Assignment 1 image on host port 5000, verify it with `docker ps`, then stop and remove it.

```bash
docker run --name flask-app -p 5000:5000 python-flask-app:latest   # root, then exits
docker ps -a --filter name=flask-app                               # Exited (0)
docker logs flask-app
docker rm flask-app

# override CMD with a long-running server to get a running container on port 5000
docker run -d --name flask-app -p 5000:5000 python-flask-app:latest python -m http.server 5000
docker ps                  # Up, 0.0.0.0:5000->5000/tcp
docker stop flask-app
docker start flask-app
docker rm -vf flask-app
docker ps
```

## Assignment 3: Docker Compose
**Task:** A Flask app connected to Redis, exposed on port 5000, started with Docker Compose.

**Files:** [Dockerfile](assignment3/Dockerfile), [app.py](assignment3/app.py), [docker-compose.yml](assignment3/docker-compose.yml)

```bash
cd assignment3
docker compose up -d --build
docker compose ps
curl localhost:5000  # Hello from Flask! This page has been visited 1 times.
docker compose down
```
**Result:** The visit counter is stored in Redis, so it keeps increasing across requests (from `curl` and from the browser). Flask reaches Redis by its service name 
(`REDIS_HOST=redis`) through Docker's internal DNS. Redis port 6379 is not published to the host; only the `web` service can reach it.

## Assignment 4: Multi-Stage Builds
**Task:** Create a multi-stage Dockerfile for a Python application with a Flask web server: one stage installs dependencies, the second is a minimal runtime.

**Files:** [Dockerfile](assignment4/Dockerfile), [Dockerfile.heavy](assignment4/Dockerfile.heavy),
[app.py](assignment4/app.py)

- **Stage 1** (`python:3.9`, builder): installs Flask into a virtual environment (`/venv`).
- **Stage 2** (`python:3.9-slim`): copies only `/venv` and `app.py`.

```bash
cd assignment4
docker build --network host -t flask-multistage .
docker run -d --name flask-ms -p 5000:5000 flask-multistage
curl localhost:5000
docker build --network host -f Dockerfile.heavy -t flask-heavy .
docker images flask-heavy
docker images flask-multistage
curl localhost:5000
```
| Image | Dockerfile | Size |
|---|---|---|
| `flask-heavy` | single stage, `python:3.9` | 1.6 GB |
| `flask-multistage` | multi-stage, runtime on `python:3.9-slim` | 219 MB |

**Result:** About 7x smaller. Flask has no compiled dependencies, so the gain over a single-stage `slim` image is small; multi-stage helps most when packages need compilers, which stay in the builder stage.

## Assignment 5: Volumes and Data Persistence
**Task:** Run a Flask app container that writes logs to a directory mounted to the volume named flask_data; the logs must survive removing and re-creating the container.

**Files:** [Dockerfile](assignment5/Dockerfile), [app.py](assignment5/app.py)

```bash
cd assignment5
docker volume create flask_data
docker build --network host -t flask-logs-app .
docker run -d --name flask-logs -p 5000:5000 -v flask_data:/data flask-logs-app
curl localhost:5000
curl localhost:5000
docker exec flask-logs cat /data/app.log  # 4 log lines
docker rm -f flask-logs
docker run -d --name flask-logs -p 5000:5000 -v flask_data:/data flask-logs-app
docker exec flask-logs cat /data/app.log  # the same 4 lines are still there
```
**Result:** The log file lives in the named volume, not in the container, so it survives removing and re-creating the container.

## Issues & fixes

**`pip install` failed during `docker build`: "Temporary failure in name resolution"**
The build container got the WSL DNS server (`10.255.255.254`), which is not reachable from Docker's bridge network. Fix: build with `--network host`
(in Compose: `build.network: host`).

**`docker ps` was empty in Assignment 2**
The container's main process (`getUser.py`) finished, so the container exited with code 0.
Fix: overrode the `CMD` with a long-running process (`python -m http.server 5000`).

**`flask-heavy` had the same size as the multi-stage image**
I forgot `-f Dockerfile.heavy`, so Docker built the default `Dockerfile`. The build log
(`load build definition from ...`) showed which file was used.

**"name is already in use" / "port is already allocated"**
Leftover containers from earlier practice. Checked with `docker ps -a`, then removed them or used another host port.


