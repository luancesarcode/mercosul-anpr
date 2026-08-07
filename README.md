# Mercosul ANPR

[![CI](https://github.com/luancesarcode/mercosul-anpr/actions/workflows/ci.yml/badge.svg)](https://github.com/luancesarcode/mercosul-anpr/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10%20%7C%203.11-blue.svg)](pyproject.toml)

Pipeline open source para reconhecimento de placas brasileiras em imagens e vídeos. Combina YOLO, PaddleOCR, rastreamento e voto temporal com CLI, API REST, interface web local e resultados versionados em JSON/CSV.

> **Estado:** alpha. A base técnica é reproduzível, mas a precisão ainda depende de um benchmark público com dados autorizados. Não use o projeto para decisões automáticas de fiscalização, segurança ou identificação de pessoas.

## Recursos

- Detecção de veículos e placas com YOLO.
- OCR para placas Mercosul e padrão brasileiro anterior.
- Associação placa/veículo, tracking e estabilização temporal.
- Pré-processamento OCR com upscale, CLAHE, binarização, rotação pela faixa azul e consenso entre variantes.
- Conversões contextuais ponderadas, limite contra correções excessivas e confiança ajustada para cada leitura.
- Imagem ou vídeo anotado, log humano, JSON versionado e CSV consolidado.
- CLI instalável, API OpenAPI e interface responsiva com upload, progresso e downloads.
- Jobs locais com limite de upload, timeout, retenção e chave de API opcional.
- Modelos carregados uma única vez entre jobs da API.
- Ambiente Windows reproduzível, CI com lint e testes e cobertura mínima de 85%.
- Benchmark reproduzível que exige origem e permissão dos exemplos.

## Início rápido — interface web local

Requisitos: Git e Python 3.10 ou 3.11 de 64 bits.

```powershell
git clone https://github.com/luancesarcode/mercosul-anpr.git
cd mercosul-anpr
.\install.ps1 -Dev
.\.venv311\Scripts\Activate.ps1
mercosul-anpr-api
```

Abra [http://localhost:8000](http://localhost:8000). A documentação interativa da API fica em [http://localhost:8000/docs](http://localhost:8000/docs).

Entradas e resultados permanecem na máquina. Jobs e artefatos são gravados em `runs/jobs/`; os modelos internos do PaddleOCR ficam no cache do usuário.

## Início rápido — CLI

Coloque uma entrada em `Imagens_input/` ou `Videos_input/` e execute:

```powershell
.\.venv311\Scripts\Activate.ps1
mercosul-anpr Imagens_input\minha-imagem.jpg
```

Para imprimir o contrato JSON também no terminal:

```powershell
mercosul-anpr Imagens_input\minha-imagem.jpg --print-json
```

Os artefatos são gravados em `runs/predict/`:

```text
entrada.jpg    mídia anotada
entrada.txt    resultado legível
entrada.json   contrato completo por frame
entrada.csv    uma linha consolidada por veículo/placa
```

## API local

| Método | Endpoint | Finalidade |
| --- | --- | --- |
| `GET` | `/health` | Disponibilidade do serviço |
| `GET` | `/version` | Versão da aplicação |
| `GET` | `/metrics` | Métricas locais em formato Prometheus |
| `POST` | `/api/v1/process/image` | Processamento síncrono de imagem |
| `POST` | `/api/v1/jobs` | Cria job assíncrono para imagem ou vídeo |
| `GET` | `/api/v1/jobs/{id}` | Consulta status e progresso |
| `GET` | `/api/v1/jobs/{id}/result` | Retorna o JSON final |
| `GET` | `/api/v1/jobs/{id}/artifacts/{tipo}` | Baixa mídia, JSON, CSV ou log |

Consulte [docs/API.md](docs/API.md) e [docs/RESULT_SCHEMA.md](docs/RESULT_SCHEMA.md).

## Estrutura

```text
src/mercosul_anpr/
  application/   casos de uso compartilhados pela CLI e API
  api/           HTTP, jobs, limites, autenticação e métricas
  core/          configuração, logging e profiling
  domain/        schema versionado de resultados
  io_layer/      leitura de fontes e persistência
  pipeline/      tracking, associação, voto temporal e orquestração
  render/        overlays e exportação de mídia
  vision/        detectores e OCR
  web/           interface local em HTML, CSS e JavaScript
tests/           testes automatizados
benchmarks/      contrato do benchmark, sem dados pessoais
docs/media/      espaços separados para imagens, GIFs e vídeos futuros
```

Detalhes em [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Configuração

Copie `.env.example` para `.env`. Argumentos da CLI têm precedência sobre ambiente e valores padrão.

Configurações da interface/API:

```env
ANPR_MAX_UPLOAD_MB=100
ANPR_JOB_TIMEOUT_SECONDS=1800
ANPR_JOB_RETENTION_HOURS=24
# ANPR_API_KEY=uma-chave-forte
```

Configurações OCR:

```env
PADDLE_OCR_LANGS=pt,en
OCR_MAX_VARIANTS=6
OCR_EARLY_STOP_SCORE=98
ANPR_OCR_INTERVAL_FRAMES=1
```

Não altere thresholds com base em uma única imagem. Use o processo de [ajuste e benchmark de OCR](docs/OCR_TUNING.md).

## Benchmark

O repositório não inclui dataset. Crie um manifesto privado com dados autorizados e execute:

```bash
mercosul-anpr-benchmark benchmarks/manifest.csv
```

O relatório mede acerto da placa completa, acerto por caractere e latência média. Veja [benchmarks/README.md](benchmarks/README.md).

## Demonstração visual

Os blocos abaixo já reservam a apresentação do projeto sem publicar imagens de placas antes da revisão de privacidade e licença.

### Interface web

<table>
  <tr>
    <th width="50%">Envio e acompanhamento</th>
    <th width="50%">Resultado da análise</th>
  </tr>
  <tr>
    <td align="center">
      <br><em>Espaço reservado para a tela de upload.</em><br><br>
      <code>docs/media/images/interface-upload.webp</code><br><br>
    </td>
    <td align="center">
      <br><em>Espaço reservado para o resultado anotado.</em><br><br>
      <code>docs/media/images/interface-resultado.webp</code><br><br>
    </td>
  </tr>
</table>

### OCR em ação

<table>
  <tr>
    <th width="50%">Imagem de entrada autorizada</th>
    <th width="50%">Detecção e leitura consolidadas</th>
  </tr>
  <tr>
    <td align="center">
      <br><em>Espaço reservado para uma placa fictícia ou autorizada.</em><br><br>
      <code>docs/media/images/exemplo-entrada.webp</code><br><br>
    </td>
    <td align="center">
      <br><em>Espaço reservado para a saída correspondente.</em><br><br>
      <code>docs/media/images/exemplo-resultado.webp</code><br><br>
    </td>
  </tr>
</table>

### GIF do fluxo completo

<p align="center">
  <br><em>Espaço reservado para um GIF curto: upload → processamento → resultado.</em><br><br>
  <code>docs/media/gifs/fluxo-completo.gif</code><br><br>
</p>

Os diretórios `docs/media/images/`, `docs/media/gifs/` e `docs/media/videos/` permanecem vazios até existirem mídias autorizadas. Consulte as regras em [docs/media/README.md](docs/media/README.md).

## Limitações e pendências externas

- A distribuição oficial usa Python e ambiente virtual; não há uma segunda configuração de runtime para manter em paralelo.
- GPU continua opcional e experimental; a instalação local padrão usa PyTorch CPU.
- A primeira execução requer internet para baixar modelos internos do PaddleOCR.
- Origem e licença de redistribuição dos pesos em `modelos/` ainda precisam ser confirmadas pelo mantenedor.
- Métricas públicas dependem de um conjunto de avaliação autorizado, que não deve ser inventado ou extraído de placas reais sem permissão.
- A API usa uma fila local em processo; múltiplas réplicas exigem um backend de fila compartilhado.

## Privacidade e licença

Placas e imagens podem ser dados pessoais ou sensíveis. Processe somente ambientes autorizados e defina retenção compatível com seu contexto. O código usa [licença MIT](LICENSE); pesos e datasets podem ter licenças próprias.
