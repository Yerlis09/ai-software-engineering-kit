# fastapi-demo conventions (project-specific)

- Routes live in `api/routes.py`; they only validate, call one service method and map the
  result. Business rules belong to `domain/`, orchestration to `application/`.
- Domain errors inherit from `DomainError` and are translated to RFC 9457 problem details in
  one place (`domain_error_handler`).
- Inject ids/clock into services (`new_id=`) so unit tests are deterministic.
- Exception to the kit's NGINX + uWSGI default: FastAPI runs on uvicorn (ADR 0002).
