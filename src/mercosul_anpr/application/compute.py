"""Compute-device discovery and selection for local inference."""

from __future__ import annotations

import shutil
from typing import Any

VALID_COMPUTE_PREFERENCES = {"auto", "cpu", "nvidia"}


def normalize_compute_preference(value: str | None, *, strict: bool = False) -> str:
    """Normalize user and environment aliases to one stable preference."""
    normalized = (value or "auto").strip().lower()
    normalized = {"cuda": "nvidia", "gpu": "nvidia"}.get(normalized, normalized)
    if normalized in VALID_COMPUTE_PREFERENCES:
        return normalized
    if strict:
        raise ValueError("Dispositivo inválido. Use automático, CPU ou NVIDIA.")
    return "auto"


def inspect_compute_capabilities() -> dict[str, Any]:
    """Test whether the installed PyTorch can execute inference on NVIDIA CUDA."""
    driver_command_found = shutil.which("nvidia-smi") is not None
    torch_version: str | None = None
    cuda_version: str | None = None
    cuda_available = False
    devices: list[str] = []
    inspection_error: str | None = None

    try:
        import torch

        torch_version = str(getattr(torch, "__version__", "desconhecida"))
        cuda_version = getattr(getattr(torch, "version", None), "cuda", None)
        cuda_available = bool(torch.cuda.is_available())
        if cuda_available:
            for index in range(int(torch.cuda.device_count())):
                try:
                    devices.append(str(torch.cuda.get_device_name(index)))
                except Exception:
                    devices.append(f"GPU NVIDIA {index + 1}")
    except Exception as exc:
        inspection_error = f"Não foi possível testar o PyTorch: {exc}"

    available = cuda_available and bool(devices)
    if available:
        joined_devices = ", ".join(devices)
        reason = f"CUDA disponível em {len(devices)} dispositivo(s): {joined_devices}."
    elif inspection_error:
        reason = inspection_error
    elif cuda_version:
        reason = (
            f"O PyTorch tem suporte CUDA {cuda_version}, mas não conseguiu acessar uma GPU NVIDIA. "
            "Verifique a placa e o driver."
        )
    elif driver_command_found:
        reason = "O driver NVIDIA foi localizado, mas o PyTorch instalado não possui suporte CUDA."
    else:
        reason = "O PyTorch instalado é somente CPU e nenhum driver NVIDIA foi localizado no sistema."

    return {
        "available": available,
        "driver_command_found": driver_command_found,
        "torch_version": torch_version,
        "cuda_version": cuda_version,
        "cuda_available": cuda_available,
        "device_count": len(devices),
        "devices": devices,
        "reason": reason,
    }


def resolve_compute_device(preference: str, capabilities: dict[str, Any]) -> str | int:
    """Resolve a stable preference to the value accepted by Ultralytics."""
    normalized = normalize_compute_preference(preference, strict=True)
    nvidia_available = bool(capabilities.get("available"))
    if normalized == "nvidia":
        if not nvidia_available:
            raise ValueError(str(capabilities.get("reason") or "NVIDIA não está disponível."))
        return 0
    if normalized == "auto" and nvidia_available:
        return 0
    return "cpu"


def device_label(device: str | int) -> str:
    """Return a human-readable name for an Ultralytics device value."""
    return "NVIDIA (CUDA)" if device != "cpu" else "CPU"
