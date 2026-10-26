"""Local document import/export. Core functionality uses only the standard library."""
import html
import re
import shutil
import subprocess
import uuid
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NS = {"w": W}


def extract(path):
    path = Path(path)
    if path.stat().st_size > 10_000_000:
        raise ValueError("Input exceeds 10 MB; use a smaller text-based document")
    suffix = path.suffix.lower()
    if suffix in (".txt", ".md"):
        text = path.read_text(encoding="utf-8-sig")
    elif suffix == ".docx":
        with zipfile.ZipFile(path) as archive:
            info = archive.getinfo("word/document.xml")
            if info.file_size > 20_000_000:
                raise ValueError("DOCX document XML exceeds 20 MB")
            root = ET.fromstring(archive.read(info))
        # Tables are readable here, but complex layout order needs human review.
        text = "\n".join("".join(t.text or "" for t in p.findall(".//w:t", NS))
                         for p in root.findall(".//w:p", NS))
    elif suffix == ".pdf":
        if shutil.which("pdftotext"):
            result = subprocess.run(["pdftotext", "-layout", str(path.resolve()), "-"],
                                    capture_output=True, text=True, timeout=30, check=True)
            text = result.stdout
        else:
            try:
                from pypdf import PdfReader
            except ImportError as exc:
                raise ValueError("PDF import requires pdftotext or pypdf. Export your resume as DOCX or UTF-8 TXT instead.") from exc
            text = "\n".join(page.extract_text() or "" for page in PdfReader(path).pages)
    else:
        raise ValueError("Supported source formats: .txt, .md, .docx, .pdf")
    if not text.strip():
        raise ValueError("No text extracted. Scanned PDFs need OCR; use a text-based resume.")
    return text.strip()


def date_label(value):
    if value == "Present":
        return value
    year, month = value.split("-")
    months = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()
    return f"{months[int(month) - 1]} {year}"


def blocks(draft):
    r = draft["resume"]
    result = [("name", r["name"]), ("headline", r["headline"]),
              ("contact", " | ".join(r["contact"]))]
    if r.get("summary"):
        result += [("section", "Professional Summary"), ("body", " ".join(r["summary"]))]
    if r.get("skills"):
        result += [("section", "Skills"), ("body", " · ".join(r["skills"]))]
    result.append(("section", "Professional Experience"))
    for role in r["experience"]:
        result.append(("role", f"{role['title']} | {role['company']}"))
        dates = f"{date_label(role['start'])} – {date_label(role['end'])}"
        if role.get("location"):
            dates += " | " + role["location"]
        result.append(("dates", dates))
        result.extend(("bullet", b["text"]) for b in role["bullets"])
    for key, title in (("projects", "Projects"), ("education", "Education"), ("certifications", "Certifications")):
        if r.get(key):
            result.append(("section", title))
            result.extend(("body", text) for text in r[key])
    return result


def plain_text(items):
    return "\n".join(("- " if kind == "bullet" else "") + text for kind, text in items) + "\n"


def export_html(items):
    tags = {"name": "h1", "section": "h2", "role": "h3"}
    body = []
    for kind, text in items:
        tag = tags.get(kind, "p")
        prefix = "• " if kind == "bullet" else ""
        body.append(f'<{tag} class="{kind}">{prefix}{html.escape(text)}</{tag}>')
    return '''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Resume preview</title><style>
*{box-sizing:border-box}body{margin:0;background:#e9edf0;color:#202934;font-family:Arial,Helvetica,sans-serif}
main{width:8.5in;min-height:11in;margin:32px auto;background:white;padding:.62in .7in;box-shadow:0 8px 40px #1c2b3b17}
p{font-size:10.5pt;line-height:1.42;margin:0 0 6pt;overflow-wrap:anywhere;orphans:2;widows:2}
h1{font-size:27pt;letter-spacing:-.6pt;color:#142e43;margin:0 0 4pt;font-weight:700}
.headline{font-size:12pt;font-weight:700;margin-bottom:7pt;color:#294a60}
.contact{font-size:9.5pt;color:#46515a;margin-bottom:13pt}
h2{font-size:10.5pt;color:#142e43;margin:15pt 0 7pt;border-bottom:1px solid #bbc8d0;padding-bottom:4pt;break-after:avoid}
h3{font-size:10.5pt;margin:9pt 0 3pt;break-after:avoid}
.dates{font-size:9.5pt;color:#46515a;margin-bottom:6pt;break-after:avoid}
.bullet{padding-left:12pt;text-indent:-9pt;break-inside:avoid;margin-bottom:5pt}
.toolbar{max-width:8.5in;margin:22px auto 0;display:flex;justify-content:space-between;gap:12px;align-items:center;font:13px Arial;color:#46515a;padding:0 12px}
button{background:#17394e;border:0;color:white;padding:10px 16px;border-radius:5px;cursor:pointer}
@page{size:Letter;margin:.62in .7in}
@media print{body{background:white}main{width:auto;min-height:0;margin:0;padding:0;box-shadow:none}.toolbar{display:none}}
@media screen and (max-width:850px){main{width:calc(100% - 24px);min-height:0;padding:28px;margin:16px auto}.toolbar{flex-wrap:wrap}}
</style></head><body><div class="toolbar"><span>Resume Studio · Draft — review claims before submitting</span><button onclick="window.print()">Print / Save PDF</button></div><main>
''' + "\n".join(body) + "\n</main></body></html>"


def export_docx(items, path):
    """Write a minimal standards-based OOXML document with true bullet numbering."""
    ET.register_namespace("w", W)
    def node(parent, name, attrs=None, text=None):
        element = ET.SubElement(parent, f"{{{W}}}{name}",
                                {f"{{{W}}}{k}": str(v) for k, v in (attrs or {}).items()})
        element.text = text
        return element
    root = ET.Element(f"{{{W}}}document")
    body = node(root, "body")
    for kind, text in items:
        p = node(body, "p")
        props = node(p, "pPr")
        if kind in ("name", "headline", "section", "role", "dates"):
            node(props, "keepNext")
        node(props, "widowControl")
        if kind == "bullet":
            num = node(props, "numPr")
            node(num, "ilvl", {"val": 0})
            node(num, "numId", {"val": 1})
        if kind == "section":
            borders = node(props, "pBdr")
            node(borders, "bottom", {"val": "single", "sz": 4, "space": 4, "color": "BBC8D0"})
        node(props, "spacing", {"before": 220 if kind == "section" else 0,
                                "after": 100, "line": 270, "lineRule": "auto"})
        run = node(p, "r")
        rp = node(run, "rPr")
        node(rp, "rFonts", {"ascii": "Arial", "hAnsi": "Arial", "eastAsia": "Arial", "cs": "Arial"})
        size = {"name": 50, "headline": 24, "contact": 19, "dates": 19}.get(kind, 21)
        node(rp, "sz", {"val": size})
        if kind in ("name", "headline", "section", "role"):
            node(rp, "b")
        node(rp, "color", {"val": "142E43" if kind in ("name", "section", "headline") else "202934"})
        t = node(run, "t", text=text)
        t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    section = node(body, "sectPr")
    node(section, "pgSz", {"w": 12240, "h": 15840})
    node(section, "pgMar", {"top": 893, "bottom": 893, "left": 1008, "right": 1008, "header": 0, "footer": 0})
    content_types = '''<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/><Override PartName="/word/numbering.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.numbering+xml"/></Types>'''
    rels = '''<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>'''
    doc_rels = '''<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/numbering" Target="numbering.xml"/></Relationships>'''
    numbering = f'''<w:numbering xmlns:w="{W}"><w:abstractNum w:abstractNumId="0"><w:multiLevelType w:val="singleLevel"/><w:lvl w:ilvl="0"><w:start w:val="1"/><w:numFmt w:val="bullet"/><w:lvlText w:val="•"/><w:lvlJc w:val="left"/><w:pPr><w:tabs><w:tab w:val="num" w:pos="180"/></w:tabs><w:ind w:left="180" w:hanging="180"/></w:pPr><w:rPr><w:rFonts w:ascii="Arial" w:hAnsi="Arial"/></w:rPr></w:lvl></w:abstractNum><w:num w:numId="1"><w:abstractNumId w:val="0"/></w:num></w:numbering>'''
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, value in {"[Content_Types].xml": content_types, "_rels/.rels": rels,
                            "word/_rels/document.xml.rels": doc_rels, "word/numbering.xml": numbering}.items():
            archive.writestr(name, value)
        archive.writestr("word/document.xml", ET.tostring(root, encoding="utf-8", xml_declaration=True))


def export_pdf(html_path, output_path):
    if not shutil.which("agent-browser"):
        raise ValueError("PDF export requires agent-browser with its browser installed. Open resume.html and choose Print / Save PDF instead.")
    session = "resume-" + uuid.uuid4().hex[:12]
    command = ["agent-browser", "--session", session]
    try:
        subprocess.run(command + ["open", Path(html_path).resolve().as_uri()], check=True,
                       capture_output=True, text=True, timeout=60)
        subprocess.run(command + ["pdf", str(Path(output_path).resolve())], check=True,
                       capture_output=True, text=True, timeout=60)
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or str(exc)).strip()
        raise ValueError(f"PDF browser failed: {detail}. Rerun without --pdf and use resume.html → Print / Save PDF.") from exc
    finally:
        try:
            subprocess.run(command + ["close"], capture_output=True, timeout=15)
        except subprocess.SubprocessError:
            pass
    if not Path(output_path).exists() or Path(output_path).stat().st_size < 100:
        raise ValueError("Browser did not produce a valid PDF")


def verify_docx(items, path):
    expected = "\n".join(text for _, text in items)
    actual = extract(path)
    return {"docx_text_roundtrip": actual == expected,
            "note": "Checks exported text and reading order; does not emulate an employer's ATS."}
