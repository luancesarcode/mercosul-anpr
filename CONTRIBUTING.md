# Como contribuir

Obrigado pelo interesse no Mercosul ANPR. Antes de implementar uma mudança grande, abra uma issue descrevendo o problema e a solução proposta.

## Ambiente de desenvolvimento

No Windows:

```powershell
.\install.ps1 -Dev
.\.venv311\Scripts\Activate.ps1
```

Ou instale manualmente:

```bash
python -m venv .venv
python -m pip install -r requirements-dev.txt
python -m pip install --no-deps -e .
```

## Verificações obrigatórias

```bash
python -m ruff check .
python -m pytest
python -m build
```

## Diretrizes

- Mantenha mudanças focadas e pequenas.
- Inclua testes para correções e novos comportamentos.
- Não adicione imagens ou vídeos com placas reais sem autorização e anonimização adequadas.
- Não registre segredos, caminhos pessoais, ambientes virtuais ou saídas de execução.
- Preserve a separação entre `vision`, `pipeline`, `render` e `io_layer`.
- Atualize README, roadmap ou changelog quando o comportamento público mudar.

## Commits e pull requests

Use mensagens curtas no imperativo, por exemplo `Add JSON result export`. Na pull request, explique:

1. O problema resolvido.
2. A abordagem escolhida.
3. Como a mudança foi testada.
4. Riscos, limitações ou impactos em desempenho.
