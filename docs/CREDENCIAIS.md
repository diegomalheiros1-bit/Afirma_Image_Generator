# Configuração da chave — versão 1.0.9

Em **Configurações > Opções avançadas**, a gestão da chave é separada da
verificação de conexão e das preferências gerais.

| Situação | Interface e ação |
| --- | --- |
| Sem chave | “Nenhuma chave configurada”, campo de senha e escolha entre uso na sessão e armazenamento protegido. |
| Chave configurada | Resumo da origem, sem campo ou conteúdo da chave; Trocar chave e Verificar conexão. |
| Troca | Campo vazio com foco; a chave atual permanece ativa. Confirmar escolhe sessão ou armazenamento; cancelar limpa o texto e retorna o foco. |
| Verificação | Não verificada, verificando, autenticação verificada ou falha; a existência da chave não significa autenticação confirmada. |

Prioridade preservada: **sessão > chave salva pelo aplicativo > ambiente/.env**.
Variáveis de ambiente prevalecem sobre `.env`, conforme o comportamento existente.
Abrir a tela não troca credenciais nem verifica conexão. Salvar preferências não
salva a chave. O botão Mostrar revela somente o texto recém-digitado.

**Descartar chave desta sessão** remove apenas a substituição temporária.
**Remover chave salva** remove apenas o arquivo protegido pelo aplicativo.
O resumo informa quando uma credencial de menor prioridade passa a ser usada.
Credenciais externas são gerenciadas fora do Studio; ele não altera `.env` ou
variáveis do sistema. Se uma chave da sessão encobre uma salva, descarte primeiro
a da sessão para gerenciar a salva pela interface.

Falha ao salvar mantém a credencial anterior e sua verificação. O texto digitado
é limpo ao confirmar (inclusive se falhar), cancelar, fechar Opções avançadas,
sair das configurações ou mudar para Sobre. Uma substituição bem-sucedida invalida
a verificação anterior. Respostas atrasadas não podem validar outra credencial.
Durante verificação ou geração, alteração e remoção são bloqueadas também no backend.

**Verificar conexão** é a única ação que solicita a checagem de autenticação.
Solicitações simultâneas são deduplicadas. Falhas de autenticação, rede e timeout
têm mensagens distintas e não apagam a chave. A consulta não gera imagens, não
consulta saldo e não garante acesso à geração. Mensagens brutas do provedor não
são retornadas. O resultado não persiste entre sessões.

O armazenamento mantém DPAPI vinculado ao usuário do Windows, com gravação
atômica. O frontend recebe somente origem/presença e estado da verificação.
Não há recuperação do segredo para preenchimento, cópia ou revelação da chave
salva, nem armazenamento em URLs, localStorage, preferências, planilhas ou logs.

## Validação local

`scripts/run_local_tests.py` bloqueia rede externa e usa clientes simulados.
Testes cobrem prioridade, remoção por origem, falha de armazenamento, reabertura
DPAPI fictícia, ausência de segredos nos estados, erros de conexão, deduplicação,
respostas atrasadas e bloqueio durante operação.

`desktop.py --self-test NOVA_PASTA` usa uma sessão isolada e credenciais fictícias,
descarta variáveis OpenAI herdadas, bloqueia o cliente real e conexões externas.
Verifica campo oculto, foco, cancelamento, limpeza, armazenamento real de um
valor fictício com DPAPI, alternativas após remoção, temas, janela pequena e ampla.
Capturas `credential-*.png` e `diagnostics.json` ficam na pasta isolada.
O build executa o mesmo diagnóstico no executável antes de criar o ZIP.

Esta entrega é local para revisão: sem push/publicação, troca da instalação ou
chamadas reais de autenticação e geração.
