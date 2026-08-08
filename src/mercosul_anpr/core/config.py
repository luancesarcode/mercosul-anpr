"""Configuration management for the ANPR application."""

from __future__ import annotations

import os
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover - fallback for environments sem python-dotenv
    def load_dotenv(*_args, **_kwargs):  # type: ignore[override]
        return False

from mercosul_anpr.core import constants


@dataclass(frozen=True)
class DetectionConfig:
    """Model inference thresholds and image sizing."""

    img_size: int
    vehicle_conf: float
    vehicle_iou: float
    vehicle_min_area_ratio: float
    plate_conf: float
    plate_recall_conf: float
    plate_iou: float
    max_plates: int


@dataclass(frozen=True)
class TrackingConfig:
    """Tracking and temporal-voting controls."""

    track_iou: float
    track_min_hits: int
    track_max_age: int
    plate_vote_window: int
    plate_switch_dominance_frames: int
    debugger_window_frames: int
    plate_min_occurrences: int
    plate_min_score: float
    ocr_interval_frames: int


@dataclass(frozen=True)
class AssociationConfig:
    """Plate-to-vehicle association and ROI reuse settings."""

    use_roi_detection: bool
    use_hybrid_association: bool
    association_threshold: float
    association_weights: tuple[float, float, float]
    roi_cache_ttl: int


@dataclass(frozen=True)
class DisplayConfig:
    """Visual filtering and smoothing controls for overlay."""

    plate_text_conf_min: float
    plate_text_conf_max: float
    plate_bbox_smooth_enabled: bool
    plate_bbox_smooth_alpha: float


@dataclass(frozen=True)
class LoggingConfig:
    """Logger output and rotation settings."""

    log_dir: Path
    file_name: str
    max_bytes: int
    backup_count: int


@dataclass(frozen=True)
class ProfilingConfig:
    """Runtime profiling toggles."""

    enable_cprofile: bool
    enable_line_profiler: bool


@dataclass(frozen=True)
class AppConfig:
    """Top-level immutable configuration object."""

    project_root: Path
    source_path: Path
    coco_model_path: Path
    plate_model_path: Path
    runs_dir: Path
    image_extensions: set[str]
    vehicle_classes: list[int]
    detection: DetectionConfig
    tracking: TrackingConfig
    association: AssociationConfig
    display: DisplayConfig
    logging: LoggingConfig
    profiling: ProfilingConfig

    @property
    def source_is_image(self) -> bool:
        """Return True when configured source extension is an image format."""
        return self.source_path.suffix.lower() in self.image_extensions


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _env_float_clamped(name: str, default: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, _env_float(name, default)))


def _env_list_int(name: str, default: Iterable[int]) -> list[int]:
    raw = os.getenv(name)
    if raw is None:
        return list(default)
    values: list[int] = []
    for item in raw.split(","):
        item = item.strip()
        if not item:
            continue
        try:
            values.append(int(item))
        except ValueError:
            continue
    return values or list(default)


def _resolve_path(project_root: Path, value: str | Path | None, fallback: Path) -> Path:
    candidate = Path(value) if value is not None else fallback
    if candidate.is_absolute():
        return candidate
    return (project_root / candidate).resolve()


def _build_detection_config() -> DetectionConfig:
    plate_conf = _env_float_clamped("ANPR_PLATE_CONF", constants.DEFAULT_PLATE_CONF, 0.001, 1.0)
    return DetectionConfig(
        img_size=max(128, _env_int("ANPR_IMG_SIZE", constants.DEFAULT_IMG_SIZE)),
        vehicle_conf=_env_float_clamped("ANPR_VEHICLE_CONF", constants.DEFAULT_VEHICLE_CONF, 0.01, 1.0),
        vehicle_iou=_env_float_clamped("ANPR_VEHICLE_IOU", constants.DEFAULT_VEHICLE_IOU, 0.05, 1.0),
        vehicle_min_area_ratio=_env_float_clamped(
            "ANPR_VEHICLE_MIN_AREA_RATIO",
            constants.DEFAULT_VEHICLE_MIN_AREA_RATIO,
            0.0,
            1.0,
        ),
        plate_conf=plate_conf,
        plate_recall_conf=min(
            plate_conf,
            _env_float_clamped(
                "ANPR_PLATE_RECALL_CONF",
                constants.DEFAULT_PLATE_RECALL_CONF,
                0.001,
                1.0,
            ),
        ),
        plate_iou=_env_float_clamped("ANPR_PLATE_IOU", constants.DEFAULT_PLATE_IOU, 0.05, 1.0),
        max_plates=max(1, _env_int("ANPR_MAX_PLATES", constants.DEFAULT_MAX_PLATES)),
    )


def _build_tracking_config() -> TrackingConfig:
    return TrackingConfig(
        track_iou=_env_float_clamped("ANPR_TRACK_IOU", constants.DEFAULT_TRACK_IOU, 0.05, 1.0),
        track_min_hits=max(1, _env_int("ANPR_TRACK_MIN_HITS", constants.DEFAULT_TRACK_MIN_HITS)),
        track_max_age=max(1, _env_int("ANPR_TRACK_MAX_AGE", constants.DEFAULT_TRACK_MAX_AGE)),
        plate_vote_window=max(
            1,
            _env_int("ANPR_PLATE_VOTE_WINDOW", constants.DEFAULT_PLATE_VOTE_WINDOW),
        ),
        plate_switch_dominance_frames=max(
            1,
            _env_int(
                "ANPR_PLATE_SWITCH_DOMINANCE_FRAMES",
                constants.DEFAULT_PLATE_SWITCH_DOMINANCE_FRAMES,
            ),
        ),
        debugger_window_frames=max(
            1,
            _env_int("ANPR_DEBUGGER_WINDOW_FRAMES", constants.DEFAULT_DEBUGGER_WINDOW_FRAMES),
        ),
        plate_min_occurrences=max(
            1,
            _env_int("ANPR_PLATE_MIN_OCCURRENCES", constants.DEFAULT_PLATE_MIN_OCCURRENCES),
        ),
        plate_min_score=_env_float_clamped("ANPR_PLATE_MIN_SCORE", constants.DEFAULT_PLATE_MIN_SCORE, 0.0, 100.0),
        ocr_interval_frames=max(
            1,
            _env_int("ANPR_OCR_INTERVAL_FRAMES", constants.DEFAULT_OCR_INTERVAL_FRAMES),
        ),
    )


def _build_association_config() -> AssociationConfig:
    raw_weights = (
        max(0.0, _env_float("ANPR_ASSOC_WEIGHT_IOU", constants.DEFAULT_ASSOCIATION_WEIGHTS[0])),
        max(0.0, _env_float("ANPR_ASSOC_WEIGHT_CENTER", constants.DEFAULT_ASSOCIATION_WEIGHTS[1])),
        max(0.0, _env_float("ANPR_ASSOC_WEIGHT_SIZE", constants.DEFAULT_ASSOCIATION_WEIGHTS[2])),
    )
    weight_total = sum(raw_weights) or 1.0
    return AssociationConfig(
        use_roi_detection=_env_bool("ANPR_USE_ROI_DETECTION", True),
        use_hybrid_association=_env_bool("ANPR_USE_HYBRID_ASSOCIATION", True),
        association_threshold=_env_float_clamped(
            "ANPR_ASSOCIATION_THRESHOLD",
            constants.DEFAULT_ASSOCIATION_THRESHOLD,
            0.0,
            1.0,
        ),
        association_weights=tuple(weight / weight_total for weight in raw_weights),
        roi_cache_ttl=max(0, _env_int("ANPR_ROI_CACHE_TTL", constants.DEFAULT_ROI_CACHE_TTL)),
    )


def _build_display_config() -> DisplayConfig:
    conf_min = _env_float_clamped("ANPR_PLATE_TEXT_CONF_MIN", constants.DEFAULT_PLATE_TEXT_CONF_MIN, 0.0, 100.0)
    conf_max = _env_float_clamped("ANPR_PLATE_TEXT_CONF_MAX", constants.DEFAULT_PLATE_TEXT_CONF_MAX, 0.0, 100.0)
    if conf_max < conf_min:
        conf_min, conf_max = conf_max, conf_min
    alpha = _env_float("ANPR_PLATE_BBOX_SMOOTH_ALPHA", constants.DEFAULT_PLATE_BBOX_SMOOTH_ALPHA)
    alpha = max(0.05, min(1.0, alpha))
    return DisplayConfig(
        plate_text_conf_min=conf_min,
        plate_text_conf_max=conf_max,
        plate_bbox_smooth_enabled=_env_bool(
            "ANPR_PLATE_BBOX_SMOOTH_ENABLED",
            constants.DEFAULT_PLATE_BBOX_SMOOTH_ENABLED,
        ),
        plate_bbox_smooth_alpha=alpha,
    )


def _build_logging_config(project_root: Path) -> LoggingConfig:
    log_dir = _resolve_path(
        project_root,
        os.getenv("ANPR_LOG_DIR"),
        constants.DEFAULT_LOG_DIR,
    )
    return LoggingConfig(
        log_dir=log_dir,
        file_name=os.getenv("ANPR_LOG_FILE", "anpr.log"),
        max_bytes=max(1024, _env_int("ANPR_LOG_MAX_BYTES", 5_000_000)),
        backup_count=max(1, _env_int("ANPR_LOG_BACKUP_COUNT", 5)),
    )


def _build_profiling_config() -> ProfilingConfig:
    return ProfilingConfig(
        enable_cprofile=_env_bool("ANPR_ENABLE_CPROFILE", False),
        enable_line_profiler=_env_bool("ANPR_ENABLE_LINE_PROFILER", False),
    )


def load_app_config(
    project_root: Path,
    overrides: dict[str, str | Path | None] | None = None,
) -> AppConfig:
    """Build and return immutable application configuration.

    Args:
        project_root: Absolute project root directory.
        overrides: Optional explicit value overrides from entrypoint.

    Returns:
        Fully populated configuration object.
    """
    load_dotenv(project_root / ".env", override=False)
    ov = overrides or {}

    default_source = constants.DEFAULT_SOURCE_VIDEO
    source_override = ov.get("source_path") or os.getenv("ANPR_SOURCE") or default_source

    config = AppConfig(
        project_root=project_root.resolve(),
        source_path=_resolve_path(project_root, source_override, default_source),
        coco_model_path=_resolve_path(
            project_root,
            ov.get("coco_model_path") or os.getenv("ANPR_COCO_MODEL"),
            constants.DEFAULT_COCO_MODEL,
        ),
        plate_model_path=_resolve_path(
            project_root,
            ov.get("plate_model_path") or os.getenv("ANPR_PLATE_MODEL"),
            constants.DEFAULT_PLATE_MODEL,
        ),
        runs_dir=_resolve_path(
            project_root,
            ov.get("runs_dir") or os.getenv("ANPR_RUNS_DIR"),
            constants.DEFAULT_RUNS_DIR,
        ),
        image_extensions=set(constants.IMAGE_EXTENSIONS),
        vehicle_classes=_env_list_int("ANPR_VEHICLE_CLASSES", constants.VEHICLE_CLASSES),
        detection=_build_detection_config(),
        tracking=_build_tracking_config(),
        association=_build_association_config(),
        display=_build_display_config(),
        logging=_build_logging_config(project_root),
        profiling=_build_profiling_config(),
    )
    return config
