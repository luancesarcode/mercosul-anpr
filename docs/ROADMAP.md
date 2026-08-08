# Roadmap

## Entregue na base atual

### Distribuição

- [x] Execução local exclusivamente em Python, sem runtimes paralelos.
- [x] CLI instalável e `src-layout`.
- [x] Configuração por CLI, `.env` e padrões.
- [x] CI para lint, testes, cobertura e build.
- [x] Documentação de segurança, contribuição e arquitetura.

### Resultados estruturados

- [x] Schema versionado `1.0.0`.
- [x] JSON detalhado por frame.
- [x] CSV consolidado por track/placa.
- [x] Confiança, frames, padrão e bounding boxes.
- [x] Testes de serialização e consolidação.

### API e interface

- [x] Health, versão, métricas e OpenAPI.
- [x] Processamento síncrono de imagem.
- [x] Jobs para imagem e vídeo.
- [x] Progresso, erros e downloads.
- [x] Limite de upload, timeout cooperativo e retenção.
- [x] Autenticação opcional por chave.
- [x] Interface responsiva com drag-and-drop e estados acessíveis.
- [x] Câmera do navegador com seleção de dispositivo e frames anotados em tempo real.
- [x] Sessão temporal em memória sem persistência automática dos frames.

### Qualidade e OCR

- [x] Harness de benchmark com manifesto autorizado.
- [x] Métricas de placa completa, caractere e latência.
- [x] Reutilização dos modelos entre jobs.
- [x] Variantes OCR com upscale, CLAHE, binarização e deskew.
- [x] Consenso limitado entre pré-processamentos.
- [x] Pastas separadas e vazias para imagens, vídeos e GIFs futuros.

## Dependências externas antes de um release estável

- [ ] Confirmar e registrar origem/licença de cada peso em `modelos/`.
- [ ] Montar dataset de avaliação com origem e permissão documentadas.
- [ ] Publicar métricas reais de acurácia, falsos positivos/negativos, FPS e memória.
- [ ] Validar clone e execução também em Linux x86_64 na CI com uma amostra redistribuível.
- [ ] Publicar o primeiro release versionado.

Esses itens não podem ser preenchidos de forma honesta apenas com código.

## Evoluções opcionais

- [ ] Imagem/perfil NVIDIA GPU depois de medir CPU e garantir ambiente de teste.
- [ ] Backend de fila compartilhado para múltiplas réplicas.
- [ ] Workers isolados em processos para timeout forçado.
- [ ] Métricas de memória, filas e duração agregadas por Prometheus.
- [ ] Inferência em lote de ROIs após benchmark de precisão e memória.
- [ ] Retificação de perspectiva baseada em cantos confiáveis.
- [ ] Testes de regressão com exemplos anonimizados e redistribuíveis.

## Fora de escopo

- consulta de proprietário ou bases governamentais;
- armazenamento permanente por padrão;
- super-resolução generativa de caracteres;
- promessa de adequação legal ou produção sem validação do operador.
