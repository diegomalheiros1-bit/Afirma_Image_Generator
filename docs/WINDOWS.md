# Afirma Image Studio no Windows

O aplicativo abre em uma janela própria, com os controles normais de minimizar,
maximizar, restaurar e redimensionar. O conteúdo usa WebView2 incorporado à janela;
não é necessário abrir nem instalar um navegador separado. O processamento
continua no computador e o servidor interno aceita apenas `127.0.0.1`.

## Usar o pacote

1. Use Windows 10/11 de 64 bits com [Microsoft Edge WebView2 Runtime](https://developer.microsoft.com/microsoft-edge/webview2/).
2. Extraia o ZIP completo e mantenha `_internal` ao lado de `Afirma-Image-Studio.exe`.
3. Abra o executável. Não é necessário instalar Python nem manter terminal aberto.
4. Selecione planilha, referências e pasta de saída. Confira os limites da execução.
5. Informe sua chave em **Configurações > Opções avançadas**. A verificação de
   autenticação não gera imagens e não confirma saldo nem acesso ao modelo.
6. Confira e simule a campanha. Os três botões têm ajuda ao passar o mouse ou
   receber foco pelo teclado. Gerar abre uma janela com o resumo do lote e o
   aviso de cobrança; revise antes de clicar em **Confirmar e gerar imagens**.
   Cancelar ou Esc fecha essa janela sem iniciar a geração.

Em **Configurações > Sobre**, consulte a apresentação do software, versão,
autoria e informações sobre a API usada. Os links oficiais de documentação,
preços, consumo e chaves abrem no navegador padrão somente quando clicados.
A consulta a Sobre não chama a API nem altera as preferências de geração.

O botão pago fica disponível no aplicativo local, mas cada execução exige
confirmação e pode gerar cobrança na conta da chave. Para uma sessão sem esse
botão, abra `Afirma-Image-Studio.exe --simulation-only`.

Ao tentar fechar durante uma campanha, escolha entre continuar ou encerrar após
a imagem atual. Na segunda opção, a janela aguarda o salvamento do resultado.
Forçar o encerramento pelo Gerenciador de Tarefas ou desligar o computador
interrompe essa proteção e pode exigir revisão do histórico na próxima abertura.

## Janela e dados

A janela tem tamanho mínimo de 520 × 500 pixels lógicos. Abaixo de 1100 pixels de
largura útil, os painéis principais passam para uma coluna. Campos e botões se
reorganizam em janelas menores. A tabela de eventos mantém rolagem horizontal
dentro da tabela para preservar as colunas; o restante da tela rola verticalmente.

Preferências, chave protegida pelo usuário do Windows, logs e cache ficam em
`%LOCALAPPDATA%\Afirma Image Studio`. O campo da chave permanece vazio ao reabrir;
o status informa se existe credencial salva, da sessão ou do ambiente. A pasta
do pacote pode ficar em local sem permissão de escrita.

Planilhas, imagens e histórico permanecem nas pastas selecionadas. A simulação
preserva a planilha e não cria imagens finais. O ZIP não inclui credenciais nem
dados de campanhas. O pacote é portátil, sem instalador e sem assinatura digital.

Se o aplicativo não abrir, confira a extração completa, o Runtime WebView2 e
`startup-error.txt` na pasta de dados. O log de processamento fica em
`logs/processamento.log` nessa mesma pasta. O aplicativo não instala componentes
do Windows nem altera Firewall automaticamente.

## Desenvolver e gerar o pacote

Use um ambiente virtual isolado. A build Windows depende de pywebview e
PyInstaller, com versões fixadas nos arquivos de requisitos:

```powershell
python -m venv .venv-desktop
.\.venv-desktop\Scripts\python.exe -m pip install -r requirements-build-windows.txt
.\.venv-desktop\Scripts\python.exe -m unittest discover -s tests -v
.\.venv-desktop\Scripts\python.exe desktop.py --simulation-only
.\.venv-desktop\Scripts\python.exe scripts/build_windows_package.py
```

A build usa `desktop.py`, o backend WebView2 e o modo Windows GUI, sem console.
O script rejeita credenciais e planilhas no pacote. Antes de criar o ZIP,
executa o próprio `.exe` com `--self-test` em uma pasta nova: três itens simulados,
seleção de arquivos, nomes normalizados, rejeição local de chave incompleta,
maximização, restauração, layouts menores, temas e log. Também testa a janela
paga com backend bloqueado e início interceptado: cancelamento, falta de chave,
resumo alterado e proteção contra clique repetido. Não usa `.env`, não
envia chaves nem chama a API. O diagnóstico recusa reutilizar uma campanha
de teste existente, para preservar arquivos.

Cada release fica em `output/releases/<data-hora>/`, separada das anteriores:

- `Afirma-Image-Studio/`: aplicativo completo, `_internal` e `LEIA-ME.txt`.
- `Afirma-Image-Studio-Windows.zip`: distribuição para o cliente.
- `SHA256.txt`: hash do ZIP.
- `build-info.json`: versões, commit de origem, estado do código e hashes dos fontes.
- `verification/`: relatório do executável e capturas da interface, fora do ZIP.

Essa validação confirma o funcionamento no computador da build. Windows com
outras políticas, escala de tela ou Runtime precisam de validação no computador
do cliente. O teste pago de acesso ao modelo e qualidade de imagem continua
sendo uma etapa explícita e separada.

A interface opcional no navegador continua disponível por `studio.py`, com API
bloqueada por padrão; `--enable-api` é o habilitador deliberado dessa versão.
