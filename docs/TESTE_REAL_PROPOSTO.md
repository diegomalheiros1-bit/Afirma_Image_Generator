# Proposta de teste pago mínimo — ainda não autorizada

O pedido exige autorização explícita somente após implementação, testes e
verificação simulada. Nenhuma chamada real foi realizada.

Preparação local já concluída por `python scripts/prepare_api_proposal.py`:
uma planilha fictícia independente, uma linha, DRY RUN aprovado (1 sucesso,
0 erros), sem `.env`, cliente de rede ou escrita em planilha de produção.

| Item | Proposta concreta |
| --- | --- |
| Planilha | `output/studio-verification/teste-real-proposto/campanha-1-imagem.xlsx` |
| ID | `API-TESTE-001` |
| Referências | `output/studio-verification/produtos/foto.png` e `output/studio-verification/marca/foto.png` (duas imagens fictícias de cores, não fotos de cliente) |
| Modo | Selecionar no software; mesma seleção direta para a linha |
| Modelo | `gpt-image-2.5-sunburst` |
| Parâmetros | `quality=low`, `size=1024x1024`, `background=opaque`, `output_format=png`; sem compressão |
| Quantidade | 1 imagem; máximo de jobs=1, imagens=1, limite da planilha=1, modo seguro=SIM |
| Timeout e retry | 120 segundos, zero novas tentativas automáticas |
| Saída | `output/studio-verification/teste-real-proposto/saida/api_teste_001.png` |
| Objetivo | Comprovar acesso à API, envio de duas referências, conteúdo PNG, gravação e CONCLUIDO persistido |

Prompt: fotografia publicitária de um frasco de perfume roxo ao lado de uma caixa
laranja, em fundo claro, sem texto; usar as cores das referências como inspiração.
Este teste comprova o fluxo técnico; fotos de produto reais e qualidade comercial
exigem uma campanha separada posteriormente.

## Custo e autorização

É uma chamada paga. A documentação oficial consultada informa US$30 por milhão
de tokens de imagem de saída, US$8 por milhão de tokens de imagem de entrada e
US$5 por milhão de tokens de texto de entrada para ambos os modelos 2.5.
O total é a soma desses consumos; não há cache de entrada na chamada direta
`images.edit`. Sem conhecer o consumo efetivo, não prometemos custo fechado por
imagem nem convertemos o valor para reais. Uma imagem em qualidade baixa limita
o escopo, mas não equivale a um teto financeiro. Nenhum crédito foi consumido.

[Preços e cálculo oficiais](https://developers.openai.com/api/docs/guides/image-generation#cost-and-latency)

**Aguardando autorização explícita para esta única imagem.** Só depois:

```powershell
python studio.py --enable-api --settings output/studio-verification/teste-real-proposto/preferences.json
```

Selecionar a planilha proposta, escolher modo direto, adicionar as duas fotos,
conferir a campanha e confirmar Gerar imagens — API paga. A chave permanece no
`.env` do projeto/ambiente existente. Não é necessário alterá-la ou copiá-la à UI.
Não execute esse comando para validar a implementação sem consentimento pago.
