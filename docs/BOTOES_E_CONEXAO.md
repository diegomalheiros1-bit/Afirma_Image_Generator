# Botões e indicador de conexão — versão 1.0.10

## Ações e cores

Os temas claro e escuro usam classes compartilhadas:

| Ação | Apresentação |
| --- | --- |
| Gerar imagens e confirmação paga | Verde sólido e ícone de iniciar |
| Retomar execução/lote | Verde sólido e ícone de continuar |
| Pausar | Âmbar e ícone de pausa |
| Interromper lote | Contorno vermelho e ícone de parar |
| Simular campanha | Contorno roxo |
| Conferir, configurações e abrir resultados | Neutro |

Rótulos, tooltips e foco visível complementam as cores. Pausar e Retomar
compartilham a mesma posição. A largura reservada reduz deslocamentos nas
transições. Em janelas pequenas, as ações se organizam em mais linhas.

## Execução e bloqueios

Durante a execução, o Studio bloqueia novo início real ou simulado e alterações
de planilha, referências, destino, seleção, parâmetros, limites e credenciais.
Também impede aplicar ou salvar preferências. A mensagem visível informa:
“Campanha em execução. As configurações poderão ser alteradas após o encerramento.”

Configurações continuam acessíveis para consulta. Histórico, acompanhamento e
**Abrir pasta de resultados** continuam disponíveis. A abertura usa apenas o
diretório configurado, no Explorador do Windows, e avisa se ele ainda não existe.
No acesso remoto por Wi-Fi, abrir a pasta no computador servidor é bloqueado.

Botões de início usam “Gerando imagens…” ou “Simulando campanha…” conforme o
modo. O frontend bloqueia cliques duplicados, e o backend serializa início e
mutações com o mesmo lock da sessão. As credenciais ficam bloqueadas também
durante a verificação explícita. A liberação de itens em revisão mantém as provas
e confirmações anteriores.

**Pausar** solicita a pausa: “Aguardando pausa…” não significa que a chamada
atual parou. O worker publica “Pausado” somente ao alcançar o checkpoint entre
itens. Só então Retomar aparece habilitado. A solicitação repetida é idempotente.

**Interromper lote** abre confirmação com foco inicial em Continuar lote.
Cancelar ou Escape preserva a execução. Confirmar bloqueia novos itens e mostra
“Interrompendo…”, aguardando o trabalho atual e a persistência final. Não há
promessa de cancelamento remoto; uma chamada já iniciada pode consumir créditos.
Chamadas incertas continuam sob a política existente de `REVISAO`, sem reenvio
automático. O encerramento não é publicado antes da tentativa de persistência.

## Indicador da Home

| Luz e texto | Significado |
| --- | --- |
| Verde — API conectada | A última verificação explícita da chave ativa confirmou autenticação. |
| Vermelho — API desconectada | Nenhuma chave configurada ou última checagem com falha de autenticação, conexão ou timeout. |
| Cinza — API não verificada | Chave configurada sem verificação válida; inclui checagem inconclusiva por limite, permissão ou falha do provedor. |
| Âmbar — Verificando API… | Checagem explícita em andamento. A animação respeita redução de movimento. |

O tooltip, acessível por mouse e teclado, explica o estado e inclui o horário
quando disponível. Clicar abre a seção de conexão sem verificar automaticamente.
Home e Configurações leem o mesmo estado. Não há monitoramento de rede, consulta
periódica de autenticação nem consulta de saldo.

O verde não garante disponibilidade contínua, saldo ou acesso ao modelo.
Trocar/remover chave invalida o resultado anterior; reabrir inicia sem verificação.
Respostas atrasadas não validam a chave substituta. Falhas de disco, parâmetros,
imagem ou quota durante uma geração não substituem o estado da última checagem.
A checagem de modelos distingue autenticação/rede/timeout de permissão, limites
e falhas inconclusivas, sem retornar mensagens brutas ou credenciais.

## Validação local

Os testes automatizados usam clientes simulados, arquivos temporários e rede
externa bloqueada. Exercitam concorrência, bloqueios, leitura durante execução,
abertura de pasta simulada, pausa efetiva, interrupção, classificação de falhas
e preservação do estado de autenticação diante de erros de geração.

O diagnóstico WebView2 usa uma instância isolada, credenciais fictícias e API
real bloqueada. Um worker simulado mantém um item em andamento para verificar
as transições. O modo real aparece apenas como fixture visual, sem chamadas reais.
As capturas `api-home-*.png` e `buttons-*.png` documentam os estados e temas.

Entrega local para revisão, sem push/publicação ou substituição da instalação.
