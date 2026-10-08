"""Rebuild the read-only Studio log for the completed three-image pilot."""
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

from openpyxl import load_workbook
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.execution_state import digest
PILOT = ROOT / "output" / "piloto-real-tabela-2026-10-08"
RATES = {"image_input": 8, "text_input": 5, "image_output": 30}  # USD / 1M tokens; estimate only.


def stamp(seconds):
    return datetime.fromtimestamp(seconds, timezone.utc).isoformat(timespec="seconds")


def build():
    queue = PILOT / "campanha-real-3.xlsx"
    metrics = json.loads((PILOT / "api-metrics-resume.json").read_text("utf-8"))
    result = json.loads((PILOT / "result-resume.json").read_text("utf-8"))
    journal = json.loads(Path(str(queue) + ".state.json").read_text("utf-8"))
    workbook = load_workbook(queue, read_only=True, data_only=True)
    try:
        rows = list(workbook["Fila_Geracao"].values)
        names = dict(zip(rows[0], range(len(rows[0]))))
        items = {str(row[names["ID"]]): row for row in rows[1:] if row[names["ID"]] is not None}
    finally:
        workbook.close()
    events, lines = [], ["# Log detalhado — piloto real de 3 imagens", "",
        "Horários em UTC. Duração total da retomada: **56,217 s**; três chamadas à API bem-sucedidas.",
        "O primeiro envio anterior foi rejeitado por autenticação HTTP 401 e não integra os tempos nem a estimativa abaixo.",
        "O painel de faturamento ainda não confirmou o valor cobrado.", ""]
    totals = dict(image_input=0, text_input=0, image_output=0)
    for metric in metrics:
        key = str(metric["index"])
        row = items[key]
        usage = metric["usage"]
        tokens = dict(image_input=usage["input_tokens_details"]["image_tokens"],
                      text_input=usage["input_tokens_details"]["text_tokens"],
                      image_output=usage["output_tokens_details"]["image_tokens"])
        for name, value in tokens.items():
            totals[name] += value
        record = journal[key]
        output = Path(record["outputs"][0])
        with Image.open(output) as image:
            dimensions = f"{image.width} × {image.height}"
        if digest(output) != record["hashes"][str(output)]:
            raise ValueError(f"Hash da saída não corresponde ao histórico: ID {key}")
        started = metric["started_at"]
        elapsed = metric["elapsed_seconds"]
        name = str(row[names["Prompt_Variacao"]]).split("Nome: ")[-1].split(",")[0].strip()
        if not name or len(name) > 80:
            name = output.stem
        events.extend([{"at": stamp(started), "type": "item_start", "id": key},
                       {"at": stamp(started + elapsed), "type": "item_end", "id": key,
                        "status": "CONCLUIDO", "message": "Imagem validada e registrada.",
                        "elapsed_seconds": elapsed, "request_id": metric["request_id"],
                        "usage": tokens, "output": str(output), "bytes": output.stat().st_size,
                        "dimensions": dimensions, "sha256": digest(output)}])
        lines += [f"## ID {key} — {name}", "",
                  f"- Início da chamada: {stamp(started)}; duração: **{elapsed:.3f} s**.",
                  f"- Estado: {row[names['Status']]}; tentativas da tarefa: {record['task_attempts']}; chamadas API acumuladas: {record['api_attempts']}.",
                  f"- Request ID: `{metric['request_id']}`.",
                  f"- Tokens: imagem de entrada {tokens['image_input']}; texto de entrada {tokens['text_input']}; imagem de saída {tokens['image_output']}.",
                  f"- Arquivo: `{output.name}` ({dimensions}, {output.stat().st_size:,} bytes); SHA-256 `{digest(output)}`.", ""]
    estimate = sum(totals[k] * rate for k, rate in RATES.items()) / 1_000_000
    lines += ["## Totais", "", f"- Tempo da retomada: **{result['elapsed_seconds']:.3f} s**; chamadas bem-sucedidas: {result['api_calls']}; imagens: {len(result['outputs'])}.",
              f"- Tokens: {totals['image_input']} de imagem de entrada; {totals['text_input']} de texto de entrada; {totals['image_output']} de imagem de saída.",
              f"- Custo **estimado**: US$ {estimate:.6f}, calculado com tarifas de US$ 8 / 5 / 30 por milhão de tokens, respectivamente. Não é cobrança confirmada.",
              "- Reexecução de conferência: zero novas chamadas; arquivos originais preservados.", ""]
    report = {"version": 1, "source": "pilot_artifacts", "started_at": stamp(metrics[0]["started_at"]),
              "finished_at": stamp(metrics[-1]["started_at"] + metrics[-1]["elapsed_seconds"]),
              "elapsed_seconds": result["elapsed_seconds"], "mode": "real", "status": "Finalizado",
              "planned_items": 3, "planned_images": 3, "settings": journal["1"]["execution"]["settings"],
              "events": events, "result": result["summary"], "usage_totals": totals,
              "estimated_cost_usd": round(estimate, 6), "billing_confirmed": False}
    Path(str(queue) + ".studio-run.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    destination = PILOT / "LOG_DETALHADO.md"
    destination.write_text("\n".join(lines), encoding="utf-8")
    return destination


if __name__ == "__main__":
    print(build())
