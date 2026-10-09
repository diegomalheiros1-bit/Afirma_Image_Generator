# Afirma Image Generator

Aplicativo Python para Windows para gerar imagens a partir de Excel, combinando prompt padrão,
variação e referências de modelo/produto. Processamento sequencial e local.
Agora inclui a interface funcional **Afirma Image Studio**: execute `python studio.py`.
Consulte [o guia do Studio](docs/STUDIO.md) para os dois modos de referências,
cadastro de pastas, configurações, simulação e retomada. A API real fica bloqueada
por padrão na interface; habilitação somente após autorização explícita.
O script depende de um processo ativo: fechar o terminal, desligar o computador
ou interromper o Python interrompe o lote. Não há serviço em segundo plano.

## Pacote Windows para teste do cliente

Um pacote portátil com `Afirma-Image-Studio.exe` pode ser gerado no Windows com
`python scripts/build_windows_package.py`. O ZIP, o SHA-256 e a pasta extraída
ficam em `output/releases/<data-hora>/`; não são enviados ao GitHub. O cliente
deve extrair o ZIP completo e abrir `Iniciar Afirma Studio.cmd`. O iniciador
habilita o botão de API real somente no computador local; cada execução paga
ainda exige confirmação na interface. Abrir o `.exe` diretamente mantém a API
bloqueada. A chave pode ser informada em **Configurações > Opções avançadas**;
o pacote não contém `.env`, chaves, planilhas ou imagens do piloto. Veja também
o `LEIA-ME.txt` incluído no ZIP. É um pacote portátil, ainda sem instalador ou
assinatura digital.

## Começar pelo Studio

Com as dependências instaladas, execute na pasta do projeto:

```powershell
python studio.py
```

O programa abre a interface no navegador em `http://127.0.0.1:<porta>/`.
Mantenha o terminal aberto. A API paga permanece bloqueada por padrão.

1. Selecione a planilha da campanha com os prompts e nomes de saída.
2. Escolha como informar as referências: por linha da planilha ou fotos comuns
   selecionadas no software.
3. Confira as pastas de referências, a pasta de saída e o resumo da fila.
4. Abra Configurações, ajuste os parâmetros e limites; os ícones `?` explicam
   cada campo principal. Em Opções avançadas, informe a chave se necessário.
5. Use **Conferir campanha** e faça uma simulação antes de uma execução real.

| Modo | Referências utilizadas |
| --- | --- |
| Pela planilha | Cada item usa exclusivamente `Arquivo_Referencia` da sua linha, com arquivos separados por `;` e aliases opcionais |
| Selecionar no software | Até 16 fotos adicionadas cumulativamente de pastas diferentes, com miniaturas e remoção individual; a seleção vale para todos os itens |

No modo direto, `Arquivo_Referencia` é ignorado e pode estar vazio ou ausente;
`Pasta_Referencias` também pode estar vazia ou ausente. A planilha continua
necessária para os demais dados. Não há fallback automático entre os modos.
Ao voltar ao modo planilha sem configuração legada, escolha uma pasta padrão.

Ao selecionar a planilha, o Studio resume itens com prompt, itens e imagens
pendentes, imagens concluídas e o tamanho da próxima execução. O painel de
progresso conta somente a sessão ativa; **Última execução desta planilha** exibe
o histórico anterior, com horários, duração, estado por item, detalhes da
chamada e custo estimado quando houver dados de uso. A estimativa não confirma
o valor faturado pela API. O lote respeita os limites
de jobs e imagens configurados, incluindo `Limite_Por_Execucao`; itens que excedem
a capacidade ficam pendentes para execuções futuras. Quantidades inválidas são
indicadas e não entram na estimativa.

O cadastro de pastas usa seletores nativos do Windows. A gravação de
`Pastas_Referencias` na planilha é uma ação explícita na interface. Fotos e cadastro
da sessão não são persistidos pelo botão de salvar preferências; consulte o guia
para reabrir a campanha. Durante execução ou pausa, alterações ficam bloqueadas.

## Acesso pelo celular no mesmo Wi-Fi

O acesso padrão continua restrito ao computador. Para habilitar a rede local,
consulte o IPv4 do Windows (`ipconfig`) e execute, substituindo o IP do exemplo:

```powershell
python studio.py --host 192.168.15.73 --port 55635 --no-browser
```

Abra no celular o **link completo exibido no terminal**, incluindo o parâmetro
de acesso. O computador pode estar conectado ao roteador por cabo e o celular
por Wi-Fi, desde que estejam na mesma rede e sem isolamento entre aparelhos.

- O link concede acesso à sessão: compartilhe somente com pessoas autorizadas.
- Uma chave nova é criada a cada inicialização; links anteriores deixam de funcionar.
- Após abrir o link, o navegador recebe um cookie de sessão e é redirecionado para a página sem a chave na URL.
- Acesso pela rede é via HTTP: use somente uma rede de confiança. Não configure encaminhamento de portas nem exponha à internet.
- Somente IPv4 privado específico é aceito; endereços públicos e `0.0.0.0` são rejeitados.
- A API paga fica obrigatoriamente bloqueada neste modo, inclusive se `--enable-api` for informado.
- Mantenha o computador e o processo ligados. Para desligar o acesso, encerre o processo com Ctrl+C.
- Os seletores de arquivos e pastas abrem no Windows; não há envio de fotos do celular.
- Tema é uma preferência de cada navegador/endereço. As opções da campanha são compartilhadas entre os aparelhos que acessam a mesma sessão.

Se a conexão falhar, confira o IP, a rede e o Firewall. Quando necessária, a
liberação deve ficar restrita ao programa, porta, IP local e sub-rede usados.
O aplicativo não altera o Firewall automaticamente. Nesta validação, o usuário
confirmou a abertura pelo celular sem ser necessário adicionar a regra tentada.

## Aparência e navegação

Os botões Configurações e Tema ficam abaixo do cabeçalho. O tema claro/escuro
é salvo no navegador para o mesmo endereço local; ao iniciar em outra porta,
a preferência do sistema é usada até uma nova escolha. Para reutilizar o endereço,
abra o Studio com uma porta disponível fixa: `python studio.py --port 55634`.
O layout se adapta a telas menores e oferece foco visível para navegação por teclado.
Os campos de planilha e pasta de saída têm ícone e seta de seleção. As etapas
**Prepare sua campanha** e **Acompanhe sua campanha** organizam a tela; os
botões `?` mostram ajuda ao clicar, passar o ponteiro ou usar o teclado.

## Configurações na interface

- Modelos: GPT Image 2.5 Sunburst e Flare.
- Formato: PNG, JPEG ou WebP; `Nome_Saida` precisa usar a extensão correspondente.
- Fundo: automático, opaco ou transparente; JPEG não aceita transparência.
- Qualidade: automática, baixa, média, alta, muito alta ou máxima.
- Resolução: automática, três tamanhos predefinidos ou dimensões personalizadas validadas.
- Compressão: opcional, de 0 a 100%, somente para JPEG/WebP, separada da qualidade de geração.
- Pasta de saída, timeout, novas tentativas, limites de jobs/imagens e modo seguro.
- Em **Opções avançadas**, chave da API para esta sessão ou salva protegida no
  usuário atual do Windows; o campo não mostra uma chave armazenada ao reabrir.

Preferências podem ser aplicadas à sessão ou salvas em `.studio-settings.json`,
sem credenciais. Os padrões vêm do ambiente sobre o `.env`; preferências salvas
e alterações aplicadas no Studio prevalecem sobre esses padrões. A pasta de saída
da planilha é usada quando não houver substituição no Studio. A opção de simular
ou gerar no Studio define o modo efetivo, independentemente de `Dry_Run` do Excel.

## Estado da validação

Consulte a [revisão pré-piloto de 08/10/2026](docs/REVISAO_2026-10-08.md)
para as correções e critérios usados antes da execução real.

Revisão de 08/10/2026: **102 testes automatizados passaram** com clientes falsos
e arquivos temporários. Incluem a leitura do resumo da planilha sem escrita,
o cálculo dos limites da próxima execução e as correções de retomada de trabalhos
`prepared` e de seleção direta sem `Pasta_Referencias`.
O relatório da implementação registra 12/12 itens simulados com pausa e retomada.
Os seletores nativos possuem testes de contrato; o fluxo de navegador registrado
usou seleção fictícia pré-carregada. Em 08/10/2026, um piloto autorizado com a
planilha real concluiu **3 imagens em 3 itens**. A retomada registrada durou
56,217 s e estimou US$ 0,060884 em uso da API; esse número não é a cobrança
confirmada. Planilha, referências, imagens e log detalhado permanecem somente
na máquina local, fora do Git. O Studio mostra o histórico da planilha selecionada.

Guias: [uso do Studio](docs/STUDIO.md), [relatório de entrega](docs/ENTREGA_STUDIO.md),
[revisão pré-piloto](docs/REVISAO_2026-10-08.md) e
[roteiro inicial de três imagens](docs/PILOTO_REAL_3_IMAGENS.md).

## Instalação

Requer Python 3.11 ou superior. Na raiz do projeto, em PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Se ainda não houver `.env`, copie `.env.example` para `.env`.
Para o CLI, preencha `OPENAI_API_KEY` no `.env` ou na variável de ambiente.
No Studio, **Configurações > Opções avançadas** também permite informar a chave
somente para a sessão ou salvá-la protegida para o usuário atual do Windows.
Nunca coloque a chave no Excel, no código, nos logs ou em commits.
No Studio, a chave informada na interface tem precedência sobre o ambiente e o
`.env`. No CLI, o ambiente tem precedência sobre o `.env`; `DRY_RUN` tem precedência sobre
`Dry_Run` da aba `Configuracao`. Feche o Excel antes de executar o programa.

## Planilha e referências

A aba `Fila_Geracao` requer `ID`, `Prompt_Padrao`, `Prompt_Variacao`,
`Nome_Saida`, `Status`, `Tentativas` e `Observacao`. `Arquivo_Referencia` é
obrigatória somente no modo de referências pela planilha.
IDs devem ser únicos, preenchidos e estáveis. Não altere IDs para contornar
uma tarefa bloqueada: eles ligam a linha ao histórico da geração.

Colunas opcionais: `Tema`, `Produto`, `Cliente`, `Prompt_Negativo`, `Quantidade`
e `Observacao_Usuario`. Quantidade ausente/vazia significa 1; deve ser inteira
positiva. Na OpenAI, use de 1 a 10 por job.

`Arquivo_Referencia` aceita `modelo.jpg;produto.png`, preservando a ordem.
No modo planilha, as referências devem existir sob a pasta padrão ou a pasta
identificada pelo alias. No modo direto, valem os arquivos escolhidos na interface. PNG, JPEG/JPG e
WEBP são aceitos. Antes da chamada real, o conteúdo também é validado como
imagem; OpenAI aceita até 16 referências, cada uma menor que 50 MB.

`Nome_Saida` deve ser um nome de arquivo, sem subpastas. Na OpenAI, use a extensão
do formato selecionado: `.png` (padrão antigo), `.jpg`/`.jpeg` ou `.webp`.
Para quantidade 1, `imagem_001.png` é preservado; para 3, as saídas são
`imagem_001_01.png`, `imagem_001_02.png` e `imagem_001_03.png`.
Arquivos existentes nunca são sobrescritos. Os arquivos reais ficam em
`Pasta_Resultados`, inclusive com o provider OpenAI.

Antes da primeira chamada real do lote, o programa cria `Pasta_Resultados` se
necessário, confirma que o caminho é um diretório e faz uma escrita exclusiva
com arquivo temporário, incluindo flush no armazenamento. O teste remove apenas
o arquivo que ele próprio criou. Caminho ocupado por arquivo, falta de permissão
ou falha de armazenamento encerra a execução com todas as linhas ainda
PENDENTE. Essa verificação é somente uma sondagem inicial: disco, permissão e
sincronização ainda podem falhar após a API responder.

A aba `Configuracao` usa as colunas `Parametro` e `Valor`:

| Parâmetro | Significado |
| --- | --- |
| Pasta_Referencias | Pasta padrão no modo planilha, relativa à pasta do Excel; dispensada no modo direto |
| Pasta_Resultados | Relativa a `output/` na pasta pai de `input/`, por exemplo `imagens` |
| Limite_Por_Execucao | Máximo de jobs por execução, inteiro positivo |
| Dry_Run | SIM/NAO; padrão SIM, usado se DRY_RUN não estiver definido |

Caminhos absolutos também são aceitos. `Modelo_API`, `Qualidade` e
`Prompt_Sistema` legados na planilha não são usados: modelo e qualidade vêm
das variáveis abaixo no CLI e das preferências aplicadas no Studio. `Observacao` é controle do programa;
`Observacao_Usuario` contém a orientação do usuário.

## Prompt enviado

O texto contém `Prompt_Padrao`, uma linha em branco e `Prompt_Variacao`.
Quando preenchidos, acrescenta blocos identificados: `Tema:`, `Produto:`,
`Observação do usuário:` e `Evitar:` (Prompt_Negativo). O campo Cliente fica
como metadado e não é enviado. O DRY RUN mostra exatamente esse texto.

## Configuração e limites

| Variável | Padrão no código | Uso |
| --- | --- | --- |
| IMAGE_PROVIDER | simulation | simulation, mock ou openai |
| DRY_RUN | Valor do Excel | SIM impede API, arquivos de saída e escrita na planilha |
| FIRST_RUN_SAFE_MODE | SIM | Exige os três limites de execução <= 1 para geração real |
| MAX_JOBS_PER_RUN | 1 | Máximo de jobs selecionados |
| MAX_IMAGES_PER_RUN | 1 | Soma máxima das quantidades selecionadas |
| OPENAI_API_KEY | Sem padrão | Necessária somente para chamada real |
| OPENAI_IMAGE_MODEL | gpt-image-2.5-sunburst | gpt-image-2.5-sunburst ou gpt-image-2.5-flare |
| OPENAI_IMAGE_QUALITY | auto | auto, low, medium, high, xhigh, max |
| OPENAI_IMAGE_FORMAT | png | png, jpeg, webp; nome de saída deve corresponder |
| OPENAI_IMAGE_BACKGROUND | auto | auto, opaque, transparent; JPEG não aceita transparência |
| OPENAI_IMAGE_SIZE | auto | auto ou largura x altura, como 1536x1024; limites no guia do Studio |
| OPENAI_IMAGE_COMPRESSION | Ausente | Percentual inteiro 0–100 somente JPEG/WebP; omitir para PNG |
| OPENAI_TIMEOUT_SECONDS | 120 | Timeout positivo por chamada |
| OPENAI_RETRIES | 2 | Novas tentativas, de 0 a 5; além da chamada inicial |

O limite de jobs é o menor entre MAX_JOBS_PER_RUN e Limite_Por_Execucao.
Uma linha que não cabe no saldo de imagens é ignorada com motivo no console;
linhas posteriores menores ainda podem ser selecionadas. Linhas excedentes
permanecem PENDENTE. Retries não aumentam o número de imagens planejadas,
mas aumentam o contador de chamadas à API.

FIRST_RUN_SAFE_MODE é uma trava explícita, não um detector automático de
primeira execução. Para liberar lotes, configure `FIRST_RUN_SAFE_MODE=NAO`.
O programa imprime provider, jobs encontrados, imagens previstas e limites.

## Simulação e mock

```powershell
python main.py
python main.py --mock
```

`simulation` valida sem gerar arquivos. `mock` cria arquivos fictícios em
`Pasta_Resultados/_mock/<execucao>/`, sem conflitar com futuras imagens reais.
Ambos preservam a planilha, inclusive PENDENTE e Tentativas, mesmo em falhas.
`--mock` seleciona o mock, mas não desativa DRY_RUN.
Sucesso no resumo desses modos significa validação/simulação bem-sucedida,
não uma imagem gerada. DRY RUN não altera o Excel nem o registro de execução;
o arquivo de lock local e o log podem ser criados.

## Nova execução real

O roteiro abaixo é para novas execuções pelo CLI. Revise a simulação, os
limites e o gasto antes de habilitar chamadas pagas. Para usar o Studio, consulte
o [guia da interface](docs/STUDIO.md).

### Validar primeiro uma imagem real

1. Coloque uma referência válida em `input/referencias/produto.png`.
2. Na planilha, preencha uma linha com ID único, prompt, referência
   `produto.png`, saída nova `teste_001.png`, Status=PENDENTE, Tentativas=0
   e Quantidade=1 (ou deixe a coluna ausente). Defina Limite_Por_Execucao=1
   e confira Pasta_Resultados (por exemplo, `imagens`).
3. No `.env`, configure IMAGE_PROVIDER=openai, DRY_RUN=SIM,
   FIRST_RUN_SAFE_MODE=SIM, MAX_JOBS_PER_RUN=1 e MAX_IMAGES_PER_RUN=1.
4. Execute `python main.py` e confira o prompt completo e caminhos.
5. Configure a chave e verifique saldo/acesso da conta. Mude apenas
   DRY_RUN=NAO e execute `python main.py`. Essa etapa faz uma chamada paga.
6. Confira a imagem na pasta configurada e o status CONCLUIDO. Em caso de
   falha, use a orientação de recuperação antes de repetir.

## Validar um lote pequeno

Após verificar visualmente a primeira imagem, crie duas linhas novas, com
IDs e saídas distintos, Quantidade=1 e Status=PENDENTE. Configure
FIRST_RUN_SAFE_MODE=NAO, MAX_JOBS_PER_RUN=2, MAX_IMAGES_PER_RUN=2 e
Limite_Por_Execucao=2. Execute com DRY_RUN=SIM. Depois de conferir o plano,
mude para DRY_RUN=NAO e execute novamente. Mantenha o terminal ativo.

## Persistência e recuperação

Além do Excel, cada fila tem um arquivo `fila.xlsx.state.json` junto dela.
Ele guarda ID, fase, tentativas da tarefa e da API, caminhos e hashes das
entradas/saídas, além do modelo, qualidade, pasta histórica e assinatura dos
campos editáveis da linha. Não armazena prompts em texto, binários ou
credenciais. Modelo, qualidade e pasta registrados pertencem à geração já
executada; alterar a configuração global afeta somente tarefas novas. Preserve esse
arquivo junto da planilha em backups; perdê-lo remove evidências necessárias
para uma recuperação segura. O arquivo `fila.xlsx.lock` usa trava do sistema
operacional; duas instâncias não podem executar a mesma fila simultaneamente.
A trava é liberada ao encerrar o processo, inclusive por falha. Não apague o
arquivo de lock enquanto houver processos ativos. Use disco local; travas de
pastas de rede/sincronização não são garantidas por este MVP.

O programa grava `prepared`, salva PROCESSANDO no Excel e somente então pode
chamar a API. Antes de cada chamada, grava `in_flight`. Após salvar e validar
todas as imagens no formato escolhido, grava `files_ready` com hashes e só então grava CONCLUIDO.
Falha no Excel ou no registro interrompe novas gerações. Não existe um save
incondicional no finally que possa ocultar o erro original.

Antes de qualquer nova chamada, a recuperação examina o histórico e agrupa as
mudanças necessárias no Excel em uma única gravação. Fila concluída e íntegra
não reescreve Excel nem observações. Se essa única gravação falhar, nenhuma nova
chamada é iniciada. As gravações críticas de PROCESSANDO e CONCLUIDO continuam
individuais durante uma geração real.

Se a API responder mas a gravação de uma imagem falhar, o lote para: nenhuma
tarefa seguinte é enviada naquela execução. Arquivos completos ou parciais são
preservados, a tarefa fica em REVISAO quando o estado puder ser salvo e as
demais ficam PENDENTE. Na execução seguinte, a tarefa afetada não é reenviada;
outras tarefas pendentes podem prosseguir depois que o armazenamento estiver
estável. Não trate a sondagem inicial como garantia de escrita futura.

| Situação | Recuperação |
| --- | --- |
| Excel aberto, permissão ou disco cheio | Feche o Excel, corrija o acesso/espaço, preserve arquivos e registro e execute novamente |
| Registro prepared | Nenhuma chamada começou; retorna automaticamente a PENDENTE |
| Registro files_ready, assinatura compatível e arquivos/hashes conferem | Recupera CONCLUIDO sem API, mesmo se o Excel ficou PROCESSANDO |
| Registro files_ready sem assinatura da linha | Só preserva CONCLUIDO já existente com saídas íntegras; demais estados ficam REVISAO |
| Registro files_ready divergente ou arquivos ausentes | REVISAO; restaure os arquivos/planilha/configuração originais a partir do backup e reexecute |
| Registro rejected / status ERRO | Chamada rejeitada sem resultado; corrija quota/parâmetros e, se desejar tentar novamente, altere ERRO para PENDENTE |
| in_flight, uncertain ou PROCESSANDO sem registro | REVISAO; não reenvia automaticamente, mesmo se alguém mudar para PENDENTE |
| Arquivo já existente sem registro confirmado | Não sobrescreve nem assume sucesso; confira sua origem antes de mover/renomear |
| Registro ilegível | Interrompe; restaure um backup íntegro, não apague para forçar execução |

### Normalização e versões das assinaturas

Novos registros usam `row_fingerprint_version=2`. A assinatura e a construção
do job compartilham a mesma validação de `Quantidade`: ausente, vazio, 1 e 1.0
(incluindo texto numérico equivalente) representam uma imagem. Somente valores
finitos, inteiros e positivos são aceitos; zero, negativos, frações e booleanos
são rejeitados. Ausências do pandas (`NaN`, `pd.NA`, `NaT`) são tratadas
explicitamente. Acrescentar uma quantidade vazia não altera o histórico anterior.

IDs de células numéricas inteiras permanecem estáveis entre leituras como int
ou float. IDs textuais preservam zeros à esquerda: `001` é diferente de `1`.
Use o tipo **Texto** no Excel para esses IDs; a formatação visual `000` de uma
célula numérica não cria um ID textual. A leitura também preserva textos como
`NA`. Prompts, referências e nomes não recebem conversão numérica; apenas
espaços nas extremidades são removidos, conforme a regra existente. Mudanças
de conteúdo, espaços internos e quantidade efetiva continuam sendo detectados.

Assinaturas antigas sem versão (ou com versão 1) são conferidas com o algoritmo
anterior, enumerando somente representações equivalentes da quantidade e de
IDs originalmente numéricos. A migração exige correspondência com o hash antigo
e integridade das saídas. O hash original permanece em `row_fingerprint_v1`;
a versão e a assinatura nova são persistidas atomicamente. Não se adota
cegamente a linha atual. Divergência, versão desconhecida ou perda de identidade
exige REVISAO. Uma possível chave antiga convertida (`1` para o atual `001`)
também bloqueia a tarefa, sem mesclar ou apagar registros. Falha ao persistir
a migração interrompe novas gerações.

### Registros legados e revisão manual

A integridade de uma imagem não comprova sua correspondência com o prompt.
Para `files_ready`, usam-se os caminhos e hashes históricos; modelo, qualidade
e pasta atuais não preenchem dados históricos ausentes. Um registro **sem
assinatura da linha** não fornece evidência suficiente para confirmar tarefas
PROCESSANDO, REVISAO ou PENDENTE: ficam REVISAO com uma mensagem específica,
sem chamada e sem alteração do registro. Voltar manualmente para PENDENTE não
contorna a proteção.

Uma tarefa já CONCLUIDO com esse registro legado permanece assim somente se
suas saídas históricas estiverem íntegras. Isso preserva o histórico, mas **não
certifica que a imagem corresponde à linha atual**. Saída ausente, adulterada
ou inválida exige REVISAO inclusive nesse caso. Registros com assinatura
compatível e arquivos verificados continuam recuperando CONCLUIDO sem API.
Histórico inalterado na versão atual não regrava Excel nem registro; uma
migração comprovada da versão anterior grava apenas o registro.

Para REVISAO por resposta perdida, consulte o resultado/uso da execução na
conta antes de decidir. Se não for possível comprovar se houve geração,
mantenha bloqueado. O MVP não consegue recuperar a resposta perdida da API.
Preserve Excel, registro e arquivos e compare com backups da execução original.
Não apague entradas, não invente hashes e não preencha metadados antigos com a
configuração atual. Restaure dados originais somente com evidência verificável;
se faltar comprovação, mantenha REVISAO. Se decidir conscientemente pagar por
uma nova geração, crie outra linha com ID novo e inequívoco e outro nome de
saída, mantendo a linha e o registro anteriores para auditoria.

CONCLUIDO legado, produzido pelas versões antigas em simulação, não é prova
de imagem real. Confira os arquivos antes de redefinir manualmente esses itens.
`Tentativas` no Excel conta execuções reais da tarefa que chegaram ao estado
PROCESSANDO. O JSON registra separadamente cada tentativa de chamada à API.

Retries automáticos têm espera exponencial com pequena variação aleatória e
respeitam Retry-After. Apenas rejeições temporárias identificadas (429 com
rate_limit_exceeded/slow_down, ou 503 com server_is_overloaded) são repetidas.
Espera indicada acima de 60 segundos adia a tarefa, sem antecipar a chamada.
Quota, autenticação e parâmetros não são repetidos. Timeout, falha de conexão,
resposta inválida e falhas com resultado incerto exigem revisão. Isso reduz
reenvios pagos; a API não oferece aqui uma garantia de execução exatamente uma vez.

## Arquitetura e testes

`main.py` seleciona jobs e coordena estados; `src/execution_state.py` contém
trava, registro atômico e verificação de arquivos. `src/excel_reader.py`
preserva os tipos das células e as demais abas e salva Excel por substituição
atômica. `src/job_values.py` compartilha a normalização de valores e validação
de quantidade entre a montagem dos jobs e as assinaturas, sem dependência circular.
`src/generation_job.py` representa o job; `src/prompt_builder.py` monta o
texto; `src/file_manager.py` valida os caminhos. `src/image_generator.py`
define a interface, o mock e o provider OpenAI.

```powershell
python -m unittest discover -s tests -v
```

Testes usam pastas temporárias, clientes falsos e espera simulada; não leem o
`.env` real nem consomem créditos. A suíte bloqueia a criação do cliente de rede.
Cobre limites, simulação seguida de geração, interrupção, Excel bloqueado,
concorrência entre processos, prompt, retries e recuperação sem reenvio.

Para validar esta revisão no Windows, abra PowerShell na pasta do projeto,
ative o ambiente com `.\.venv\Scripts\Activate.ps1` (se instalado nesse caminho)
e execute o comando de testes acima. Para executar somente as regressões de
histórico: `python -m unittest discover -s tests -p test_history_signatures.py -v`.
Esses testes criam suas próprias planilhas e registros temporários, incluindo
a quarta linha com quantidade vazia, migração de assinaturas e revisão legada.
Não é necessário abrir a planilha do cliente nem executar `main.py` para validar
essas correções.

Documentação oficial consultada em 23/09/2026:
[edição de imagens](https://developers.openai.com/api/reference/cli/resources/images/methods/edit)
e [rate limits e retries](https://developers.openai.com/api/docs/guides/rate-limits).
Usamos `images.edit`, modelos gpt-image-2.5-sunburst e gpt-image-2.5-flare,
saída PNG/JPEG/WebP e retorno base64. Parâmetros adicionais foram conferidos em
06/10/2026 e estão documentados no [guia do Studio](docs/STUDIO.md).
Outros modelos são rejeitados até validar seus parâmetros. Acesso da conta,
saldo e qualidade visual devem ser avaliados para cada nova campanha; o piloto
de três imagens não garante custo ou resultado iguais.

Inclui interface local no navegador e estimativa de custo no histórico quando
há dados de uso. Ainda não inclui executável nem serviço em segundo plano.

## Referências em várias pastas

É possível combinar referências de pastas independentes em uma mesma linha da fila.
Na planilha, crie a aba opcional `Pastas_Referencias`, com estas duas colunas:

| Alias | Caminho |
| --- | --- |
| Produtos | C:\Fotos\Produtos |
| Marca | D:\Campanhas\Marca |

Em `Arquivo_Referencia`, use `Produtos::frente.jpg; Marca::logo.png`.
O nome antes de `::` identifica a pasta cadastrada; o restante é o caminho relativo
do arquivo, incluindo subpastas quando necessário. Os aliases distinguem maiúsculas
de minúsculas, começam com letra e aceitam letras sem acento, números, hífen e
sublinhado (até 40 caracteres). Não cadastre aliases que diferem apenas pela caixa.

Arquivos sem alias continuam usando `Pasta_Referencias` da aba `Configuracao`;
essa configuração permanece compatível com planilhas existentes e é dispensada
no modo de seleção direta.
Caminhos relativos das pastas são resolvidos a partir da pasta da planilha.
Pastas inexistentes ou aliases duplicados bloqueiam a configuração. Arquivos ausentes,
aliases desconhecidos e caminhos que escapem da pasta cadastrada são rejeitados.
O limite existente de 1 a 16 referências por geração OpenAI permanece.

O Studio integra os seletores nativos do Windows, edição de aliases e pasta padrão.
Use a ação de salvar pastas para gravar explicitamente o cadastro na planilha.
O protótipo aprovado permanece como referência visual; execute `studio.py` para
utilizar a interface conectada ao processamento.
