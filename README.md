# Projeto Gerador de Imagens em Lote

## Objetivo

Automatizar a preparação e execução de gerações de imagens a partir de uma planilha Excel.

O cenário principal é:
- um prompt técnico padrão;
- uma variação por imagem;
- uma imagem de referência local;
- execução em lote;
- salvamento organizado;
- controle de status por linha.

## Fluxo do MVP

Excel -> Python -> validação -> montagem do prompt -> DRY RUN ou simulação.

Nesta versão inicial **nenhuma API de imagem é chamada**.

## Estrutura

```text
projeto-gerador-imagens/
├── main.py
├── requirements.txt
├── .env.example
├── .gitignore
├── README.md
├── CODEX_PROMPT.md
├── src/
│   ├── excel_reader.py
│   ├── prompt_builder.py
│   ├── image_generator.py
│   ├── file_manager.py
│   └── logger.py
├── input/
│   ├── fila.xlsx
│   └── referencias/
├── output/
│   └── imagens/
└── logs/
```

## Status suportados

- PENDENTE
- PROCESSANDO
- CONCLUIDO
- ERRO

## Instalação

```bash
python -m venv .venv
```

Windows:

```bash
.venv\Scripts\activate
```

Instale as dependências:

```bash
pip install -r requirements.txt
```

## Uso

1. Coloque as imagens de referência em `input/referencias/`.
2. Atualize `input/fila.xlsx`.
3. Execute:

```bash
python main.py
```

4. Veja o resultado no Excel e em `logs/processamento.log`.

## Configuração

Na aba `Configuracao` de `input/fila.xlsx`, preencha `Pasta_Referencias`,
`Pasta_Resultados` e `Limite_Por_Execucao`. O limite deve ser um inteiro positivo.
Pastas relativas são resolvidas a partir de `input/` para referências e de
`output/` para resultados. Caminhos absolutos também são aceitos.

`Dry_Run` aceita `SIM` ou `NAO` e usa `SIM` se a linha estiver ausente. Em DRY RUN,
o console mostra ID, prompt final, referência e nome de saída. A planilha não é
alterada. Com `NAO`, o programa valida e marca os itens como `CONCLUIDO` em uma
simulação, sem gerar imagens. Erros são marcados como `ERRO` nesse modo.

## Referências e jobs

`Arquivo_Referencia` aceita um ou mais nomes separados por `;`, por exemplo
`modelo.jpg;produto.webp`. Todos devem existir na pasta de referências e ter
extensão PNG, JPG, JPEG ou WEBP. O erro identifica o arquivo ausente.

As colunas opcionais `Tema`, `Produto`, `Cliente`, `Prompt_Negativo`, `Quantidade`
e `Observacao_Usuario` são lidas para o `GenerationJob`; a planilha antiga segue
válida. `Quantidade` deve ser um inteiro positivo e usa 1 quando vazia ou ausente.
Com mais de uma imagem, `nome.png` produz `nome_001.png`, `nome_002.png` etc.

`src/generation_job.py` define o job; `src/image_generator.py` define a interface
abstrata `ImageGenerator` e o `MockImageGenerator`. Para exercitar o fluxo completo
com arquivos fictícios, defina `Dry_Run=NAO` e execute:

```bash
python main.py --mock
```

O mock grava conteúdo de teste, não imagens válidas. Arquivos existentes impedem
o processamento do respectivo job e nunca são sobrescritos. Sem `--mock`, a
execução com `Dry_Run=NAO` continua apenas simulando sucesso, sem criar arquivos.

## OpenAI Image API

Copie `.env.example` para `.env` e configure `IMAGE_PROVIDER=openai`. Defina
`OPENAI_API_KEY` no ambiente ou no `.env`; mantenha `.env` fora do controle de
versão. A chave nunca deve ser colocada na planilha. Para usar arquivos fictícios,
configure `IMAGE_PROVIDER=mock`. Sem `IMAGE_PROVIDER`, a execução mantém a
simulação local anterior. O argumento `--mock` também permite executar o mock.

Configure `Dry_Run=SIM` na planilha para revisar os jobs sem chamada externa.
`DRY_RUN` no `.env`, quando definido, tem prioridade sobre a aba `Configuracao`.
Com `Dry_Run=NAO` e `IMAGE_PROVIDER=openai`, `python main.py` usa o endpoint de
edição de imagens, pois cada job tem uma ou mais referências. O modelo padrão é
`gpt-image-2.5-sunburst`; `OPENAI_IMAGE_MODEL` permite escolher outro modelo
compatível. `OPENAI_IMAGE_QUALITY` usa `auto` por padrão. A saída real é PNG em
`output/imagens/`. Com quantidade maior que 1, `imagem_001.png` produz
`imagem_001_01.png`, `imagem_001_02.png` etc. O endpoint aceita até 10 imagens
de saída e 16 referências por chamada.

`MAX_JOBS_PER_RUN` e `MAX_IMAGES_PER_RUN` limitam cada execução (padrões 10 e 20).
Antes de processar, o console mostra provider, jobs encontrados, imagens previstas
e limites. `OPENAI_TIMEOUT_SECONDS` e `OPENAI_RETRIES` controlam timeout e novas
tentativas em erros temporários. Falhas são marcadas como `ERRO`, com incremento
de `Tentativas`; os jobs seguintes continuam. Os testes usam clientes falsos e
não fazem chamadas à API nem consomem créditos.

Implementação baseada no [guia oficial de geração de imagens](https://developers.openai.com/api/docs/guides/image-generation)
e na [referência oficial de edição](https://developers.openai.com/api/reference/cli/resources/images/methods/edit).

## Primeiro teste com OpenAI

O projeto vem com `.env` inicial sem chave. Para o primeiro teste, mantenha:

```dotenv
IMAGE_PROVIDER=openai
DRY_RUN=SIM
MAX_JOBS_PER_RUN=1
MAX_IMAGES_PER_RUN=1
OPENAI_IMAGE_MODEL=gpt-image-2.5-sunburst
```

No `.env`, essas quatro primeiras variáveis de controle são necessárias para o
primeiro teste. `OPENAI_API_KEY` precisa ter valor antes da execução real; pode
estar no `.env` ou como variável de ambiente. `OPENAI_IMAGE_MODEL` é opcional e
usa `gpt-image-2.5-sunburst` por padrão. `OPENAI_IMAGE_QUALITY`,
`OPENAI_TIMEOUT_SECONDS` e `OPENAI_RETRIES` são opcionais, com padrões `auto`,
`120` e `2`. Nunca coloque o valor da chave na planilha, em logs ou no README.

1. Copie uma imagem PNG, JPG, JPEG ou WEBP para `input/referencias/`, por exemplo
   `produto.png`.
2. Na aba `Fila_Geracao` de `input/fila.xlsx`, deixe apenas a linha desejada como
   `PENDENTE`. Preencha `Arquivo_Referencia` com `produto.png`, `Nome_Saida` com
   um nome novo terminado em `.png`, por exemplo `teste_001.png`, e
   `Prompt_Padrao` e/ou `Prompt_Variacao`. Se houver `Quantidade`, use `1`.
3. Na aba `Configuracao`, confira `Pasta_Referencias=referencias` e
   `Limite_Por_Execucao=1`. Execute `python main.py` com `DRY_RUN=SIM`. Confira
   ID, prompt, referência e saída no console; nenhuma API será chamada e a
   linha continuará `PENDENTE`.
4. Para a primeira execução real, configure `OPENAI_API_KEY` no ambiente ou no
   `.env`, mantenha ambos os limites em `1`, mude `DRY_RUN=NAO` no `.env` e
   execute `python main.py`. O programa valida chave, referência e nome de
   saída antes de criar o cliente. O resultado será salvo em `output/imagens/`.

O primeiro teste real é bloqueado se qualquer limite exceder 1, se a chave
estiver ausente, se a referência faltar ou se o nome de saída for inválido ou
já existir. Verifique a disponibilidade do modelo na sua conta antes de
autorizar uma chamada paga.

O limite seleciona os primeiros itens `PENDENTE` na ordem da planilha. O resumo
mostra processados, sucessos, erros e ignorados; ignorados inclui todas as linhas
não selecionadas, inclusive as que já estavam concluídas. Um nome de saída vazio,
inválido ou já existente na pasta de resultados causa erro na linha.

## Testes

Depois de instalar as dependências, execute na raiz do projeto:

```bash
python -m unittest discover -s tests -v
```

Os testes usam uma planilha temporária e não modificam `input/fila.xlsx`.

## Regras de confiabilidade

- Só processar linhas `PENDENTE`.
- Não interromper toda a fila quando uma linha falhar.
- Marcar linha problemática como `ERRO`.
- Incrementar tentativas.
- Permitir reexecução sem reprocesar itens `CONCLUIDO`.
- Não salvar chave de API dentro da planilha.
- Não sobrescrever saída silenciosamente na fase de geração real.

## Próximas fases

1. Validar com imagens reais do cliente.
2. Implementar integração com API de imagem.
3. Salvar resultados em `output/imagens/`.
5. Adicionar retry configurável.
6. Adicionar estimativa de custo.
7. Avaliar criação de interface gráfica ou `.exe`.
