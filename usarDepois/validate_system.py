#!/usr/bin/env python3
"""System validation utility for production ANPR checks."""

from __future__ import annotations

import argparse
import statistics
from pathlib import Path

import psutil

from core.config import load_app_config
from io_layer.video_reader import InputSourceReader
from pipeline.processor import PipelineProcessor
from pipeline.temporal_voter import TemporalVoter
from pipeline.tracker import IoUTracker
from vision.ocr_engine import OCREngine
from vision.plate_detector import PlateDetector
from vision.vehicle_detector import VehicleDetector, escolher_dispositivo


def _build_processor(config, device):
    vehicle_detector = VehicleDetector(config.coco_model_path, config.detection, config.vehicle_classes)
    plate_detector = PlateDetector(config.plate_model_path, config.detection, roi_cache_ttl=config.association.roi_cache_ttl)
    ocr = OCREngine()
    ocr.warmup()
    tracker = IoUTracker(config.tracking)
    voter = TemporalVoter(config.tracking)
    return PipelineProcessor(config, device, vehicle_detector, plate_detector, ocr, tracker, voter)


def _arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate ANPR runtime quality and resilience.")
    parser.add_argument("--source", type=str, default=None, help="Input source path (video/image).")
    parser.add_argument("--max-frames", type=int, default=150, help="Max frames to evaluate.")
    parser.add_argument("--min-fps", type=float, default=25.0, help="Minimum target FPS.")
    parser.add_argument("--max-ram-mb", type=float, default=1200.0, help="Maximum RAM usage in MB.")
    parser.add_argument("--min-stability", type=float, default=0.75, help="Minimum OCR stability ratio.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _arg_parser().parse_args(argv)
    project_root = Path(__file__).resolve().parent
    config = load_app_config(project_root, overrides={"source_path": args.source})

    device = escolher_dispositivo()
    processor = _build_processor(config, device)
    process = psutil.Process()

    fps_values: list[float] = []
    mem_values_mb: list[float] = []
    track_texts: dict[int, list[str]] = {}
    recovered_failures = 0

    with InputSourceReader(config.source_path, config.image_extensions) as reader:
        confirmar_imediato = reader.is_image
        for packet in reader.frames():
            if packet.frame_idx > args.max_frames:
                break

            try:
                if packet.frame_idx == 3:
                    raise RuntimeError("Falha injetada para teste de recuperacao.")
                result = processor.process_frame(packet.frame, packet.frame_idx, confirmar_imediato)
                recovered_failures += 1 if packet.frame_idx > 3 else 0
            except Exception:
                continue

            fps_values.append(result.metrics.fps)
            mem_values_mb.append(process.memory_info().rss / (1024 * 1024))
            for plate in result.plates:
                track_id = int(plate.get("vehicle_track_id", -1))
                if track_id < 0:
                    continue
                track_texts.setdefault(track_id, []).append(str(plate.get("text") or ""))

    if not fps_values:
        print("[validate] Nenhum frame processado com sucesso.")
        return 2

    avg_fps = statistics.mean(fps_values)
    max_ram = max(mem_values_mb) if mem_values_mb else 0.0
    stability = _compute_stability(track_texts)

    print(f"[validate] avg_fps={avg_fps:.2f}")
    print(f"[validate] max_ram_mb={max_ram:.2f}")
    print(f"[validate] ocr_stability={stability:.3f}")
    print(f"[validate] recovered_after_failure={recovered_failures > 0}")

    ok = True
    if avg_fps < args.min_fps:
        print(f"[validate][fail] FPS abaixo do minimo: {avg_fps:.2f} < {args.min_fps:.2f}")
        ok = False
    if max_ram > args.max_ram_mb:
        print(f"[validate][fail] RAM acima do limite: {max_ram:.2f}MB > {args.max_ram_mb:.2f}MB")
        ok = False
    if stability < args.min_stability:
        print(f"[validate][fail] Estabilidade OCR baixa: {stability:.3f} < {args.min_stability:.3f}")
        ok = False
    if recovered_failures <= 0:
        print("[validate][fail] Pipeline nao recuperou apos falha injetada.")
        ok = False
    return 0 if ok else 1


def _compute_stability(track_texts: dict[int, list[str]]) -> float:
    if not track_texts:
        return 0.0
    ratios: list[float] = []
    for texts in track_texts.values():
        filtered = [text for text in texts if text and text != "N/A"]
        if len(filtered) <= 1:
            continue
        changes = sum(1 for idx in range(1, len(filtered)) if filtered[idx] != filtered[idx - 1])
        ratios.append(max(0.0, 1.0 - (changes / max(1, len(filtered) - 1))))
    if not ratios:
        return 0.0
    return float(statistics.mean(ratios))


if __name__ == "__main__":
    raise SystemExit(main())
