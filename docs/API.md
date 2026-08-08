# API local

A API usa FastAPI e publica OpenAPI em `/openapi.json`, documentação Swagger em `/docs` e ReDoc em `/redoc`.

## Iniciar com Python

```powershell
.\install.ps1
.\.venv311\Scripts\Activate.ps1
mercosul-anpr-api
```

## Criar e acompanhar um job

```bash
curl -F "file=@Imagens_input/Test1.jpg" http://localhost:8000/api/v1/jobs
curl http://localhost:8000/api/v1/jobs/ID_DO_JOB
curl http://localhost:8000/api/v1/jobs/ID_DO_JOB/result
```

Quando `ANPR_API_KEY` estiver definido, envie `X-API-Key` em todas as rotas `/api/v1/*`.

## CPU e NVIDIA

```bash
# Consulta a preferência e o diagnóstico em cache
curl http://localhost:8000/api/v1/system/compute

# Repete o teste do driver, PyTorch e CUDA
curl -X POST http://localhost:8000/api/v1/system/compute/test

# Define o dispositivo dos próximos processamentos
curl -X PUT -H "Content-Type: application/json" \
  -d '{"preference":"cpu"}' \
  http://localhost:8000/api/v1/system/compute
```

As preferências aceitas são `auto`, `cpu` e `nvidia`. `auto` usa NVIDIA nos detectores YOLO apenas quando o PyTorch confirma uma GPU CUDA acessível; caso contrário, usa CPU. A API rejeita NVIDIA indisponível e não permite trocar o dispositivo enquanto houver job ou sessão de câmera ativos. O PaddleOCR continua usando a configuração própria `PADDLE_USE_GPU`.

## Ciclo de status

```text
queued -> running -> completed
                  -> failed
```

Jobs de imagem e vídeo usam a mesma fila local. A execução dos modelos é serializada porque várias inferências CPU simultâneas normalmente aumentam latência e memória sem elevar throughput.

## Câmera do navegador

```bash
# 1. Abre uma sessão e prepara os modelos
curl -X POST http://localhost:8000/api/v1/realtime/sessions

# 2. Envia frames sequencialmente usando o id retornado
curl -F "file=@frame.jpg;type=image/jpeg" \
  http://localhost:8000/api/v1/realtime/sessions/ID_DA_SESSAO/frames

# 3. Encerra a sessão
curl -X DELETE http://localhost:8000/api/v1/realtime/sessions/ID_DA_SESSAO
```

O endpoint de frame aceita JPEG, PNG ou WEBP e retorna contagem de veículos, placas válidas, métricas por estágio e a imagem anotada como data URL JPEG. Os frames não são persistidos. A sessão mantém tracker, cache de ROI e voto temporal em memória.

Por segurança operacional, existe apenas uma sessão de câmera local por processo. Jobs de arquivo são rejeitados com `409` enquanto ela estiver ativa, e uma sessão não pode ser criada durante um job em execução.

## Limites

- `ANPR_MAX_UPLOAD_MB`: tamanho máximo recebido, padrão 100 MB.
- `ANPR_JOB_TIMEOUT_SECONDS`: tempo máximo observado pelo callback de progresso, padrão 1800 s.
- `ANPR_JOB_RETENTION_HOURS`: retenção local, padrão 24 h.
- `ANPR_REALTIME_SESSION_TTL_SECONDS`: expiração da sessão de câmera ociosa, padrão 300 s.
- `ANPR_REALTIME_MAX_FRAME_MB`: limite de cada frame recebido, padrão 5 MB.
- `ANPR_REALTIME_MAX_DIMENSION`: maior dimensão usada na inferência, padrão 1280 px.
- `ANPR_REALTIME_JPEG_QUALITY`: qualidade da imagem anotada retornada, padrão 82.
- Extensões são validadas antes da fila; conteúdo malformado é rejeitado pelo leitor na execução.

O timeout é cooperativo entre frames. Uma inferência individual que travar em biblioteca nativa não pode ser interrompida com segurança por uma thread Python; produção crítica deve isolar workers em processos.

## Artefatos

Os tipos aceitos na rota de download são `media`, `text`, `json` e `csv`. O servidor resolve somente nomes registrados pelo resultado e impede caminhos fora da pasta do job.
