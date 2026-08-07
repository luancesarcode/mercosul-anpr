# Pesos de modelos

Os pesos desta pasta são carregados pelo pacote Python local. Antes do primeiro release estável, o mantenedor deve preencher a origem, a licença e a versão do treinamento de cada arquivo; a licença MIT do código não substitui a licença dos pesos.

| Arquivo | Uso atual | SHA-256 | Origem/licença |
| --- | --- | --- | --- |
| `yolov8n.pt` | Detecção de veículos | `31E20DDE3DEF09E2CF938C7BE6FE23D9150BBBE503982AF13345706515F2EF95` | A confirmar |
| `best.pt` | Detecção de placas | `62EFB271EC3502EFDEDA0022067F02D688F9C76E25305EF5854679E42AE25B4C` | A confirmar |
| `license_plate_detector.pt` | Peso legado; não usado pela configuração padrão | `8EC3B254A6C87610F037A90957462CAFA11A9C03224E33A28C6A1D1AC2AC51B0` | A confirmar |

## Atualização

Ao substituir um peso:

1. Registre origem, licença, conjunto de treinamento e métricas conhecidas.
2. Atualize o hash SHA-256.
3. Execute os testes e o benchmark de regressão.
4. Documente a mudança no `CHANGELOG.md`.

No PowerShell, calcule o hash com:

```powershell
Get-FileHash modelos\nome-do-modelo.pt -Algorithm SHA256
```
