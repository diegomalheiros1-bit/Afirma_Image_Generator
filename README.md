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
entradas/saídas. Não armazena prompts, binários ou credenciais. Preserve esse
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

| Situação | Recuperação |
| --- | --- |
| Excel aberto, permissão ou disco cheio | Feche o Excel, corrija o acesso/espaço, preserve arquivos e registro e execute novamente |
| Registro prepared | Nenhuma chamada começou; retorna automaticamente a PENDENTE |
| Registro files_ready e arquivos/hashes conferem | Recupera CONCLUIDO sem API, mesmo se o Excel ficou PROCESSANDO |
| Registro files_ready divergente ou arquivos ausentes | REVISAO; restaure os arquivos/planilha/configuração originais a partir do backup e reexecute |
| Registro rejected / status ERRO | Chamada rejeitada sem resultado; corrija quota/parâmetros e, se desejar tentar novamente, altere ERRO para PENDENTE |
| in_flight, uncertain ou PROCESSANDO sem registro | REVISAO; não reenvia automaticamente, mesmo se alguém mudar para PENDENTE |
| Arquivo já existente sem registro confirmado | Não sobrescreve nem assume sucesso; confira sua origem antes de mover/renomear |
| Registro ilegível | Interrompe; restaure um backup íntegro, não apague para forçar execução |

Para REVISAO por resposta perdida, consulte o resultado/uso da execução na
conta antes de decidir. Se não for possível comprovar se houve geração,
mantenha bloqueado. O MVP não consegue recuperar a resposta perdida da API.
Somente após confirmação de que não houve resultado ou uma decisão consciente
de pagar por uma nova geração, arquive Excel, registro e arquivos; remova
manualmente apenas a entrada daquele ID no JSON e retorne a linha a PENDENTE.
Não apague o registro inteiro: ele protege as outras tarefas de duplicação.

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
preserva as demais abas e salva Excel por substituição atômica.
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

Documentação oficial consultada em 23/09/2026:
[edição de imagens](https://developers.openai.com/api/reference/cli/resources/images/methods/edit)
e [rate limits e retries](https://developers.openai.com/api/docs/guides/rate-limits).
Usamos `images.edit`, modelo gpt-image-2.5-sunburst, saída PNG e retorno base64.
Outros modelos são rejeitados até validar seus parâmetros. Acesso do projeto,
saldo e qualidade visual só podem ser confirmados em teste real autorizado.

Não inclui interface gráfica, executável, serviço ou estimativa monetária.
