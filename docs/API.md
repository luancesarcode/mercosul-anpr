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

## Ciclo de status

```text
queued -> running -> completed
                  -> failed
```

Jobs de imagem e vídeo usam a mesma fila local. A execução dos modelos é serializada porque várias inferências CPU simultâneas normalmente aumentam latência e memória sem elevar throughput.

## Limites

- `ANPR_MAX_UPLOAD_MB`: tamanho máximo recebido, padrão 100 MB.
- `ANPR_JOB_TIMEOUT_SECONDS`: tempo máximo observado pelo callback de progresso, padrão 1800 s.
- `ANPR_JOB_RETENTION_HOURS`: retenção local, padrão 24 h.
- Extensões são validadas antes da fila; conteúdo malformado é rejeitado pelo leitor na execução.

O timeout é cooperativo entre frames. Uma inferência individual que travar em biblioteca nativa não pode ser interrompida com segurança por uma thread Python; produção crítica deve isolar workers em processos.

## Artefatos

Os tipos aceitos na rota de download são `media`, `text`, `json` e `csv`. O servidor resolve somente nomes registrados pelo resultado e impede caminhos fora da pasta do job.
