# Afirma Image Studio

Interface funcional local sobre o mesmo processamento de `main.py`. Usa o logo,
paleta roxa, painéis claros e organização do protótipo aprovado. Sem dependências
web, CDN, upload para terceiros, serviço público ou armazenamento do navegador.

## Instalar e abrir

Python 3.11+, dependências de `requirements.txt` e Tkinter (incluído no instalador
oficial do Python para Windows). Nesta implementação, Python/Tkinter, pandas,
openpyxl, Pillow e OpenAI já estavam instalados: nenhum download foi necessário.

```powershell
python studio.py
```

O terminal mostra o endereço `http://127.0.0.1:<porta>/` e abre o navegador.
Mantenha o processo ativo. O servidor aceita somente o host loopback exato,
valida a origem e exige token de sessão nas operações; não serve `.env` ou
arquivos arbitrários. A API real fica **bloqueada no servidor**, não apenas no botão.

`--no-browser` evita abrir uma aba; `--port 8765` escolhe uma porta local.
Não use o HTML sozinho: ele precisa do servidor Python.

## Dois modos de referências

**Pela planilha — fotos por item:** cada item usa somente `Arquivo_Referencia`.
Fotos da seleção direta não participam. Campo vazio, alias desconhecido, arquivo
ausente e imagem inválida impedem a conferência da campanha antes de qualquer API.

**Selecionar no software — fotos da campanha:** use Adicionar fotos repetidamente
para selecionar PNG, JPG/JPEG e WebP de diferentes pastas. Miniaturas, nome e
caminho distinguem arquivos com o mesmo nome. Remova fotos individualmente.
Somente o mesmo caminho resolvido é deduplicado. Todas as linhas usam essa seleção;
`Arquivo_Referencia` é completamente ignorado, inclusive ausente ou inválido.
Prompts, IDs, nomes de saída e demais colunas obrigatórias continuam exigidos.
São aceitas de 1 a 16 referências, cada uma com menos de 50 MiB e conteúdo válido.

### Resumo ao selecionar a planilha

Depois da seleção, o Studio informa quantos itens têm prompt, quantos estão
pendentes e quantas imagens estão previstas para os pendentes. Também mostra o
lote estimado para a próxima execução: ele respeita o menor limite entre
`MAX_JOBS_PER_RUN` e `Limite_Por_Execucao`, além de `MAX_IMAGES_PER_RUN`.
Linhas que excedam esses limites permanecem pendentes para execuções futuras.
Quando `Quantidade` está vazia, considera-se uma imagem; quantidades inválidas
são sinalizadas e ficam fora da estimativa.
Planilha, modo, referências, pastas e preferências ficam bloqueados durante a
execução, inclusive pausada. Encerrar aguarda o item atual; não interrompe uma
requisição em andamento. Pausar/Retomar funciona entre itens e mantém o mesmo
snapshot de configurações. Arquivos de referência alterados durante o lote são
rejeitados; o provider envia cópias imutáveis dos bytes validados.

## Várias pastas e compatibilidade com Excel

A seleção da planilha carrega a aba opcional `Pastas_Referencias`:

| Alias | Caminho |
| --- | --- |
| Produtos | C:\Campanhas\Produtos |
| Marca | D:\Identidade\Marca |

Exemplo: `Produtos::frente.jpg; Marca::logos\principal.png`.
Arquivos sem alias usam a pasta padrão, originalmente `Pasta_Referencias` da aba
`Configuracao`. Planilhas antigas continuam funcionando sem a aba adicional.
Aliases começam com letra ASCII e têm até 40 caracteres: letras, números, `_`, `-`.
Duplicados são rejeitados inclusive quando diferem apenas por maiúsculas.
O uso do alias é exato, incluindo maiúsculas/minúsculas.

Adicionar/editar abre um seletor nativo de diretórios. O nome curto é informado
separadamente. Remover consulta os IDs que usam o alias e mostra um aviso; nenhum
arquivo da pasta é apagado. Para remover a pasta padrão, escolha outra padrão
explicitamente antes. Arquivos sem alias não são redirecionados silenciosamente.
Caminhos finais são resolvidos, incluindo junctions e links: nenhum arquivo pode
escapar da raiz autorizada. Subpastas dentro dessa raiz são permitidas.

O cadastro editado fica **somente na sessão** até clicar em **Salvar pastas na
planilha** e confirmar a gravação explícita. Essa ação usa a trava da fila e uma
substituição atômica do Excel; atualiza `Pastas_Referencias` e, quando escolhida,
`Pasta_Referencias` para a pasta padrão absoluta. As demais abas são preservadas.
Não é necessário salvar o cadastro para simular ou gerar nesta sessão.

## Parâmetros de imagem

Os dois modelos suportados são `gpt-image-2.5-sunburst` e `gpt-image-2.5-flare`.
Suportam PNG/JPEG/WebP; fundo `auto`, `opaque`, `transparent`; qualidade `auto`,
`low`, `medium`, `high`, `xhigh`, `max`. JPEG com transparência é erro explícito.
PNG/WebP aceitam transparência. Não há conversão silenciosa de escolhas.

Resoluções: automática, 1024×1024, 1536×1024, 1024×1536 ou personalizada.
Personalizadas exigem ambos os lados múltiplos de 16, razão entre 1:3 e 3:1,
lados de no máximo 3840 pixels e área de 655.360 a 8.294.400 pixels.
Acima da área de 2560×1440, a interface identifica a resolução como experimental.
Qualidade/resolução maiores podem aumentar tempo e custo; não há estimativa
monetária inventada nem consulta de saldo por esta interface.

Compressão é opcional, somente JPEG/WebP, separada da qualidade de geração.
A documentação oficial atual define `output_compression` como compressão de
0–100%; a interface envia o mesmo percentual, sem inversão. PNG não envia esse
parâmetro. Ao trocar para PNG, se havia compressão explícita, desmarque-a antes
de aplicar; uma combinação inválida é bloqueada, não corrigida silenciosamente.

O nome na planilha deve combinar com o formato: `.png`, `.jpg`/`.jpeg`, `.webp`.
O software não renomeia os nomes da planilha automaticamente. A API recebe o
formato e o conteúdo retornado é validado com Pillow antes de gravar. Conteúdo
inesperado é resultado incerto para revisão; não vira uma imagem de outro formato
com uma extensão falsa. Criação exclusiva impede sobrescrita.

Fontes oficiais conferidas em 06/10/2026:

- [Guia de geração e limites](https://developers.openai.com/api/docs/guides/image-generation)
- [Parâmetros de edição e até 16 referências](https://developers.openai.com/api/reference/resources/images/methods/edit)

## Precedência e persistência

- CLI: ambiente do processo > `.env` junto à estrutura da fila > padrões do código.
  `DRY_RUN` do ambiente/`.env` tem precedência sobre `Dry_Run` do Excel.
  `Pasta_Resultados`, pastas de referência e limite da planilha continuam válidos.
- Studio: preferências salvas > valores não secretos do ambiente/`.env` do
  **projeto** > padrões. Alterações aplicadas na sessão têm precedência na próxima
  execução; o snapshot da interface prevalece sobre os parâmetros de imagem do
  ambiente. Pasta de saída vazia usa o Excel. O máximo de itens continua sendo o
  menor entre limite da interface e `Limite_Por_Execucao` do Excel.
- Simular impõe `DRY_RUN=SIM`; gerar impõe `DRY_RUN=NAO`, somente quando o servidor
  foi iniciado explicitamente com `--enable-api`. Modo seguro mantém a trava
  existente dos três limites <= 1. Simulação não lê a chave para criar clientes.
- Aplicar nesta sessão não grava arquivos. Salvar preferências grava atomicamente
  `.studio-settings.json` (ignorado no Git), somente com uma lista permitida de
  parâmetros. `--settings <arquivo>` permite usar outro destino local.
- Planilha selecionada, modo, fotos e cadastro não salvo são da sessão e se perdem
  ao fechar o servidor. Fotos nunca são colocadas em localStorage/browser storage.
- Chaves continuam somente no `.env` existente ou no ambiente. Não há campo de
  chave, armazenamento pelo navegador, alteração de credencial ou inclusão da
  chave nas preferências, HTML, JSON de estado ou logs do servidor.

## Histórico e retomada

`fila.xlsx.state.json` continua sendo o registro de cada geração. Novos registros
acrescentam `execution` versão 1 e `execution_fingerprint`: configuração de imagem,
modo, caminhos resolvidos, hashes SHA256 das referências, saídas e assinatura da
linha. A assinatura de linha v2 e a migração comprovada v1 continuam existindo.
No modo direto, apenas `Arquivo_Referencia` é excluído da assinatura efetiva,
pois não participa da geração. Mudanças reais de prompt, quantidade e demais
campos continuam detectadas.

Para tarefas interrompidas com `files_ready`, confira a mesma planilha, selecione
o mesmo modo/fotos e reaplique os parâmetros originais. Correspondência e
integridade comprovadas recuperam CONCLUIDO sem API. Divergências de parâmetros,
modo, caminho ou bytes da referência mantêm REVISAO. Versões desconhecidas também.
Tarefas já concluídas preservam modelo, qualidade, formato e destino históricos;
novas preferências globais não as reinterpretam. Mudanças de referência/linha
continuam sendo detectadas. Os novos parâmetros não são inventados para registros
antigos: saídas antigas continuam PNG e a política conservadora legada permanece.

`in_flight`, `uncertain`, registros sem assinatura e arquivos divergentes não são
reenviados automaticamente. Preserve Excel, estado e imagens. Não apague histórico
para destravar itens. O software não recupera uma resposta perdida da API.

## Testes e verificação sem API

```powershell
python -m unittest discover -s tests -v
python scripts/verify_studio.py
```

A suíte usa planilhas/imagens temporárias e clientes falsos. A classe de isolamento
bloqueia a criação de `openai.OpenAI`. Inclui as regressões anteriores, modos,
seleção cumulativa, aliases/junctions, parâmetros, formatos, recuperação e bloqueio
de alterações. O script cria `output/studio-verification/`, uma campanha fictícia
de 12 itens e duas fotos `foto.png` em pastas diferentes. Abre um servidor loopback
com API real desabilitada. Mostra a URL; abra-a, simule, pause e retome. A seleção
pré-carregada permite testar o fluxo sem tocar em dados de produção.

Simulação valida os itens e exibe SIMULADO; preserva PENDENTE, tentativas e histórico.
Não cria imagens finais. Pausa é da sessão ativa; após fechar o programa, uma nova
simulação começa de novo. Retomada de gerações reais depende do registro persistido.

## Teste pago e limitações

Nenhuma chamada real foi autorizada para esta implementação. Após revisar testes
e interface, proponha uma única imagem, com fotos e parâmetros definidos, nome
de saída novo e limite 1. Só após autorização explícita abra `python studio.py
--enable-api`, confira a campanha e use Gerar imagens — API paga. O botão pede
confirmação da execução concreta. Acesso ao modelo, saldo, latência e qualidade
visual só podem ser confirmados nesse teste pago.

Não inclui executável, serviço Windows, processamento com computador desligado,
gerenciador de chaves, recuperação remota de respostas ou estimativa financeira.
Não publica nem faz push. Um diretório inexistente configurado no Excel é rejeitado
ao carregar; corrija seu caminho antes de usar o modo planilha.

## Revisão independente

No modo de seleção direta, `Pasta_Referencias` pode ficar vazia ou ausente.
Ao voltar para referências pela planilha, selecione uma pasta padrão se não houver
uma configuração legada. Trabalhos interrompidos na fase `prepared` participam
da validação e da captura de hashes antes da retomada, mesmo com status
`PROCESSANDO`, preservando a detecção de alterações nos arquivos.

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
