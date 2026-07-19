# Relatorio Tecnico - Refatoracao ANPR

## 1. Objetivo

Transformar o pipeline ANPR em arquitetura modular de producao, mantendo funcionalidades existentes e compatibilidade operacional.

## 2. Principais mudancas

- Migracao de `main.py` monolitico para camadas:
  - `core/`: configuracao, constantes, logging
  - `vision/`: detectores e regras OCR
  - `pipeline/`: tracking, associacao, voto temporal e orquestracao
  - `render/`: overlays e exportacao
  - `io/`: leitura/escrita (espelhado em `io_layer/` por conflito com modulo padrao `io`)
- Logging incremental com `RotatingFileHandler` e flush por evento.
- Associacao placa-veiculo hibrida (IoU + distancia de centro + proporcao de area), com fallback de contencao total.
- Deteccao por ROI de veiculo com cache temporal configuravel (TTL).
- Profiling integrado (cProfile e line_profiler opcional).
- Suite de testes com `pytest` para tracking, associacao, OCR e pipeline.
- Script `validate_system.py` para verificacao operacional.

## 3. Compatibilidade

Preservado:

- Entry point principal em `main.py`
- OCR via PaddleOCR
- Formato de linhas `[info]` e `[result]`
- Saida em `runs/predict/*.mp4|*.jpg` + `*.txt`

## 4. Ganhos de arquitetura

- Menor acoplamento entre deteccao, OCR, tracking e render.
- Funcoes curtas e responsabilidades mais claras.
- Maior testabilidade (mocks e testes unitarios por modulo).
- Configuracao central via `.env` e `pathlib`.

## 5. Requisitos de producao implementados

- Sem hardcode absoluto de paths
- Type hints
- Docstrings em funcoes publicas
- Tratamento explicito de excecoes no entrypoint
- Logging estruturado e rotativo
- Validacao de recursos (memoria/FPS/estabilidade)

## 6. Riscos e recomendacoes

- O pacote `io` conflita com o modulo builtin do Python; por isso runtime usa `io_layer`.
- Para metas de FPS em Full HD, ajustar:
  - `ANPR_USE_ROI_DETECTION=true`
  - `ANPR_IMG_SIZE`
  - thresholds de deteccao
- Para cobertura >85%, expandir testes de integracao com amostras reais de video/imagem e mocks de falhas de inferencia.
