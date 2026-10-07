"""Copy the approved local prototype logo without fetching external assets."""
from html.parser import HTMLParser
from pathlib import Path


class LogoParser(HTMLParser):
    logo = None

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == "img" and "company-logo" in values.get("class", ""):
            self.logo = values["src"]


if __name__ == "__main__":
    prototype = Path(r"C:\Users\Pichau\Documents\Codex\2026-10-06\me-da\outputs\afirma-studio-prototipo-atual.html")
    parser = LogoParser()
    parser.feed(prototype.read_text("utf-8"))
    if not parser.logo:
        raise SystemExit("Logo não encontrada no protótipo.")
    target = Path(__file__).resolve().parents[1] / "web" / "studio.html"
    target.write_text(target.read_text("utf-8").replace("__BRAND_LOGO__", parser.logo), encoding="utf-8")
    print("Identidade visual local do protótipo incorporada.")
