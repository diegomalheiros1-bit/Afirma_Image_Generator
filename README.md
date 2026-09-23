# Afirma Image Generator

MVP Python para gerar imagens a partir de Excel, combinando prompt padrão,
variação e referências de modelo/produto. Processamento sequencial e local.
O script depende de um processo ativo: fechar o terminal, desligar o computador
ou interromper o Python interrompe o lote. Não há serviço em segundo plano.

## Instalação

Requer Python 3.11 ou superior. Na raiz do projeto, em PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Se ainda não houver `.env`, copie `.env.example` para `.env`.
Preencha `OPENAI_API_KEY` apenas nesse arquivo ou na variável de ambiente.
Nunca coloque a chave no Excel, no código, nos logs ou em commits.
O ambiente tem precedência sobre o `.env`; `DRY_RUN` tem precedência sobre
`Dry_Run` da aba `Configuracao`. Feche o Excel antes de executar o programa.

## Planilha e referências

A aba `Fila_Geracao` requer `ID`, `Prompt_Padrao`, `Prompt_Variacao`,
`Arquivo_Referencia`, `Nome_Saida`, `Status`, `Tentativas` e `Observacao`.
IDs devem ser únicos, preenchidos e estáveis. Não altere IDs para contornar
uma tarefa bloqueada: eles ligam a linha ao histórico da geração.

Colunas opcionais: `Tema`, `Produto`, `Cliente`, `Prompt_Negativo`, `Quantidade`
e `Observacao_Usuario`. Quantidade ausente/vazia significa 1; deve ser inteira
positiva. Na OpenAI, use de 1 a 10 por job.

`Arquivo_Referencia` aceita `modelo.jpg;produto.png`, preservando a ordem.
Todas as referências devem existir sob a pasta configurada. PNG, JPEG/JPG e
WEBP são aceitos. Antes da chamada real, o conteúdo também é validado como
imagem; OpenAI aceita até 16 referências, cada uma menor que 50 MB.

`Nome_Saida` deve ser um nome de arquivo, sem subpastas. Na OpenAI, use `.png`.
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
| Pasta_Referencias | Relativa à pasta do Excel, por exemplo `referencias` |
| Pasta_Resultados | Relativa a `output/` na pasta pai de `input/`, por exemplo `imagens` |
| Limite_Por_Execucao | Máximo de jobs por execução, inteiro positivo |
| Dry_Run | SIM/NAO; padrão SIM, usado se DRY_RUN não estiver definido |

Caminhos absolutos também são aceitos. `Modelo_API`, `Qualidade` e
`Prompt_Sistema` legados na planilha não são usados: modelo e qualidade vêm
das variáveis abaixo. `Observacao` é controle do programa;
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
| OPENAI_IMAGE_MODEL | gpt-image-2.5-sunburst | Modelo validado neste MVP |
| OPENAI_IMAGE_QUALITY | auto | auto, low, medium, high, xhigh, max |
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

## Validar primeiro uma imagem real

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
todos os PNGs, grava `files_ready` com hashes e só então grava CONCLUIDO.
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
Usamos `images.edit`, modelo gpt-image-2.5-sunburst, saída PNG e retorno base64.
Outros modelos são rejeitados até validar seus parâmetros. Acesso do projeto,
saldo e qualidade visual só podem ser confirmados em teste real autorizado.

Não inclui interface gráfica, executável, serviço ou estimativa monetária.
