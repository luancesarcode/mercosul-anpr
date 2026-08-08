# Ajuste de detecção e OCR

## Melhorias já aplicadas

1. **Modelos reutilizados entre jobs:** evita recarregar YOLO e PaddleOCR em cada solicitação da API.
2. **Upscale limitado:** recortes baixos são ampliados até uma altura útil, com limite para evitar custo excessivo.
3. **CLAHE:** melhora contraste local em placas com iluminação desigual.
4. **Polaridade normalizada:** a binarização tenta manter fundo claro para reconhecimento consistente.
5. **Deskew guiado:** a faixa azul Mercosul estima a inclinação e gera variantes geométricas conservadoras, mantendo também o deskew por contornos.
6. **Consenso:** o mesmo texto lido em variantes diferentes recebe bônus pequeno e limitado; uma confiança isolada continua registrada.
7. **Seleção de tokens:** padrões com menos conversões são preferidos e um a três caracteres espúrios nas bordas podem ser descartados com penalidade rastreável.
8. **Ambiguidades contextuais ponderadas:** trocas fortes (`0/O`, `1/I`, `5/S`, `8/B`) custam menos que hipóteses fracas (`0/Q`, `7/Y`) e só ocorrem nas posições exigidas pelo padrão.
9. **Limites contra invenção:** leituras que exigem mais de duas substituições são rejeitadas; a faixa azul só vence outro padrão quando a diferença é uma única ambiguidade plausível.
10. **Confiança calibrada:** conversões e caracteres descartados nas bordas reduzem a confiança exibida, em vez de preservar artificialmente a confiança bruta do OCR.
11. **Rastreabilidade:** cada candidato guarda texto bruto, janela usada, posições convertidas, motivo e penalidade aplicada.
12. **Placa isolada:** uma faixa azul dominante permite recortar imagens em que a placa ocupa quase todo o quadro e o detector de objetos retorna caixa parcial.
13. **Intervalo de OCR:** vídeos podem reaproveitar voto estável entre frames para reduzir inferências.

Essas mudanças melhoram a robustez esperada e o custo operacional, mas somente o benchmark pode quantificar o efeito em um dataset representativo.

## Formato brasileiro e conversão contextual

A Resolução CONTRAN nº 969/2022 define sete caracteres no formato `LLLNLNN`. A tabela `0→A` até `9→J` do mesmo regulamento é uma regra cadastral para substituir uma placa antiga, não uma tabela de semelhança visual. Por isso, o OCR aceita qualquer letra na posição `L` e corrige apenas glifos visualmente confundíveis, como `3/J` ou `4/A`, quando a posição e a faixa azul sustentam essa hipótese.

Fonte normativa: [anexos da Resolução CONTRAN nº 969/2022](https://www.gov.br/transportes/pt-br/assuntos/transito/conteudo-contran/resolucoes/resolucao9692022anexos.pdf).

## Ordem recomendada de otimização

1. Congele um manifesto de avaliação autorizado.
2. Meça o baseline com os pesos e configurações atuais.
3. Altere uma variável por vez.
4. Compare placa completa, caracteres, falsos positivos, falsos negativos, latência e memória.
5. Rejeite mudanças que melhoram poucos exemplos e pioram o conjunto completo.

## Parâmetros com maior impacto

| Variável | Efeito | Risco |
| --- | --- | --- |
| `ANPR_IMG_SIZE` | Mais detalhes na detecção | Latência e memória maiores |
| `ANPR_VEHICLE_CONF` | Filtra veículos fracos | Pode perder veículos distantes |
| `ANPR_PLATE_CONF` | Filtra placas | Valores altos reduzem recall |
| `ANPR_PLATE_TEXT_CONF_MIN` | Filtra OCR exibido | Pode ocultar leitura correta difícil |
| `OCR_MAX_VARIANTS` | Amplia busca do OCR | Custo quase proporcional |
| `PADDLE_OCR_LANGS` | Testa modelos de idioma | Mais memória e latência |
| `ANPR_OCR_INTERVAL_FRAMES` | Reduz OCR em vídeo | Atualização mais lenta quando a placa muda |

## Próximos experimentos

- Calibrar confiança real por faixa de iluminação e resolução.
- Comparar OCR único `en` com `pt,en`.
- Fazer inferência em lote para múltiplos ROIs, medindo memória.
- Avaliar retificação por perspectiva somente quando quatro cantos forem confiáveis.
- Treinar detector de placa com exemplos autorizados de ângulo, chuva e baixa luz.
- Separar métricas por placa Mercosul e padrão anterior.

Não implemente super-resolução generativa em placas reais: ela pode inventar caracteres visualmente plausíveis e comprometer rastreabilidade.
