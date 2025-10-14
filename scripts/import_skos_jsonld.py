from __future__ import annotations
import argparse, json, sys, re
from pathlib import Path
from typing import Dict, List, Optional, Set
from rdflib import Graph, URIRef, Literal
from rdflib.namespace import RDF, SKOS

Lang = str

# SKOS extras que vamos a mapear también
SKOS_SCOPE_NOTE = SKOS.scopeNote
SKOS_NOTE       = SKOS.note
SKOS_EXAMPLE    = SKOS.example
SKOS_EXACT      = SKOS.exactMatch
SKOS_CLOSE      = SKOS.closeMatch
SKOS_RELATED    = SKOS.related

def clean_notation(code: str) -> str:
    return re.sub(r"[^A-Za-z0-9]", "", str(code or ""))

def collect_lang_literals(g: Graph, s: URIRef, p, langs: List[Lang]) -> Dict[Lang, List[str]]:
    out: Dict[Lang, List[str]] = {l: [] for l in langs}
    out["_all"] = []
    for o in g.objects(s, p):
        if isinstance(o, Literal):
            if o.language in langs:
                out[o.language].append(str(o))
            else:
                out["_all"].append(str(o))
        else:
            out["_all"].append(str(o))
    for k in list(out.keys()):
        out[k] = sorted({x for x in out[k] if x})
    return out

def pick_one(g: Graph, s: URIRef, p, langs: List[Lang], fallback: str="") -> Dict[Lang, str]:
    lab = collect_lang_literals(g, s, p, langs)
    ans = {}
    for l in langs:
        ans[l] = (lab[l][0] if lab[l] else (lab["_all"][0] if lab.get("_all") else fallback))
    return ans

def main():
    ap = argparse.ArgumentParser(description="Importa SKOS JSON-LD → taxonomy.json (bilingüe, datos completos).")
    ap.add_argument("--in", dest="inp", required=True, help="Ruta JSON-LD SKOS")
    ap.add_argument("--out", dest="out", required=True, help="Salida taxonomy.json")
    ap.add_argument("--langs", default="es,en", help="Idiomas por coma (default: es,en)")
    ap.add_argument("--scheme", default=None, help="URI de skos:ConceptScheme para filtrar (opcional)")
    args = ap.parse_args()

    langs = [x.strip() for x in args.langs.split(",") if x.strip()] or ["es","en"]

    src = Path(args.inp)
    if not src.exists():
        print(f"ERROR: no existe {src}", file=sys.stderr); sys.exit(1)

    g = Graph(); g.parse(src.as_posix(), format="json-ld")
    concepts: Set[URIRef] = set(g.subjects(RDF.type, SKOS.Concept))
    if args.scheme:
        scheme = URIRef(args.scheme)
        concepts = {c for c in concepts if (c, SKOS.inScheme, scheme) in g}
    if not concepts:
        print("ERROR: sin skos:Concept (o filtraste todo).", file=sys.stderr); sys.exit(1)

    # Mapa uri->notation y notation->uri
    uri2notation: Dict[URIRef, str] = {}
    notation2uri: Dict[str, URIRef] = {}

    # Recolecta etiquetas, notas, matches, relaciones
    pref, alt, hidden, definition, scopeNote, note, example = {}, {}, {}, {}, {}, {}, {}
    exactMatch, closeMatch, related = {}, {}, {}
    inScheme = {}

    for c in concepts:
        nots = [str(o) for o in g.objects(c, SKOS.notation)]
        notation = (nots[0].strip() if nots else str(c))
        uri2notation[c] = notation
        notation2uri[notation] = c

        pref[c]  = pick_one(g, c, SKOS.prefLabel, langs, fallback=notation)
        alt[c]   = collect_lang_literals(g, c, SKOS.altLabel, langs)
        hidden[c]= collect_lang_literals(g, c, SKOS.hiddenLabel, langs)
        definition[c] = pick_one(g, c, SKOS.definition, langs, fallback="")
        scopeNote[c]  = pick_one(g, c, SKOS_SCOPE_NOTE, langs, fallback="")
        note[c]       = pick_one(g, c, SKOS_NOTE, langs, fallback="")
        example[c]    = collect_lang_literals(g, c, SKOS_EXAMPLE, langs)

        exactMatch[c] = sorted({str(o) for o in g.objects(c, SKOS_EXACT)})
        closeMatch[c] = sorted({str(o) for o in g.objects(c, SKOS_CLOSE)})
        related[c]    = sorted({str(o) for o in g.objects(c, SKOS_RELATED)})
        inScheme[c]   = sorted({str(o) for o in g.objects(c, SKOS.inScheme)})

    # Relaciones broader/narrower por URI
    broader, narrower = {}, {}
    for c in concepts:
        broader[c] = [b for b in g.objects(c, SKOS.broader) if b in concepts]
        narrower[c]= [n for n in g.objects(c, SKOS.narrower) if n in concepts]

    # Construir path por idioma usando padres detectados (dinámico: prefijos de notation que existan como conceptos)
    all_clean = {clean_notation(uri2notation[c]): uri2notation[c] for c in concepts}

    def parent_notations(c: URIRef) -> List[str]:
        me = uri2notation[c]; mc = clean_notation(me)
        parents = []
        for i in range(1, len(mc)):
            pref = mc[:i]
            if pref in all_clean:
                parents.append(all_clean[pref])
        # dedup manteniendo orden
        seen=set(); out=[]
        for p in parents:
            if p not in seen: seen.add(p); out.append(p)
        return out

    out = []
    for c in concepts:
        nid = uri2notation[c]
        chain = parent_notations(c) + [nid]
        path_lang = {}
        for l in langs:
            labels=[]
            for nt in chain:
                cu = notation2uri.get(nt, c)
                lab = pref.get(cu, {}).get(l) or nt
                if not labels or labels[-1] != lab:
                    labels.append(lab)
            path_lang[l] = labels

        out.append({
            "id": nid,
            "uri": str(c),
            "inScheme": inScheme.get(c, []),
            "prefLabel": {l: pref.get(c, {}).get(l) or nid for l in langs},
            "altLabel":  {l: alt.get(c, {}).get(l, []) for l in langs},
            "hiddenLabel": {l: hidden.get(c, {}).get(l, []) for l in langs},
            "definition": {l: (definition.get(c, {}).get(l) or None) for l in langs},
            "scopeNote":  {l: (scopeNote.get(c, {}).get(l) or None) for l in langs},
            "note":       {l: (note.get(c, {}).get(l) or None) for l in langs},
            "example":    {l: example.get(c, {}).get(l, []) for l in langs},
            "path": path_lang,
            "broader": [uri2notation[b] for b in broader.get(c, [])],
            "narrower": [uri2notation[n] for n in narrower.get(c, [])],
            "exactMatch": exactMatch.get(c, []),
            "closeMatch": closeMatch.get(c, []),
            "related": related.get(c, []),
        })

    out.sort(key=lambda x: x["id"])
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"OK: escrito {args.out} con {len(out)} conceptos; langs={langs}")
