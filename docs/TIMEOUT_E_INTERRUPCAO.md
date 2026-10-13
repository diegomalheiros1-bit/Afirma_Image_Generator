# Diagnóstico, timeout e interrupção — versão 1.0.3

## Evidências da execução de 13/10/2026

A leitura do histórico existente confirmou dez itens planejados, três
processados, zero sucessos e três erros. Os itens 1, 2 e 3 ficaram em `REVISAO`,
com durações de 120,440, 120,303 e 120,238 segundos. A configuração informada
foi Sunburst, qualidade `max`, tamanho/fundo automáticos, PNG, timeout de 120
segundos e duas repetições. Esses registros não armazenavam o tipo original da
exceção nem a contagem de chamadas nos eventos do Studio.
O arquivo de estado confirma uma chamada por item, com fase `uncertain` para
os três itens. Duas repetições configuradas não significam que elas ocorreram.

A proximidade de 120 segundos sustenta a hipótese de timeout, mas não comprova
o motivo das falhas, a lentidão do serviço ou uma relação causal com a qualidade.
O piloto anterior com qualidade `low` e outros parâmetros não é uma comparação
controlada. Os históricos anteriores permanecem intactos; o software não atribui
retroativamente uma classificação de timeout a eles.

## Diagnóstico seguro

O gerador usa os tipos reais do SDK OpenAI instalado, incluindo a distinção
entre `APITimeoutError`, `APIConnectionError` e `APIStatusError`. A documentação
oficial descreve essa hierarquia e a propriedade `request_id` para erros HTTP:
[biblioteca Python](https://developers.openai.com/api/reference/python).

Os novos registros incluem, quando disponíveis e permitidos:

- Categoria e tipo da exceção.
- Status HTTP, código conhecido da API e identificador de requisição validado.
- Número de chamadas, duração e timeout configurado.
- Motivo de interrupção e contagens de itens planejados, iniciados, concluídos,
  em revisão e aguardando início.

As contagens são do lote selecionado. Itens aguardando início não incluem as
linhas que ficaram fora dos limites dessa execução. O campo antigo `ignored`
continua representando todas as linhas não processadas, para compatibilidade.

As categorias distinguem timeout, conexão, autenticação, permissão, parâmetros,
limite/quota, servidor, outros erros HTTP, resposta de imagem inválida,
armazenamento, validação local e erro inesperado. Mensagens são produzidas pelo
aplicativo em português. Corpos, cabeçalhos completos, mensagens brutas,
credenciais e cadeia de exceções não são registrados. Códigos e tipos usam
listas permitidas; identificadores e números são validados.

Os campos `error` do estado, `diagnostic` dos eventos e `counts` do histórico
são adicionais. A versão de histórico continua em 1 e os novos campos são
opcionais; a interface calcula contagens disponíveis ao ler um histórico antigo.
Dados ausentes, como o tipo da antiga exceção, não são inventados.

## Política de repetição e interrupção

Timeout, conexão, HTTP 408, falhas de servidor sem rejeição segura, resposta
inválida, falha de armazenamento após resposta e erros inesperados preservam
o processamento como incerto. O item fica em `REVISAO`; o lote para antes do
próximo item, com motivo explícito. Nenhuma dessas chamadas é repetida
automaticamente. Os itens não iniciados continuam `PENDENTE` e as saídas
existentes são preservadas.

As repetições anteriores continuam restritas a HTTP 429 com código
`rate_limit_exceeded`/`slow_down` e HTTP 503 com `server_is_overloaded`, dentro
do orçamento configurado e quando a espera indicada não ultrapassa 60 segundos.
Quota, autenticação, permissão e parâmetros não são repetidos automaticamente.
Erros confirmadamente rejeitados mantêm o comportamento anterior de `ERRO` e
podem permitir o processamento dos próximos itens. A política não foi ampliada.

O SDK é criado com `max_retries=0`, para evitar repetições ocultas além da
política do aplicativo. Pedir interrupção também impede uma nova tentativa
durante o intervalo de um retry seguro. Um item em `REVISAO` não é reenviado
automaticamente na próxima execução; recuperação, fingerprints e proteção
contra sobrescrita mantêm os critérios existentes.

Se falhar a gravação do próprio estado ou da planilha, o processamento ainda
para com `PersistenceError`. O encerramento não elimina nem reinicia o histórico.
Gravações atômicas evitam substituir o arquivo válido por um arquivo parcial;
falhas reais de disco/permissão exigem conferência dos registros preservados.

## Orientação e encerramento

Qualidade `max` com timeout de até 120 segundos mostra um aviso em Opções
avançadas e na confirmação da geração. O aviso recomenda considerar 600 segundos
como margem inicial de teste. Ele não bloqueia o botão, não é uma exigência
oficial da OpenAI e não garante conclusão. Qualidade e dimensões podem influenciar
a duração; ver [guia oficial de imagens](https://developers.openai.com/api/docs/guides/image-generation).

Timeout, qualidade, dimensões, modelo e outras preferências não são alterados
silenciosamente. O usuário pode mudar o valor no campo de timeout e aplicar ou
salvar. O timeout é uma configuração do cliente HTTP, não uma garantia de prazo
de geração do serviço.

**Interromper lote** impede os próximos itens. A chamada atual pode continuar
até retornar ou atingir o timeout; encerramento local não confirma cancelamento
remoto. Durante a espera, o aplicativo permanece ativo e mostra **Interrupção
solicitada — aguardando o item atual**. Pausar, retomar e repetir a solicitação
ficam indisponíveis após o pedido de interrupção.

Fechar a janela durante uma campanha explica essa limitação e pede confirmação.
Quando autorizado, o aplicativo aguarda o worker e suas gravações antes de fechar.
O estado final só é publicado após a última tentativa de persistência. A
validação usa uma instância isolada e não fecha a instância do usuário.

## Validação e limites das conclusões

Os testes usam arquivos temporários, exceções reais do SDK e clientes falsos.
Cobrem timeout/conexão distintos, primeira falha incerta, nenhuma repetição
automática, retomada sem reenviar revisão, HTTP e retries permitidos, saída
parcial, carregamento antigo, preferências mantidas e interrupção/fechamento
durante chamada bloqueada.

O diagnóstico do próprio executável verifica temas, tamanhos, zoom, aviso não
bloqueante, alteração manual do timeout e contagens na interface. Em uma fila
isolada de dez itens, o SDK é substituído por um cliente local que lança timeout:
uma chamada fictícia, um item em revisão e nove aguardando, sem transporte de rede.

Isso valida o tratamento de falhas e a preservação de estados, não a latência,
o saldo, a qualidade das imagens ou o acesso real ao modelo. Confirmar a causa
da execução anterior e a adequação do timeout exige um teste real posterior
explicitamente autorizado. Não há novas chamadas pagas nesta revisão.
