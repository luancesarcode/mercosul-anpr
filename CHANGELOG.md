# Changelog

Todas as mudanças relevantes serão documentadas neste arquivo. O projeto pretende seguir versionamento semântico a partir do primeiro release público.

## [Não publicado]

### Adicionado

- Layout `src/mercosul_anpr` com camadas de aplicação, domínio, API e interface web.
- Resultados estruturados em JSON e CSV com schema `1.0.0`.
- Jobs locais, autenticação opcional, limites, retenção, métricas e downloads.
- Interface responsiva para upload, progresso, visualização e artefatos.
- Modo de câmera ao vivo com seleção de dispositivo, sessões temporais em memória, métricas e overlay atualizado por frame.
- Benchmark com manifesto que exige origem e permissão de uso.
- Pré-processamentos OCR com upscale, CLAHE, deskew e consenso limitado.
- Espaços vazios e separados para imagens, vídeos e GIFs futuros.
- Execução local em Python para CPU, com GPU opcional.
- Cache persistente dos modelos internos do PaddleOCR.
- Metadados de pacote e comando `mercosul-anpr`.
- Opção `--version` na CLI.
- Workflow de CI para lint, testes, cobertura e validação do pacote Python.
- Documentação de arquitetura, roadmap, contribuição e segurança.

### Alterado

- Configuração agora respeita a precedência CLI, `.env` e padrões.
- Dependências de desenvolvimento foram separadas das dependências de runtime.
- Instaladores locais detectam e recriam ambientes virtuais inválidos.
- OCR agora usa padrão visual Mercosul, consenso por variantes, tolerância a caracteres extras e correção de inclinação pela faixa azul.
- Conversões contextuais do OCR agora usam penalidades por semelhança, limite de alterações, confiança ajustada e metadados auditáveis.
- Detecções globais válidas são preservadas mesmo quando veículos não relacionados aparecem na imagem.
- Persistência de jobs usa snapshots temporários exclusivos, retries e escrita limitada por intervalo.
- README foi reorganizado como apresentação de portfólio, com arquitetura, recursos, uso da câmera e áreas reservadas para demonstrações.
