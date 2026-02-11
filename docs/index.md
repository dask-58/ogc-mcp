# Building an OGC API – Processes Backend from Scratch

**February 11, 2026** · Dhruv Koli · GSoC 2026 · 52°North

---

If you've ever wondered how geospatial data gets *processed* on the web — not just displayed on a map, but actually transformed, buffered, aggregated — this post is for you. I'm going to walk you through how I set up a fully working backend that lets anyone submit a geospatial operation over an API and get results back, all following an open international standard.

No proprietary lock-in. No magic. Just open standards, Python, Docker, and a bit of geometry.

---

## Table of Contents

- [The Problem](#the-problem)
- [What is OGC API – Processes?](#what-is-ogc-api--processes)
- [My Approach](#my-approach)
- [Architecture & Tech Stack](#architecture--tech-stack)
- [The Buffer Process — A Proof of Concept](#the-buffer-process--a-proof-of-concept)
- [The Bug That Took Me Down a Rabbit Hole](#the-bug-that-took-me-down-a-rabbit-hole)
- [Results & Validation](#results--validation)
- [What's Next](#whats-next)

---

## The Problem

Geospatial processing has traditionally been trapped inside desktop GIS applications. You open QGIS, load a shapefile, run a buffer, export the result. It works, but it doesn't scale. It doesn't compose. And it certainly doesn't allow a web application to say: *"Hey server, take this polygon and give me a 500-meter buffer around it."*

The [OGC API – Processes](https://ogcapi.ogc.org/processes/) standard changes that. It defines a REST API for discovering, executing, and managing geospatial processes over HTTP. Think of it as a contract: any client that speaks this standard can talk to any server that implements it, regardless of what's running under the hood.

My goal was straightforward: **deploy a working OGC API – Processes backend, register a custom geospatial process, and prove the whole thing works end-to-end** — from submitting a job to getting the result back.

---

## What is OGC API – Processes?

For the non-GIS folks: imagine you have an API like any other REST service. You can ask it "what can you do?" and it responds with a list of available operations. You pick one, send it some input data (say, a point on a map and a distance), and it sends back the result (a circle around that point). That's essentially it.

The standard defines a few key endpoints:

| Endpoint | What it does |
|---|---|
| `GET /processes` | List all available processes |
| `GET /processes/{id}` | Describe a specific process (inputs, outputs) |
| `POST /processes/{id}/execution` | Run a process |
| `GET /jobs` | List submitted jobs |
| `GET /jobs/{jobId}` | Check job status |
| `GET /jobs/{jobId}/results` | Get the results |

It supports both **synchronous** execution (send request → get result immediately) and **asynchronous** execution (send request → get a job ID → poll for status → retrieve results when done). This is crucial for long-running operations like raster analysis or large-scale data aggregation.

---

## My Approach

I didn't want to build an OGC API server from scratch — that would be reinventing the wheel. Instead, I chose [pygeoapi](https://pygeoapi.io), the official OGC reference implementation for several API standards. It's written in Python, configured via YAML, and has a clean plugin architecture for adding custom processes.

The plan was simple:

1. Use the official `geopython/pygeoapi` Docker image as the base
2. Write a custom process plugin (geometry buffer using [Shapely](https://shapely.readthedocs.io/))
3. Configure everything via a single YAML file
4. Wrap it in Docker Compose for one-command deployment
5. Write a validation script that tests the entire lifecycle

Modular. No fluff. Each piece does one thing.

---

## Architecture & Tech Stack

```
┌──────────────────────────────────────────────────┐
│                  Docker Container                │
│                                                  │
│   ┌──────────┐    ┌───────────┐    ┌──────────┐  │
│   │ Gunicorn │───▶│  pygeoapi │───▶│ Shapely  │  │
│   │ (WSGI)   │    │  (Flask)  │    │ (buffer) │  │
│   └──────────┘    └─────┬─────┘    └──────────┘  │
│                         │                        │
│                   ┌─────▼─────┐                  │
│                   │  TinyDB   │                  │
│                   │ (job mgr) │                  │
│                   └───────────┘                  │
│                                                  │
│   Config: pygeoapi.config.yml                    │
│   Processes: ogc_processes/buffer_process.py     │
└──────────────────────────────────────────────────┘
         ▲
         │ HTTP :5001
         │
    ┌────┴────┐
    │  Client │  (curl, browser, GIS app)
    └─────────┘
```

*Figure 1: System architecture — a single container running pygeoapi with Gunicorn, TinyDB for job management, and a custom Shapely-based buffer process.*

### The tech involved

- **[pygeoapi](https://pygeoapi.io)** — Python server implementing OGC API standards. YAML-configured, plugin-based. The OGC reference implementation.
- **[Shapely](https://shapely.readthedocs.io/)** — Python library for geometric operations. I used it to compute buffers around input geometries.
- **[TinyDB](https://tinydb.readthedocs.io/)** — A lightweight document-oriented database. pygeoapi uses it to track async job state without needing PostgreSQL or MongoDB.
- **[Docker](https://www.docker.com/)** — The whole thing runs in a single container. `docker compose up --build` and you're done.
- **[Gunicorn](https://gunicorn.org/)** — Production-grade WSGI server that pygeoapi's Docker image uses internally.

---

## The Buffer Process — A Proof of Concept

I needed a process that's simple enough to be a clear demonstration, but meaningful enough to actually do something geospatial. A **geometry buffer** fit perfectly: you give it a shape (a point, a line, a polygon) and a distance, and it returns a new polygon that represents the area within that distance of the original shape.

Think of it like drawing a circle around a point on a map, or expanding a boundary outward by a certain amount. This is one of the most fundamental operations in GIS — used for proximity analysis, impact zones, setback calculations, you name it.

Writing the process plugin meant implementing pygeoapi's `BaseProcessor` class. The key parts:

```python
# The process metadata — tells the API what inputs/outputs to expect
PROCESS_METADATA = {
    'id': 'geometry-buffer',
    'title': 'Geometry Buffer',
    'inputs': {
        'geometry': { ... },   # GeoJSON geometry
        'distance': { ... },   # Buffer distance
        'resolution': { ... }, # Optional: smoothness
    },
    'outputs': {
        'buffered_geometry': { ... }
    },
    'jobControlOptions': ['sync-execute', 'async-execute'],
}

class GeometryBufferProcessor(BaseProcessor):
    def execute(self, data, outputs=None):
        geom = shape(data['geometry'])            # Parse GeoJSON
        buffered = geom.buffer(data['distance'])  # Compute buffer
        return 'application/json', {
            'type': 'Feature',
            'geometry': mapping(buffered),         # Back to GeoJSON
            'properties': { ... }
        }
```

*Figure 2: Simplified version of the buffer process plugin. The full implementation includes input validation, configurable resolution, and error handling.*

Then it's just a matter of registering it in the YAML config:

```yaml
resources:
  geometry-buffer:
    type: process
    processor:
      name: ogc_processes.buffer_process.GeometryBufferProcessor
```

That's it. pygeoapi picks it up, generates the OpenAPI spec, and exposes it at `/processes/geometry-buffer`.

---

## The Bug That Took Me Down a Rabbit Hole

Here's where it got interesting. I had everything wired up — Dockerfile, config, custom process, validation script. I ran `docker compose up --build`, waited, ran my tests, and… every single test failed. The server wasn't responding at all.

`docker ps` showed the container in a **restart loop**:

```
CONTAINER ID   IMAGE              STATUS
0713fd49497f   ogc-mcp-pygeoapi   Restarting (255) 4 seconds ago
```

Exit code 255. Not helpful. I pulled the container logs and found the culprit:

```
ModuleNotFoundError: No module named 'ogc_processes'
```

The issue was subtle. My Dockerfile copies the process files into `/pygeoapi/ogc_processes/`, and pygeoapi's entrypoint tries to generate the OpenAPI document at startup — which means it needs to *import* every registered process plugin. But `/pygeoapi/` isn't on Python's module search path inside the container.

The fix was one line in the Dockerfile:

```dockerfile
ENV PYTHONPATH="/pygeoapi"
```

That's it. One environment variable. The container started, the OpenAPI doc generated successfully, and all 17 tests passed on the next run. Sometimes the hardest bugs have the simplest fixes.

> **Lesson learned:** When extending a Docker image with custom Python modules, always check whether the working directory is on `PYTHONPATH`. Don't assume it — especially when the base image uses a virtualenv (`/venv/bin/python`) that has its own site-packages path.

---

## Results & Validation

I wrote a bash validation script that tests the entire OGC API – Processes lifecycle. Here's what it checks:

1. Landing page returns valid metadata
2. Conformance endpoint lists OGC conformance classes
3. Process listing includes both `hello-world` and `geometry-buffer`
4. Process description returns inputs, outputs, and metadata
5. Synchronous execution of `hello-world` (smoke test)
6. Synchronous execution of `geometry-buffer` with a Point
7. Synchronous execution of `geometry-buffer` with a LineString
8. Asynchronous execution: job creation → status polling → result retrieval
9. Jobs endpoint returns the job list

```
$ ./validate.sh
== 1. Landing Page ==
  ✓ Landing page returns title
== 2. Conformance ==
  ✓ Conformance lists conformsTo
== 3. List Processes ==
  ✓ Processes list contains hello-world
  ✓ Processes list contains geometry-buffer
== 4. Describe Process: geometry-buffer ==
  ✓ Process description has id
  ✓ Process description has inputs
  ✓ Process description has outputs
== 5. Sync Execute: hello-world ==
  ✓ Hello-world echoes name
== 6. Sync Execute: geometry-buffer (Point) ==
  ✓ Buffer returns Feature
  ✓ Buffer returns Polygon
  ✓ Buffer returns area
== 7. Sync Execute: geometry-buffer (LineString) ==
  ✓ LineString buffer returns Feature
  ✓ LineString buffer returns Polygon
== 8. Async Execute: geometry-buffer ==
  ✓ Async job created
  ✓ Job completed successfully
  ✓ Async results contain geometry
== 9. Jobs Endpoint ==
  ✓ Jobs endpoint returns list

=========================================
  Results: 17 passed, 0 failed
=========================================
```

*Figure 3: Full validation output — all 17 checks pass, covering discovery, sync execution, async lifecycle, and job management.*

The async test is particularly satisfying. The client sends a request with `Prefer: respond-async`, gets back a `201 Created` with a `Location` header pointing to the job URL, polls until the status is `"successful"`, then fetches the buffered polygon from `/jobs/{id}/results`. That's the full OGC API – Processes lifecycle, working exactly as the standard describes.

---

## What's Next

This is a solid foundation, but there's more to build. Here's what I'm planning for the coming weeks:

- **More processes** — zonal statistics, spatial intersection, coordinate transformation. The plugin architecture makes this straightforward.
- **Input validation** — proper JSON Schema validation for process inputs, better error messages.
- **Authentication** — API key or OAuth2 middleware for production deployments.
- **PostgreSQL job manager** — replace TinyDB with PostgreSQL for multi-instance scaling.
- **CI/CD pipeline** — automated testing on every push, with the validation script running against a fresh container.
- **MCP integration** — connecting this backend to a Model Context Protocol server for AI-driven geospatial workflows.

The whole project is open source and designed to be picked up by anyone. Clone the repo, run `docker compose up --build`, and you have a working OGC API – Processes server in under a minute. Add a new process by dropping a Python file in `processes/` and adding three lines to the YAML config.

> The best infrastructure is the kind you don't have to think about. You describe what you want to compute, the standard handles the rest.

If you're interested in geospatial APIs, open standards, or just want to see how a simple Docker setup can implement a full OGC specification, check out the [pygeoapi project](https://github.com/geopython/pygeoapi) — it's one of the best examples of what open-source geospatial software can be.

Thanks for reading. More updates coming soon as the project evolves.

---

**Tags:** `OGC API` · `Processes` · `pygeoapi` · `Docker` · `Geospatial` · `Shapely` · `GSoC 2026` · `52°North` · `Open Standards` · `REST API` · `Python` · `GIS`
