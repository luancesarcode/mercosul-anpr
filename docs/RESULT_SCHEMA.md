# Schema de resultado

Versão atual: `1.0.0`.

O JSON é o contrato canônico. O CSV é uma visão consolidada, adequada a planilhas e integrações simples.

## Campos principais

| Campo | Tipo | Descrição |
| --- | --- | --- |
| `schema_version` | string | Versão semântica do contrato |
| `run_id` | string | Identificador da execução |
| `source` | string | Fonte processada |
| `source_type` | string | `image` ou `video_or_stream` |
| `status` | string | Estado final da execução |
| `started_at`, `completed_at` | ISO-8601 | Instantes UTC |
| `duration_ms` | number | Duração total |
| `frames_processed` | integer | Total de frames |
| `frames[]` | array | Observações e métricas por frame |
| `vehicles[]` | array | Placas consolidadas por track |
| `artifacts` | object | Nomes dos arquivos gerados |

Cada observação contém `track_id`, texto, confiança OCR, padrão, confiança do detector e bounding box `[x1, y1, x2, y2]`.

## Compatibilidade

- Inclusão de campo opcional é compatível dentro da versão principal.
- Remoção, renomeação ou mudança de semântica exige uma nova versão principal.
- Consumidores devem ignorar campos desconhecidos e verificar `schema_version`.
- Testes validam serialização JSON, cabeçalhos CSV e consolidação temporal.
