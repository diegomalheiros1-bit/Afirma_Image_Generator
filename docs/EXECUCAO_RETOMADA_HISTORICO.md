# Execução, retomada e histórico — versão 1.0.8

## Selecionar o que executar

Na campanha, use **O que deseja executar?** e **Conferir seleção**. A prévia
mostra IDs selecionados e excluídos com seus motivos. Os limites de itens e de
imagens são independentes; um item com várias imagens é selecionado inteiro.

- **Gerar pendentes:** itens sem evidência de chamada incerta. Registros
  preparados antes de iniciar uma chamada também podem ser retomados.
- **Repetir erros:** rejeições locais cuja validação
  agora passa; rejeições transitórias confirmadas de limite de taxa/sobrecarga;
  erros de parâmetros após alteração das configurações e validação local.
- **Repetir itens em revisão:** seleciona exclusivamente revisões liberadas
  explicitamente, sem incluir pendentes comuns ou outros erros. Primeiro clique
  **Revisar e liberar itens**, confira as evidências e confirme **Liberar nova
  tentativa** para cada item desejado. Sem liberação, a seleção fica vazia.

No **Histórico de execuções**, escolha uma execução e clique em **Retomar lote**.
  Essa ação usa apenas os IDs da seleção original e prepara um painel de retomada.
  Não inicia geração. Clique **Escolher outra ação** para sair desse contexto. Um lote de 10 com 6 concluídos, 1 em revisão
  e 3 não iniciados oferece somente esses 3. Não completa o limite com itens
  externos. A retomada gera outro registro ligado ao anterior.

Falhas de autenticação, permissão e saldo não são declaradas corrigidas por
alteração do texto do status. A aplicação não consegue comprovar localmente
mudanças externas de saldo/permissão. Essas rejeições permanecem excluídas;
não há teste pago nem reenvio automático para descobrir se a causa desapareceu.
Uma mudança apenas no nome do arquivo não libera erro de parâmetros.

Históricos antigos sem IDs não permitem reconstruir a composição do lote.
Informe os IDs explicitamente no campo correspondente. A seleção antiga não
é inferida pela ordem atual das linhas nem pela quantidade planejada.
Sem itens elegíveis, iniciar é bloqueado antes de qualquer cliente de geração.
Simular preserva os estados e imagens; portanto, pode simular os mesmos IDs
novamente. Sucesso simulado não significa imagem realmente produzida.

## Ajuda dos botões

Os botões de campanha, prévia, revisão, controle da execução e confirmação
mostram ajuda ao passar o mouse ou receber foco pelo teclado. O botão
**Retomar lote** no histórico também tem ajuda, explicando o escopo original.
As ajudas deixam explícito quais ações apenas conferem ou simulam e qual
confirmação inicia a geração paga. Escape oculta a ajuda; as confirmações
continuam com Cancelar como foco inicial.

Na versão 1.0.7, as três ações do seletor são separadas: revisões liberadas
não entram em Gerar pendentes nem Repetir erros. A retomada pode combinar
pendentes e revisões liberadas, sempre dentro dos IDs do lote original. O
modo combinado antigo permanece apenas para compatibilidade interna e não
aparece no seletor. Os registros históricos existentes são preservados.

## Revisar resultados incertos

Em **Itens em revisão**, clique **Conferir evidências**. São exibidos diagnóstico
seguro, requisição quando disponível, data/duração registradas, chamadas,
saídas existentes e o resultado da verificação de correspondência.

**Recuperar saída comprovada** exige registro `files_ready`, hashes válidos,
formato correto, assinatura da linha e identidade efetiva de configurações,
referências/caminhos/hashes e saídas. A ação é confirmada, revalida as evidências
sob o lock da planilha e não chama a API. Uma imagem existente sem essa prova
permanece em revisão. Restaure as referências/configurações originais quando
houver divergência; não apague histórico para forçar recuperação.

**Liberar nova tentativa** exige assinatura versão 2 e identidade efetiva
correspondentes, além da ausência de todas as saídas locais. A confirmação
avisa que a chamada remota anterior pode ter sido processada e que reenviar
pode gerar outra cobrança. A liberação registra a decisão e a evidência da
tentativa anterior em `review_actions`, com fase `retry_authorized`. Só então
o status passa a pendente. Não inicia geração. Uma mudança posterior na
identidade invalida a liberação. Sem evidência suficiente, o botão fica inativo.

Na versão 1.0.5, o item liberado permanece visível na seção de revisão, com
indicador **Liberado para nova tentativa** e botão **Já liberado para nova
tentativa**. Uma mensagem confirma o ID e informa que a geração não começou.
O combo muda automaticamente para **Repetir itens em revisão** e a prévia
mostra os IDs selecionados. Depois confira a seleção e use a confirmação do
botão de geração. Somente a confirmação da liberação não gera imagens.

Na versão 1.0.6, a seleção reconhece uma liberação persistida mesmo que o status
da planilha ainda seja `REVISAO`. A assinatura da linha/configuração/referências
e a ausência de saídas continuam obrigatórias. A seleção e a simulação não
alteram esses estados. Não é necessário editar o status manualmente.
O modal mostra os IDs efetivos após aplicar os limites. Seleção vazia por
falta de liberação ou divergência não é mais apresentada como falta de limite.

## Histórico desta planilha

O seletor **Histórico de execuções** consulta os registros originais:

- `<planilha>.studio-runs/<run_id>.json`: arquivo de cada execução;
- `<planilha>.studio-run.json`: ponteiro materializado para a última execução;
- `<planilha>.state.json`: evidência dos trabalhos, hashes e decisões de revisão.

Não há um banco paralelo nem índice global. Registros são deduplicados pelo
ID. Feche/reabra, selecione a mesma planilha e consulte execuções anteriores.
Se mover a planilha, preserve seus arquivos e diretório de histórico ao lado.
Arquivos inválidos são sinalizados individualmente; os demais continuam
acessíveis. Campos antigos ausentes permanecem desconhecidos.

Cada novo registro inclui seleção original e efetiva, vínculo de retomada,
parâmetros, eventos por item, saídas, contagens, duração total e média dos itens
concluídos/simulados. A interface usa o fuso local do computador. Os resumos
separam fora da seleção, aguardando limite, concluídos preservados, erros
excluídos, revisão e itens selecionados não iniciados após interrupção.

As durações continuam persistidas em segundos. Uma única função da interface
arredonda ao segundo mais próximo antes de separar horas/minutos/segundos:
59,5 s vira `1 min`; 3.920 s vira `1 h 5 min 20 s`. Ausente/inválido aparece
como `—`. O timeout continua sendo digitado em segundos e mostra sua equivalência.
A média não representa previsão garantida nem cobrança confirmada.

Durante a interrupção, não são iniciados novos itens. Uma chamada já iniciada
pode retornar ou atingir o timeout; a aplicação aguarda e salva seu resultado.
Não existe confirmação de cancelamento remoto.

## Linha do tempo em lotes grandes

Na versão 1.0.8, a tabela tem rolagem interna e cabeçalho fixo. Em duas colunas,
o quadro direito acompanha a altura do quadro de preparação; a tabela ocupa
o espaço restante sem ampliar a página a cada evento. Em uma coluna, sua
altura permanece limitada. Há rolagem horizontal quando as colunas não cabem.
O contêiner tem foco por teclado e identificação para leitores de tela.
O diagnóstico usa 53 itens fictícios com 106 eventos e confere o último item,
o alinhamento dos painéis, o cabeçalho e o ajuste após redimensionamento.

## Validação local e limites desta entrega

Os testes usam fixtures temporárias, clientes simulados e construtores OpenAI
bloqueados. A suíte de entrega também nega conexões externas; HTTP local é
permitido apenas para testar o servidor. O diagnóstico Windows mantém
`allow_api=False` e usa simulação; o fluxo visual pago é interceptado na própria
interface, sem chegar ao backend. Nenhuma chave real é lida ou validada.

Há testes de seleção, quantidades/limites, exclusões, lote original, legado sem
IDs, liberação/recuperação com provas, divergências, reabertura, arquivos inválidos,
vínculos, interrupção e persistência. A janela WebView2 é verificada em tamanhos
pequenos/ampliados, temas, zoom, histórico, revisão e estados vazios.

Resultado da suíte: **161 testes, zero falhas e zero erros**, com negação de
conexões externas. Reproduza com `python scripts/run_local_tests.py`.

O pacote é local, separado da instalação atual. Não houve alteração da campanha,
chave ou sessão do usuário, push ou publicação. Custo, latência e qualidade do
serviço real permanecem pendentes de nova autorização explícita para teste pago.
