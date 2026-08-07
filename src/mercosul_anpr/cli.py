"""Command-line adapter for Mercosul ANPR."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from mercosul_anpr import __version__
from mercosul_anpr.application.service import ProcessingService
from mercosul_anpr.core.config import AppConfig, load_app_config
from mercosul_anpr.core.constants import PROJECT_ROOT


def build_parser() -> argparse.ArgumentParser:
    """Create the public CLI parser."""
    parser = argparse.ArgumentParser(
        prog="mercosul-anpr",
        description="Reconhecimento automático de placas brasileiras em imagens e vídeos.",
    )
    parser.add_argument("source", nargs="?", help="Arquivo de entrada, câmera ou stream.")
    parser.add_argument("--coco-model", dest="coco_model", help="Modelo YOLO de veículos.")
    parser.add_argument("--plate-model", dest="plate_model", help="Modelo YOLO de placas.")
    parser.add_argument("--runs-dir", dest="runs_dir", help="Diretório de saída.")
    parser.add_argument("--profile", action="store_true", help="Ativa cProfile nesta execução.")
    parser.add_argument("--line-profile", action="store_true", help="Ativa line_profiler, se instalado.")
    parser.add_argument("--print-json", action="store_true", help="Imprime o resultado estruturado no terminal.")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def load_config_from_args(args: argparse.Namespace) -> AppConfig:
    """Apply CLI overrides over environment and defaults."""
    return load_app_config(
        PROJECT_ROOT,
        overrides={
            "source_path": args.source,
            "coco_model_path": args.coco_model,
            "plate_model_path": args.plate_model,
            "runs_dir": args.runs_dir,
        },
    )


def main(argv: list[str] | None = None) -> int:
    """Run the command-line application."""
    args = build_parser().parse_args(argv)
    try:
        config = load_config_from_args(args)
        source: Path | str | int = args.source or config.source_path
        result = ProcessingService(config).process(
            source,
            output_dir=config.runs_dir,
            enable_cprofile=args.profile,
            enable_line_profiler=args.line_profile,
        )
        if args.print_json:
            print(json.dumps(result.to_dict(), ensure_ascii=False))
        return 0
    except FileNotFoundError as exc:
        print(exc, file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"[erro] Falha de execucao: {exc}", file=sys.stderr)
        return 1


principal = main


if __name__ == "__main__":
    raise SystemExit(main())
