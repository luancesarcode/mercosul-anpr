# ANPR Pipeline (Production-Ready)

Repositório: `anpr-mercosul-pipeline`

Sistema ANPR (Automatic Number Plate Recognition) para Windows 10/11 com:

- deteccao de veiculos (YOLO)
- deteccao de placas (YOLO, global + ROI)
- OCR PaddleOCR
- validacao/correcao Mercosul e padrao antigo
- voto temporal por `track_id`
- logs incrementais com rotacao
- profiling e validacao de sistema

## Arquitetura

```text
core/
  config.py
  constants.py
  logger.py
  profiling.py

pipeline/
  processor.py
  tracker.py
  associator.py
  temporal_voter.py

vision/
  vehicle_detector.py
  plate_detector.py
  ocr_engine.py
  ocr_rules.py
  ocr/
    aplicar_ocr.py
    processar_contorno.py
    processar_imagem.py
    utils.py

render/
  overlay.py
  exporter.py

io_layer/
  video_reader.py
  result_writer.py

tests/
  test_tracking.py
  test_association.py
  test_ocr.py
  test_pipeline.py
  test_temporal_voter.py

main.py
```

Observacao: as importacoes usam `io_layer/` para evitar conflito com o modulo padrao `io` do Python. Arquivos nao essenciais ao fluxo principal (antigo diretorio `io/`, `validate_system.py`, relatorio tecnico) foram movidos para `usarDepois/`.

## Requisitos

- Python >= 3.10 (recomendado 3.11)
- Windows 10/11

## Instalacao

### PowerShell

```powershell
.\install.ps1
```

### CMD

```cmd
install.bat
```

## Configuracao via `.env`

Exemplo (`.env` na raiz):

```env
ANPR_SOURCE=Videos_input/Test1.mp4
ANPR_COCO_MODEL=modelos/yolov8n.pt
ANPR_PLATE_MODEL=modelos/best.pt
ANPR_RUNS_DIR=runs/predict
ANPR_USE_ROI_DETECTION=true
ANPR_USE_HYBRID_ASSOCIATION=true
ANPR_ASSOCIATION_THRESHOLD=0.34
ANPR_ROI_CACHE_TTL=2
ANPR_PLATE_MIN_OCCURRENCES=2
ANPR_PLATE_MIN_SCORE=65.0
ANPR_OCR_INTERVAL_FRAMES=1
ANPR_PLATE_TEXT_CONF_MIN=70.0
ANPR_PLATE_TEXT_CONF_MAX=100.0
ANPR_PLATE_BBOX_SMOOTH_ENABLED=true
ANPR_PLATE_BBOX_SMOOTH_ALPHA=0.35
ANPR_ENABLE_CPROFILE=false
ANPR_ENABLE_LINE_PROFILER=false
```

Crie rapidamente:

```powershell
Copy-Item .env.example .env
```

## Execucao

### Modo padrao (compatibilidade com constante no `main.py`)

```powershell
.\.venv311\Scripts\python.exe main.py
```

### Com argumentos

```powershell
.\.venv311\Scripts\python.exe main.py Videos_input\Test1.mp4 --plate-model modelos\best.pt --coco-model modelos\yolov8n.pt
```

## Saidas

- Video/imagem anotado: `runs/predict/<nome>.mp4` ou `runs/predict/<nome>.jpg`
- Log textual incremental da execucao: `runs/predict/<nome>.txt`
- Log rotativo estruturado: `runs/logs/anpr.log`
- cProfile (se habilitado): `runs/predict/profile_main.prof` e `runs/predict/profile_main.txt`
- line_profiler (se habilitado): `runs/predict/line_profile.txt`

## Logging estruturado

Formato de eventos por frame:

```text
[2026-02-17T14:32:11.321] FRAME=245 VEHICLE=3 PLATE=ABC1D23 CONF=0.9400 DETECTED=2
```

## Testes

```powershell
.\.venv311\Scripts\python.exe -m pytest
```

Configuracao de cobertura (`pyproject.toml`):
- escopo de cobertura: `pipeline.*` + `vision.ocr_rules`
- `cov-fail-under = 85`

## Anti-tremor e filtro de confianca

- `ANPR_PLATE_MIN_OCCURRENCES`: minimo de ocorrencias no voto temporal antes de exibir.
- `ANPR_PLATE_MIN_SCORE`: score medio minimo no voto temporal.
- `ANPR_OCR_INTERVAL_FRAMES`: roda OCR a cada N frames por `track_id` (`1`=todos, `2/3`=mais rapido).
- `ANPR_PLATE_TEXT_CONF_MIN` / `ANPR_PLATE_TEXT_CONF_MAX`: intervalo de confianca permitido para exibir placa.
- `ANPR_PLATE_BBOX_SMOOTH_ENABLED`: ativa suavizacao do bbox de placa por `track_id`.
- `ANPR_PLATE_BBOX_SMOOTH_ALPHA`: intensidade da suavizacao (`0.05` a `1.0`; menor = mais suave).

## Validacao de sistema

O script de validacao foi movido para `usarDepois/validate_system.py`. Para usa-lo, copie de volta para a raiz e execute:

```powershell
Copy-Item usarDepois\validate_system.py .\validate_system.py
.\.venv311\Scripts\python.exe validate_system.py --source Videos_input\Test1.mp4 --max-frames 150 --min-fps 25 --max-ram-mb 1200
```

Verifica:

- FPS medio
- uso de memoria
- estabilidade OCR
- recuperacao apos falha injetada

## Observacoes de compatibilidade

- O formato dos outputs `[info]` e `[result]` foi mantido.
- OCR continua em PaddleOCR com o mesmo pipeline base.
- `main.py` permanece como entrypoint unico.
