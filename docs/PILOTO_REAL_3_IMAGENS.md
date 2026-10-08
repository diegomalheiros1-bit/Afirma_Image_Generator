# Primeiro piloto — 3 imagens

Este roteiro registra a preparação técnica inicial. O piloto posterior com a
planilha real foi concluído em 08/10/2026; veja o histórico no Studio e
`output/piloto-real-tabela-2026-10-08/LOG_DETALHADO.md` na máquina local.

Preparado em 08/10/2026. DRY RUN aprovado: 3 itens, 3 sucessos, zero erros.
Nenhuma geração paga executada na preparação.

- Campanha: `output/piloto-real-3-imagens/campanha-3-imagens.xlsx`.
- Três linhas, quantidade 1 por linha; até três chamadas sequenciais.
- Sunburst, qualidade low, 1024×1024, PNG opaco, timeout de 120 segundos.
- Zero retries. Limites de jobs, imagens e planilha iguais a 3.
- Modo seguro de uma imagem desativado nesta campanha para permitir o limite
  solicitado de três imagens. A trava de API da sessão continua independente.
- Duas referências fictícias copiadas para a pasta isolada `referencias`.
- Três variações: frontal, perspectiva e vista de cima. Este é um teste técnico;
  fidelidade de produto com fotos reais exige outro piloto.
- Saídas novas: `saida/piloto_3_001.png` até `saida/piloto_3_003.png`.
- Backup inicial: `campanha-3-imagens.original.xlsx`.
- Plano, parâmetros, resumo e hash inicial: `preflight.json`.

Para abrir a campanha já selecionada, com botão pago habilitado:

```powershell
python scripts/real_pilot.py --serve --enable-api
```

Abrir o endereço local impresso. Conferir campanha e confirmar **Gerar imagens
— API paga** somente quando quiser iniciar as chamadas e autorizar o gasto.
Iniciar o servidor ou conferir a campanha não gera imagens. A chave é lida do
ambiente/`.env` existente; não é copiada para a campanha ou preferências.

A planilha permanece com `Dry_Run=SIM` para prevenir execução paga acidental
pelo CLI; o botão real do Studio define o modo efetivo após confirmação.
O limite de três imagens não é um teto monetário. Acesso, saldo, latência,
qualidade e consumo serão confirmados somente pela execução real.

Após gerar, conferir os três PNGs, os estados CONCLUIDO e o journal ao lado do
Excel. Em timeout ou REVISAO, preservar o histórico e não forçar PENDENTE.
Falha após resposta e gravação interrompe novas chamadas; rejeições da API
podem aparecer como ERRO. Não repetir a campanha sem conferir esses estados.

O script de preparação recusa sobrescrever a pasta do piloto. Para reabrir,
usar `--serve`; para abrir sem habilitar API, omitir `--enable-api`. Não abrir
duas sessões para o mesmo piloto. Mantenha o processo ativo até encerrar o lote.
