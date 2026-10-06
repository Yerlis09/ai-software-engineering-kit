# Stack — NGINX + uWSGI

> Kit file — managed by `ai-project update`. Generic rules live in `rules/`; this file only adds NGINX + uWSGI-specific guidance.

Team web-serving standard: **NGINX as reverse proxy** in front of **uWSGI** for Python **WSGI** apps (Django, Flask). **FastAPI is ASGI: uWSGI is not suitable** — run it with `uvicorn` (or `gunicorn -k uvicorn.workers.UvicornWorker`) and use `proxy_pass` instead of `uwsgi_pass`. NGINX also serves static frontends (React/Angular builds).

## Recommended tooling

- `nginx -t` (syntax check) in CI and before reloads; `gixy` for config security linting.
- uWSGI with the Python plugin (pip-installed `uwsgi` in the app image).
- TLS: certificates from the internal PKI or cert-manager; test with `testssl.sh`.
- In Kubernetes, TLS usually terminates at the RKE ingress controller (ingress-nginx); an in-pod NGINX is then optional (static files, `uwsgi_pass`).

## Project structure

```
docker/
  uwsgi.ini          # app server config (in the app image)
  nginx.conf         # reverse proxy config (separate NGINX image/container)
static/              # collected static assets served by NGINX
```

NGINX and uWSGI run as separate containers (sidecar in the same pod, or separate Deployments) — one process per container.

## Conventions

- uWSGI: `master`, explicit `processes`/`threads`, `harakiri` (request timeout), `max-requests` (recycle workers), `vacuum`, `die-on-term`, `need-app`, `lazy-apps` when the app opens connections at import.
- Never run uWSGI as root: the container `USER` is non-root (uid 10001); do not use `uid`/`gid` switching from root.
- Communicate via the `uwsgi` protocol over TCP (`socket = :8000`) between containers, or a Unix socket on a shared `emptyDir` in the same pod.
- Keep NGINX timeouts slightly above `harakiri` so uWSGI kills slow requests first and errors are attributed correctly.
- Health endpoints (`/healthz`, `/readyz`) bypass auth and are excluded from access logs if noisy.

## Security

- Security headers: `Strict-Transport-Security`, `X-Content-Type-Options nosniff`, `X-Frame-Options DENY` (or CSP `frame-ancestors`), `Referrer-Policy`, `Content-Security-Policy`.
- `server_tokens off;`; limit methods where possible; `client_max_body_size` set explicitly.
- TLS: TLS 1.2+ only (prefer 1.3), modern ciphers, HSTS once HTTPS is stable; redirect HTTP → HTTPS. When terminated upstream (ingress), trust `X-Forwarded-*` only from the ingress CIDR.
- Rate-limit auth and expensive endpoints (`limit_req_zone`).
- Deny access to hidden files (`location ~ /\. { deny all; }`).
- Never expose the uWSGI socket or stats server outside the pod/namespace.

## Performance

- Tune `processes` ≈ CPU cores allotted to the pod (start with 2–4) and `threads` for I/O-bound apps; scale out with replicas.
- `gzip on` for text types (or brotli if available); long-lived cache headers for hashed static assets, `no-cache` for `index.html`.
- `uwsgi_buffering on` with adequate buffers; `keepalive` to upstreams for `proxy_pass`.
- `listen` backlog and uWSGI `listen` queue sized together to avoid dropped connections under bursts.

## Testing

- `nginx -t -c docker/nginx.conf` and `gixy` in CI; `uwsgi --ini uwsgi.ini --need-app` fails fast if the app cannot load.
- Smoke test after deploy: headers present (`curl -I`), large upload rejected, timeout behavior.

## Pitfalls

- Using uWSGI for FastAPI/ASGI apps.
- `harakiri` larger than NGINX `uwsgi_read_timeout` (NGINX returns 504 while workers keep running).
- No `max-requests` → slow memory growth over days.
- Missing `die-on-term` → uWSGI reloads instead of exiting on `SIGTERM` (slow pod shutdowns).
- Forgetting `add_header ... always` (headers missing on error responses); `add_header` in a `location` overrides server-level headers.

## Example

```ini
; docker/uwsgi.ini
; uWSGI ini does not support inline comments: keep comments on their own lines.
[uwsgi]
; Django: module = config.wsgi:application
module = app.wsgi:app
master = true
processes = 4
threads = 2
socket = :8000
harakiri = 30
max-requests = 5000
max-requests-delta = 500
vacuum = true
die-on-term = true
need-app = true
lazy-apps = true
strict = true
buffer-size = 32768
```

```nginx
upstream app_upstream { server 127.0.0.1:8000; }

server {
    listen 8080;                       # non-root port; TLS terminated at ingress
    server_tokens off;
    client_max_body_size 10m;
    gzip on;
    gzip_types text/css application/javascript application/json image/svg+xml;

    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-Frame-Options "DENY" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    add_header Content-Security-Policy "default-src 'self'" always;

    location /static/ { alias /app/static/; expires 30d; access_log off; }
    location ~ /\. { deny all; }

    location / {
        include uwsgi_params;
        uwsgi_pass app_upstream;
        uwsgi_connect_timeout 5s;
        uwsgi_read_timeout 35s;        # > harakiri (30s)
        uwsgi_send_timeout 35s;
    }
}
```

For FastAPI replace the `location /` block with `proxy_pass http://app_upstream;` plus `proxy_set_header Host $host; proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for; proxy_set_header X-Forwarded-Proto $scheme; proxy_read_timeout 35s;`.
