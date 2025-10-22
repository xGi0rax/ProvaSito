#!/usr/bin/env python3
import argparse
import json
import os
from datetime import datetime
from pathlib import Path
from bs4 import BeautifulSoup

# tassonomia attesa
SEZIONI = ["candidatura", "presentazione"]
TIPI = ["documenti", "verbali"]
AMBITI = ["interni", "esterni"]

# id dei blocchi = "<sezione>-<tipo>-<ambito>"
def section_id(sezione, tipo, ambito):
    return f"{sezione}-{tipo}-{ambito}"

def humanize(name: str) -> str:
    base = os.path.splitext(os.path.basename(name))[0]
    return base.replace("_", " ").strip()

def collect_entries(root: Path, base_url: str):
    entries = []
    for dirpath, _, files in os.walk(root):
        for f in files:
            if not f.lower().endswith(".pdf"):
                continue
            full = Path(dirpath) / f
            rel = full.relative_to(root)  # p.es. candidatura/verbali/interni/VI-....pdf
            parts = rel.parts
            if len(parts) < 4:
                continue
            sezione, tipo, ambito = parts[0], parts[1], parts[2]
            if sezione not in SEZIONI or tipo not in TIPI or ambito not in AMBITI:
                continue

            url = f"{base_url.rstrip('/')}/" + rel.as_posix()
            mtime = datetime.fromtimestamp(full.stat().st_mtime)

            entries.append({
                "label": humanize(f),
                "path": rel.as_posix(),
                "url": url,
                "sezione": sezione,
                "tipo": tipo,
                "ambito": ambito,
                "date": mtime.strftime("%Y-%m-%d"),
                "timestamp": int(mtime.timestamp()),
            })
    # ordina per gruppo, poi data desc
    entries.sort(key=lambda e: (e["sezione"], e["tipo"], e["ambito"], -e["timestamp"]))
    return entries

def build_ul_inner(entries_for_group):
    if not entries_for_group:
        return "<li>Nessun documento trovato per questa sezione.</li>"
    items = []
    for e in entries_for_group:
        items.append(
            f'<li><a href="{e["url"]}">{e["label"]}</a>'
            f' <span class="doc-date" style="opacity:.7;margin-left:.5rem;">{e["date"]}</span></li>'
        )
    return "\n".join(items)

def replace_between_markers(html: str, block_id: str, new_content: str) -> str:
    begin = f"<!-- AUTO-GEN:BEGIN {block_id} -->"
    end   = f"<!-- AUTO-GEN:END {block_id} -->"
    if begin in html and end in html:
        start = html.index(begin) + len(begin)
        stop  = html.index(end)
        return html[:start] + "\n" + new_content + "\n" + html[stop:]

    # fallback: <ul id="autolist-<block_id>">...</ul>
    soup = BeautifulSoup(html, "html.parser")
    container = soup.find(id=f"autolist-{block_id}")
    if container:
        container.clear()
        frag = BeautifulSoup(new_content, "html.parser")
        for child in frag.contents:
            container.append(child)
        return str(soup)

    return html  # nessuna modifica

def update_index(index_path: Path, entries):
    # raggruppa
    grouped = {}
    for e in entries:
        k = (e["sezione"], e["tipo"], e["ambito"])
        grouped.setdefault(k, []).append(e)

    html = index_path.read_text(encoding="utf-8")

    # garantisci che tutte le 8 liste vengano toccate (anche se vuote)
    for sezione in SEZIONI:
        for tipo in TIPI:
            for ambito in AMBITI:
                block_id = section_id(sezione, tipo, ambito)
                group_entries = grouped.get((sezione, tipo, ambito), [])
                new_inner = build_ul_inner(group_entries)
                html = replace_between_markers(html, block_id, new_inner)

    index_path.write_text(html, encoding="utf-8")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True, help="Radice documenti (es. documenti/cartella_con_documenti)")
    ap.add_argument("--index", required=True, help="Percorso a index.html")
    ap.add_argument("--base-url", required=True, help="Prefisso URL per i link")
    ap.add_argument("--manifest", required=True, help="Dove scrivere il manifest json")
    args = ap.parse_args()

    root = Path(args.root)
    entries = collect_entries(root, args.base_url)

    # manifest (utile per debug/ricerche future)
    manifest_path = Path(args.manifest)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")

    # aggiorna html
    update_index(Path(args.index), entries)
    print("Index aggiornato.")

if __name__ == "__main__":
    main()
