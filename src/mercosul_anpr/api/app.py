"""FastAPI application and local web interface."""

from __future__ import annotations

import hmac
import os
import re
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Any

import uvicorn
from fastapi import Depends, FastAPI, File, Header, HTTPException, UploadFile, status
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool

from mercosul_anpr import __version__
from mercosul_anpr.api.jobs import JobManager
from mercosul_anpr.application.service import ProcessingService
from mercosul_anpr.core.config import load_app_config
from mercosul_anpr.core.constants import PROJECT_ROOT

WEB_ROOT = Path(__file__).resolve().parent.parent / "web"
ALLOWED_VIDEO_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv", ".m4v"}


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def _safe_filename(filename: str | None) -> str:
    raw = Path(filename or "upload.bin").name
    clean = re.sub(r"[^A-Za-z0-9._-]+", "-", raw).strip(".-")
    return clean[:120] or "upload.bin"


async def _save_upload(upload: UploadFile, destination: Path, max_bytes: int) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    try:
        with destination.open("wb") as handle:
            while chunk := await upload.read(1024 * 1024):
                written += len(chunk)
                if written > max_bytes:
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=f"Arquivo excede o limite de {max_bytes // (1024 * 1024)} MB.",
                    )
                handle.write(chunk)
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    finally:
        await upload.close()


def _require_api_key(x_api_key: Annotated[str | None, Header()] = None) -> None:
    expected = os.getenv("ANPR_API_KEY", "").strip()
    if expected and (not x_api_key or not hmac.compare_digest(expected, x_api_key)):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Chave de API inválida.")


def create_app() -> FastAPI:
    """Build an isolated app instance for production and tests."""
    config = load_app_config(PROJECT_ROOT)
    jobs_root = config.runs_dir.parent / "jobs"
    service = ProcessingService(config)
    manager = JobManager(
        service,
        jobs_root,
        timeout_seconds=_env_int("ANPR_JOB_TIMEOUT_SECONDS", 1800),
        retention_hours=_env_int("ANPR_JOB_RETENTION_HOURS", 24),
    )
    max_upload_bytes = max(1, _env_int("ANPR_MAX_UPLOAD_MB", 100)) * 1024 * 1024

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        yield
        manager.shutdown()

    app = FastAPI(
        title="Mercosul ANPR API",
        summary="Reconhecimento local de placas brasileiras",
        description="API local para processar imagens e vídeos, acompanhar jobs e baixar resultados estruturados.",
        version=__version__,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )
    app.state.processing_service = service
    app.state.job_manager = manager
    app.mount("/assets", StaticFiles(directory=WEB_ROOT / "assets"), name="assets")

    @app.get("/", include_in_schema=False)
    async def web_app() -> FileResponse:
        return FileResponse(WEB_ROOT / "index.html")

    @app.get("/health", tags=["Operação"])
    async def health() -> dict[str, str]:
        return {"status": "ok", "service": "mercosul-anpr"}

    @app.get("/version", tags=["Operação"])
    async def version() -> dict[str, str]:
        return {"version": __version__}

    @app.get("/metrics", response_class=PlainTextResponse, tags=["Operação"])
    async def metrics() -> str:
        counts = manager.stats()
        lines = ["# HELP anpr_jobs Local jobs by status", "# TYPE anpr_jobs gauge"]
        lines.extend(f'anpr_jobs{{status="{key}"}} {value}' for key, value in counts.items())
        return "\n".join(lines) + "\n"

    @app.post(
        "/api/v1/process/image",
        tags=["Processamento"],
        dependencies=[Depends(_require_api_key)],
    )
    async def process_image(file: Annotated[UploadFile, File(description="Imagem da placa ou veículo")]) -> Any:
        filename = _safe_filename(file.filename)
        if Path(filename).suffix.lower() not in config.image_extensions:
            raise HTTPException(status_code=415, detail="Formato de imagem não suportado.")
        job_id = uuid.uuid4().hex[:12]
        job_root = jobs_root / job_id
        source_path = job_root / "input" / filename
        await _save_upload(file, source_path, max_upload_bytes)
        try:
            result = await run_in_threadpool(
                service.process,
                source_path,
                output_dir=job_root / "output",
                run_id=job_id,
            )
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        return JSONResponse(result.to_dict())

    @app.post(
        "/api/v1/jobs",
        status_code=status.HTTP_202_ACCEPTED,
        tags=["Jobs"],
        dependencies=[Depends(_require_api_key)],
    )
    async def create_job(
        file: Annotated[UploadFile, File(description="Imagem ou vídeo para processar")],
    ) -> dict[str, Any]:
        filename = _safe_filename(file.filename)
        extension = Path(filename).suffix.lower()
        allowed = config.image_extensions | ALLOWED_VIDEO_EXTENSIONS
        if extension not in allowed:
            raise HTTPException(status_code=415, detail="Formato não suportado.")
        job_id = uuid.uuid4().hex[:12]
        source_path = jobs_root / job_id / "input" / filename
        await _save_upload(file, source_path, max_upload_bytes)
        return manager.submit(job_id, source_path, filename).public_dict()

    @app.get("/api/v1/jobs/{job_id}", tags=["Jobs"], dependencies=[Depends(_require_api_key)])
    async def get_job(job_id: str) -> dict[str, Any]:
        record = manager.get(job_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Job não encontrado.")
        return record.public_dict()

    @app.get("/api/v1/jobs/{job_id}/result", tags=["Jobs"], dependencies=[Depends(_require_api_key)])
    async def get_result(job_id: str) -> dict[str, Any]:
        record = manager.get(job_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Job não encontrado.")
        if record.status != "completed" or record.result is None:
            raise HTTPException(status_code=409, detail="Resultado ainda não está disponível.")
        return record.result

    @app.get(
        "/api/v1/jobs/{job_id}/artifacts/{artifact}",
        tags=["Jobs"],
        dependencies=[Depends(_require_api_key)],
    )
    async def download_artifact(job_id: str, artifact: str) -> FileResponse:
        record = manager.get(job_id)
        if record is None or not record.result:
            raise HTTPException(status_code=404, detail="Resultado não encontrado.")
        filename = record.result.get("artifacts", {}).get(artifact)
        if not filename:
            raise HTTPException(status_code=404, detail="Artefato não encontrado.")
        output_root = (jobs_root / job_id / "output").resolve()
        path = (output_root / Path(filename).name).resolve()
        if path.parent != output_root or not path.is_file():
            raise HTTPException(status_code=404, detail="Arquivo não encontrado.")
        return FileResponse(path, filename=path.name)

    return app


app = create_app()


def run() -> None:
    """Start the local production server."""
    uvicorn.run(
        "mercosul_anpr.api.app:app",
        host=os.getenv("ANPR_API_HOST", "0.0.0.0"),
        port=_env_int("ANPR_API_PORT", 8000),
        workers=1,
    )


if __name__ == "__main__":
    run()
