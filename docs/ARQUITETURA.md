# Arquitetura e manutenção do Afirma Studio

O aplicativo Windows e a interface no navegador usam o mesmo processamento local.
Não há serviço externo próprio, banco de dados ou processo de geração paralelo.
O objetivo é manter responsabilidades claras sem adicionar infraestrutura que
não é necessária para o produto atual.

## Responsabilidades

| Camada | Arquivos | Responsabilidade |
| --- | --- | --- |
| Janela Windows | `desktop.py`, `src/desktop_app.py` | WebView2, seletores nativos e encerramento após salvar o item atual |
| Transporte local | `studio.py` | HTTP, autenticação local, rotas e lista explícita de arquivos da interface |
| Interface | `web/studio.html`, `studio.css`, `studio.js`, `studio-utils.js`, `theme.js`, `brand.png` | Estrutura, aparência, interação, contadores e tema |
| Sessão | `src/studio_session.py` | Preferências, credenciais, prévia, bloqueios, worker e progresso |
| Histórico | `src/run_history.py` | Leitura e validação dos registros de execução |
| Processamento | `main.py` | CLI, sequência de itens, persistência e recuperação |
| Preparação | `src/job_builder.py`, `generation_job.py`, `run_selection.py`, `output_naming.py` | Job imutável, elegibilidade, referências e alocação de nomes |
| Dados locais | `excel_reader.py`, `execution_state.py`, `regeneration.py` | Excel, trava, journal, assinaturas e preservação das gerações anteriores |
| Provedor | `image_generator.py`, `image_settings.py`, `generation_errors.py` | Parâmetros, chamada, diagnóstico sanitizado e gravação exclusiva |
| Credenciais | `credential_store.py`, `api_connection.py` | DPAPI e verificação de conexão |

Os módulos de preparação importam `src/job_builder.py`, sem importar o ponto
de entrada da CLI. `main.make_job` permanece disponível por compatibilidade.
O worker da sessão chama o mesmo `main()` usado pela CLI: não existe um segundo
motor de geração. A leitura do histórico não decide a elegibilidade de uma imagem;
essa decisão continua dependendo do journal e das evidências locais.

## Validação e geração

1. A planilha é lida sem salvar para montar a conferência. Dentro de cada
   conferência, seleção e validação compartilham o mesmo DataFrame e journal.
2. Conferir seleção e abrir a confirmação paga usam a validação existente.
3. A confirmação revalida os dados e exige uma nova confirmação se o plano mudou.
4. O início revalida, congela a seleção, as saídas e os hashes das referências.
5. O worker executa em sequência, preservando a trava e o registro antes da API.
6. Arquivos e histórico são persistidos antes de publicar o encerramento.

Não há cache persistente do Excel nem reutilização de uma validação antiga ao
gerar. A interface não inclui mais o modal técnico de Conferir campanha.
O endpoint de validação continua necessário para seleção, confirmação e simulação.

## Contratos preservados

- Planilhas existentes, IDs, assinaturas e formatos de journals não foram migrados.
- CONCLUIDO e REVISAO mantêm suas regras de recuperação e proteção.
- A simulação não usa a API nem altera os estados da planilha.
- A geração paga exige confirmação e nunca começa durante um teste de interface.
- A extensão do arquivo acompanha o formato escolhido; saídas não são sobrescritas.
- Rotas de API continuam exigindo token; recursos estáticos usam uma lista
  explícita e mantêm a verificação de Host/Origin e autenticação do acesso LAN.
- O cliente OpenAI usa o destino oficial explicitamente, como a checagem de conexão.
- A embalagem Windows deriva seus arquivos web da mesma lista usada pelo servidor.

## Verificação de mudanças

```powershell
python -m pip install -r requirements-dev.txt
python -m pyflakes main.py studio.py desktop.py src scripts tests
python scripts/run_local_tests.py
python -m pip check
node --check web/studio.js
node --check web/studio-utils.js
node --check web/theme.js
node --test tests/test_studio_ui.cjs
git diff --check
```

A suíte Python bloqueia rede externa e usa diretórios temporários. As funções
de contagem e duração são verificadas também no Node sem navegador ou pacotes
adicionais. O workflow em `.github/workflows/checks.yml` repete essas verificações
no Windows quando o código for publicado; não executa campanhas nem usa chaves.

Antes de entregar um executável, `scripts/build_windows_package.py` compila e
executa o diagnóstico do próprio pacote congelado com WebView2. O diagnóstico
usa sua própria planilha, proíbe clientes externos, verifica layouts, confirmações,
teclado, histórico e interrupção. O ZIP só é gerado se esse diagnóstico passar.

Esses testes comprovam comportamento local. Qualidade visual das imagens, acesso
da conta e integração paga precisam de validação real autorizada separadamente.
