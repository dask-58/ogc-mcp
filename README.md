# OGC API – Processes Backend

> [!NOTE]
> Read the full blog post here: [Building an OGC API](https://dask-58.github.io/ogc-mcp/)

A backend implementing the **OGC API – Processes** standard, powered by [pygeoapi](https://pygeoapi.io).

---

## Sitemap

```zsh
ogc-mcp/
├── Dockerfile              # Extends geopython/pygeoapi:latest
├── docker-compose.yml      # One-command deployment
├── pygeoapi.config.yml     # pygeoapi YAML configuration
├── processes/              # Custom process plugins
│   ├── __init__.py
│   └── buffer_process.py   # Geometry Buffer processor
├── validate.sh             # End-to-end validation script
└── .env                    # Environment variables
```

## OGC API – Processes Endpoints

| Endpoint                              | Method | Description                     |
|---------------------------------------|--------|---------------------------------|
| `/`                                   | GET    | Landing page                    |
| `/conformance`                        | GET    | Conformance classes             |
| `/processes`                          | GET    | List available processes        |
| `/processes/{id}`                     | GET    | Describe a specific process     |
| `/processes/{id}/execution`           | POST   | Execute a process (sync/async)  |
| `/jobs`                               | GET    | List all jobs                   |
| `/jobs/{jobId}`                       | GET    | Get job status                  |
| `/jobs/{jobId}/results`               | GET    | Retrieve job results            |
| `/jobs/{jobId}`                       | DELETE | Cancel/delete a job             |
| `/openapi`                            | GET    | OpenAPI 3.0 document            |

---

## Quick Start

### Prerequisites
- Docker & Docker Compose

### 1. Build & Run

```zsh
docker compose up --build
```

The service starts at **http://localhost:5001**.

### 2. Validate

```zsh
zsh ./validate.sh
```

This runs through the full OGC API – Processes lifecycle:
- Landing page, conformance, process listing
- Sync execution of `hello-world` and `geometry-buffer`
- Async execution + job polling + result retrieval
- Jobs endpoint

### 3. Stop

```zsh
docker compose down
```

---

## Registered Processes

### hello-world (built-in)

Echoes back a name and optional message.

```zsh
curl -X POST http://localhost:5001/processes/hello-world/execution \
  -H "Content-Type: application/json" \
  -d '{"inputs":{"name":"World","message":"Hello!"}}'
```

### geometry-buffer (custom)

Computes a buffer around any GeoJSON geometry using [Shapely](https://shapely.readthedocs.io/).

**Inputs:**

| Parameter    | Type    | Required | Description                              |
|-------------|---------|----------|------------------------------------------|
| `geometry`  | object  | yes      | GeoJSON geometry (Point, Line, Polygon…) |
| `distance`  | number  | yes      | Buffer distance (CRS units)              |
| `resolution`| integer | no       | Quarter-circle segments (default: 16)    |

**Example — buffer a Point:**

```zsh
curl -X POST http://localhost:5001/processes/geometry-buffer/execution \
  -H "Content-Type: application/json" \
  -d '{
    "inputs": {
      "geometry": {"type":"Point","coordinates":[0.0,0.0]},
      "distance": 1.0,
      "resolution": 16
    }
  }'
```

**Example — buffer a Polygon (async):**

```zsh
curl -i -X POST http://localhost:5001/processes/geometry-buffer/execution \
  -H "Content-Type: application/json" \
  -H "Prefer: respond-async" \
  -d '{
    "inputs": {
      "geometry": {"type":"Polygon","coordinates":[[[0,0],[1,0],[1,1],[0,1],[0,0]]]},
      "distance": 0.25
    }
  }'
# Returns Location header → poll GET /jobs/{jobId} → GET /jobs/{jobId}/results
```

---

## Configuration

All configuration lives in [`pygeoapi.config.yml`](pygeoapi.config.yml). Key sections:

| Section              | Purpose                                    |
|---------------------|--------------------------------------------|
| `server.bind`       | Host/port binding                          |
| `server.url`        | Public base URL (env-overridable)          |
| `server.manager`    | Job manager                                |
| `server.cors`       | CORS enabled by default                    |
| `metadata`          | Service identification & contact           |
| `resources`         | Process registration (type: process)       |

### Adding a New Process

1. Create `processes/my_process.py` implementing `BaseProcessor`
2. Add to `pygeoapi.config.yml` under `resources`:

```yaml
resources:
  my-process:
    type: process
    processor:
      name: ogc_processes.my_process.MyProcessor
```

3. Rebuild: `docker compose up --build`
