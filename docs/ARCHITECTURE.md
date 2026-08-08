# Arquitetura

O projeto usa o padrão `src-layout` para evitar imports acidentais do diretório de trabalho e separar o pacote distribuível dos arquivos de operação.

## Fluxo

```text
CLI ─────────┐
             ├─> ProcessingService -> InputSourceReader -> PipelineProcessor
API/Web ─────┤                         |                    |
Câmera Web ──┘                         |                    |
                                  |                    +-> YOLO veículos
                                  |                    +-> tracking IoU
                                  |                    +-> YOLO placas/ROI
                                  |                    +-> OCR + consenso
                                  |                    +-> voto temporal
                                  |
                                  +-> mídia + TXT + JSON + CSV
                                  +-> frame anotado em memória
```

CLI e API dependem somente do serviço de aplicação. Elas não constroem detectores nem interpretam detalhes do pipeline.

## Pacotes

- `application/`: coordena uma execução, reutiliza modelos e gera o contrato final.
- `api/`: valida uploads, controla jobs e sessões de câmera, autenticação opcional, retenção, métricas e downloads.
- `core/`: configuração imutável, constantes, logging e profiling.
- `domain/`: dataclasses do schema público `1.0.0` e consolidação por track.
- `io_layer/`: leitura uniforme de imagem/vídeo/stream e writers.
- `pipeline/`: associação, tracking, voto temporal e processamento por frame.
- `render/`: overlay e mídia anotada.
- `vision/`: integrações YOLO/PaddleOCR e regras brasileiras de placa.
- `web/`: interface estática servida pela própria API.

## Estado e concorrência

`ProcessingService` mantém os modelos carregados, mas cria tracker e voto temporal novos para cada fonte. Um lock serializa inferências no processo, evitando estado cruzado e excesso de concorrência CPU. A fila local usa um worker e persiste snapshots de status em `runs/jobs/<id>/status.json`.

`RealtimeSessionManager` reserva uma sessão local, preserva o `PipelineProcessor` entre frames e processa uma requisição por vez. O navegador só captura o frame seguinte depois da resposta anterior. As imagens da câmera são decodificadas, limitadas em resolução, inferidas e codificadas novamente sem escrita em disco. Jobs e câmera são mutuamente exclusivos para proteger o estado dos detectores compartilhados.

Para várias réplicas, jobs devem migrar para uma fila externa e os artefatos para armazenamento compartilhado. O contrato de domínio e as rotas podem permanecer.

## Configuração

Precedência:

1. argumento explícito da CLI;
2. variável de ambiente ou `.env`;
3. padrão em `core/constants.py`.

`ANPR_PROJECT_ROOT` permite executar o pacote Python fora da raiz do repositório sem perder as referências de modelos, entradas e saídas.

## Segurança e privacidade

- uploads têm nome normalizado, limite de bytes e extensões permitidas;
- downloads são restritos aos artefatos registrados no diretório do job;
- chave `X-API-Key` é opcional para redes confiáveis e obrigatória quando configurada;
- jobs antigos são removidos pela retenção local;
- frames da câmera existem somente em memória e a sessão expira quando fica ociosa;
- entradas e saídas não são enviadas a serviços externos pelo código da aplicação;
- modelos internos do PaddleOCR ainda são baixados na primeira execução.

## Execução

O projeto usa apenas Python e ambiente virtual. CLI, API e interface web compartilham o mesmo pacote instalado em modo editável pelo script `install.ps1` ou `install.bat`.
