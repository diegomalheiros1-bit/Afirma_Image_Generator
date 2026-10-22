# Build macOS Apple Silicon

Destino inicial: Mac M1/M2 ou posterior, macOS 15+. Preparado a partir da
versão Windows 1.0.21. Esta preparação ainda exige execução e validação em Mac.
Não apresenta testes simulados no Windows como prova de funcionamento nativo.

Validação local em 22/10/2026: 219 testes Python passaram com rede externa
bloqueada, 3 testes JavaScript passaram, análise estática sem avisos e
dependências Windows consistentes. Diagnóstico nativo Windows passou após a
adaptação. A compilação Mac, os testes WKWebView e o DMG permanecem pendentes.

## Compilação

Em macOS ARM64 com Python 3.13:

```sh
python -m pip install -r requirements-build-macos.txt
python -m pip check
python scripts/build_macos_package.py
```

O workflow `Build Mac Apple Silicon` usa `macos-15` ARM64. Dispara ao publicar
a branch `codex/macos-installer`, ou manualmente quando disponível no GitHub.
Não publica releases nem envia
o pacote ao cliente; guarda o DMG como artefato da execução bem-sucedida.
Minutos de CI dependem do plano e da visibilidade do repositório.

O script produz `.app` com dependências, verifica ARM64 e assinatura ad-hoc,
rejeita arquivos de campanha/credenciais e executa o aplicativo congelado com
diagnóstico isolado. O diagnóstico verifica WKWebView, inicialização, mensagem
vazia, três tamanhos de janela, leitura de Excel/referência e simulação. Não
usa chave real, não acessa o Chaves e bloqueia conexões Python fora do loopback.
Somente então cria/verifica o DMG e grava SHA256 e metadados de build.

## Limites e conferência antes de entrega

- Testar o DMG baixado em macOS, arrastar o aplicativo para Aplicativos e
  confirmar a primeira abertura pela opção documentada pela Apple.
- Conferir seletores nativos de Excel, imagens e pastas e abertura no Finder.
- Conferir salvar, reler e remover uma chave fictícia no Chaves; verificar que
  negar acesso deixa a opção de chave somente na sessão utilizável.
- Conferir fechamento durante simulação e histórico após reabrir.
- A geração paga não faz parte dos testes automáticos nem foi validada nesta
  preparação. O processo existente de confirmação continua obrigatório.

O teste automatizado não cobre os diálogos do Gatekeeper nem acesso real ao
Chaves. Sem certificado de desenvolvedor/notarização, a primeira abertura pode
pedir autorização em Privacidade e Segurança. Não remover quarentena ou
desativar o Gatekeeper para esconder erros de distribuição.

## Dados

Preferências/cache/logs: `~/Library/Application Support/Afirma Image Studio`.
Chave: backend específico `keyring.backends.macOS.Keyring`, sem backend
alternativo ou fallback em texto. Um identificador derivado do caminho das
preferências separa instalações de diagnóstico. O status é consultado uma vez
e atualizado em salvar/remover; a leitura para uso continua consultando Chaves.
Histórico e saídas seguem junto das planilhas/pastas escolhidas pelo usuário.

Referências técnicas: [PyInstaller](https://pyinstaller.org/en/stable/feature-notes.html),
[pywebview](https://pywebview.flowrl.com/guide/installation),
[keyring](https://keyring.readthedocs.io/en/stable/),
[runners GitHub](https://docs.github.com/en/actions/reference/runners/github-hosted-runners),
[primeira abertura no Mac](https://support.apple.com/pt-br/102445).
