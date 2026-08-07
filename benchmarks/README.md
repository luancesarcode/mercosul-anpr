# Benchmark

Este diretório contém somente o contrato do benchmark. Nenhuma imagem, vídeo, placa ou dado pessoal é versionado.

Crie uma cópia privada de `manifest.example.csv` e preencha uma linha por exemplo autorizado. O campo `permission` é obrigatório para evitar que métricas sejam publicadas com dados de origem desconhecida.

```csv
path,expected_plate,source,permission,hardware
../dataset/imagem-001.jpg,ABC1D23,dataset-interno,consentimento-documentado,Ryzen-CPU
```

Execute após instalar o projeto:

```bash
mercosul-anpr-benchmark benchmarks/manifest.csv
```

O relatório é gravado em `runs/benchmarks/<data>/benchmark.json`. Compare esse arquivo antes e depois de mudar modelos, thresholds ou pré-processamento OCR.
