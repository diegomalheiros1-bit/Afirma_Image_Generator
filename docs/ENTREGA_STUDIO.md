# Entrega local para revisão — 06/10/2026

## Diagnóstico

- Branch `main`, HEAD `e3a145c`; `git ls-remote origin refs/heads/main` confirmou o
  mesmo commit no remoto durante o diagnóstico. Não foi feito fetch com alterações
  de branch, commit, push, merge ou publicação.
- Alterações prévias preservadas: README, main, excel_reader, file_manager e
  `tests/test_reference_folders.py`. O arquivo temporário do Excel `input/~$fila.xlsx`
  já estava presente e não foi alterado/removido.
- Existia processamento Python e um protótipo HTML; não existia interface conectada.
- Nenhuma dependência instalada ou baixada. Credenciais e planilha de produção
  não foram editadas; fixtures são independentes.

## Entregue

Interface funcional local, dois modos exclusivos de referências, seleção cumulativa
com miniaturas e caminhos, cadastro de pastas com gravação explícita no Excel,
parâmetros completos dos dois modelos, formato/conteúdo validados, pausa/retomada
entre itens, bloqueio de mutações, preferências locais sem segredos e histórico
da configuração efetiva com hashes de referências. API real bloqueada por padrão
também no servidor. O guia [STUDIO.md](STUDIO.md) contém uso e limitações.

## Arquivos

- Interface/servidor: `studio.py`, `web/studio.html`, `src/studio_session.py`,
  `src/native_picker.py`.
- Pipeline: `main.py`, `src/image_settings.py`, `src/generation_job.py`,
  `src/image_generator.py`, `src/execution_state.py`, `src/excel_reader.py`,
  `src/file_manager.py`.
- Configuração/documentação: `.env.example`, `.gitignore`, `README.md`, `docs/`.
- Testes: `tests/test_studio.py`; preservado `tests/test_reference_folders.py`.
- Reprodução: `scripts/verify_studio.py`, `scripts/prepare_api_proposal.py`,
  `scripts/import_prototype_brand.py` (importação local do logo aprovado).

## Validação

`python -m unittest discover -s tests`: **87 testes passaram**, incluindo 63
preexistentes e regressões novas. Clientes de rede são bloqueados; APIs falsas
retornam imagens reais locais PNG/JPEG/WebP. A suíte verifica também junctions,
saídas sem sobrescrita, recuperação e diferenças de configurações/referências.

Artefatos locais ignorados no Git:

- `output/studio-verification/test-summary.json` e `test-results.txt`.
- `output/studio-verification/interface-concluida.png`.
- `output/studio-verification/campanha-ficticia.xlsx` e fotos de demonstração.
- `output/studio-verification/teste-real-proposto/proposal.json`: DRY RUN de uma
  imagem concluído sem API; proposta [TESTE_REAL_PROPOSTO.md](TESTE_REAL_PROPOSTO.md).

Verificação no Chrome pela interface: 12/12 itens simulados, zero erros; duas
fotos `foto.png` de pastas diferentes preservadas, pausa em 3/12, controles de
modo/seleção desabilitados durante a pausa e retomada até 12/12. JPEG com fundo
transparente exibiu erro e impediu aplicar a configuração. Captura salva acima.
Seletores Tk nativos têm testes de contrato; a automação do navegador verificou
o fluxo com a seleção fictícia pré-carregada, não dirigiu os diálogos nativos.
Listener inspecionado: somente `127.0.0.1`.

## Estado da publicação e limites

Tudo desta entrega está **somente local**, como alterações para revisão. O remoto
permanece na entrega anterior `e3a145c`. Nenhuma chamada paga foi realizada.
Não há executável/serviço, estimativa financeira por imagem ou retomada de
simulação após fechar o processo. Pausa aguarda o item atual terminar; respostas
perdidas da API continuam exigindo REVISAO. Acesso/saldo/qualidade comercial
dependem do teste real explicitamente autorizado.

## Correções da revisão independente — 06/10/2026

Corrigidos os dois casos reproduzidos na revisão: referência exclusiva de trabalho
`prepared` omitida da captura e exigência desnecessária de `Pasta_Referencias`
no modo direto. Testes de regressão em `tests/test_review_regressions.py`.
A suíte final contém 89 testes, executados em cópia isolada com clientes falsos.
A publicação foi autorizada pelo usuário após a revisão; o estado de entrega
somente local acima descreve a etapa anterior à publicação. Nenhum teste pago foi autorizado.
