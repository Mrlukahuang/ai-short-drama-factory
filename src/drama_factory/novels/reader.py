from __future__ import annotations
import io
import re
import zipfile
from html.parser import HTMLParser
from pathlib import PurePosixPath
from xml.etree import ElementTree as ET

SUPPORTED_EXTENSIONS = {".txt", ".md", ".docx", ".pdf", ".epub"}
MAX_UPLOAD_BYTES = 20 * 1024 * 1024
MAX_EXPANDED_EPUB_BYTES = 60 * 1024 * 1024
MAX_TEXT_CHARS = 3_000_000

class ReaderError(ValueError):
    pass

class _HTMLText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.ignore = 0
    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "svg"}:
            self.ignore += 1
        elif tag in {"p", "div", "h1", "h2", "h3", "li", "br"}:
            self.parts.append("\n")
    def handle_endtag(self, tag):
        if tag in {"script", "style", "svg"}:
            self.ignore = max(self.ignore - 1, 0)
        elif tag in {"p", "div", "h1", "h2", "h3", "li"}:
            self.parts.append("\n")
    def handle_data(self, data):
        if not self.ignore:
            self.parts.append(data)
    def text(self):
        return "".join(self.parts)


def _from_epub(raw: bytes) -> str:
    """Read EPUB spine order, avoiding path extraction and large zip expansion."""
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            if sum(i.file_size for i in archive.infolist()) > MAX_EXPANDED_EPUB_BYTES:
                raise ReaderError("EPUB decompressed size exceeds limit")
            container = ET.fromstring(archive.read("META-INF/container.xml"))
            roots = [x.attrib.get("full-path") for x in container.iter() if x.tag.endswith("rootfile")]
            if not roots or not roots[0]:
                raise ReaderError("EPUB is missing its OPF package")
            opf_path = roots[0]
            opf = ET.fromstring(archive.read(opf_path))
            manifest = {x.attrib.get("id"): x.attrib.get("href") for x in opf.iter() if x.tag.endswith("item")}
            spine = [x.attrib.get("idref") for x in opf.iter() if x.tag.endswith("itemref")]
            base = PurePosixPath(opf_path).parent
            sections: list[str] = []
            for idref in spine:
                href = manifest.get(idref)
                if not href:
                    continue
                item = str(base / href.split("#")[0])
                if item not in archive.namelist():
                    continue
                parser = _HTMLText()
                parser.feed(archive.read(item).decode("utf-8", errors="replace"))
                value = parser.text().strip()
                if value:
                    sections.append(value)
            if not sections:
                raise ReaderError("EPUB has no readable spine content")
            return "\n\n".join(sections)
    except (zipfile.BadZipFile, KeyError, ET.ParseError) as exc:
        raise ReaderError(f"Invalid EPUB: {exc}") from exc


def extract_text(raw: bytes, ext: str) -> str:
    ext = ext.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise ReaderError(f"Unsupported file format: {ext}")
    if len(raw) > MAX_UPLOAD_BYTES:
        raise ReaderError("Upload exceeds 20 MiB limit")
    try:
        if ext in {".txt", ".md"}:
            try:
                text = raw.decode("utf-8-sig")
            except UnicodeDecodeError:
                text = raw.decode("gb18030")
        elif ext == ".docx":
            from docx import Document
            doc = Document(io.BytesIO(raw))
            text = "\n".join(p.text for p in doc.paragraphs)
        elif ext == ".pdf":
            import fitz
            with fitz.open(stream=raw, filetype="pdf") as doc:
                if len(doc) > 1500:
                    raise ReaderError("PDF page count exceeds safety limit")
                text = "\n".join(page.get_text(sort=True) for page in doc)
        else:
            text = _from_epub(raw)
    except ImportError as exc:
        raise ReaderError("Install the 'readers' extra for DOCX/PDF support") from exc
    except ReaderError:
        raise
    except Exception as exc:
        raise ReaderError(f"Could not read {ext} file: {exc}") from exc
    if len(text) > MAX_TEXT_CHARS:
        raise ReaderError("Extracted text exceeds 3 million characters")
    text = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not text:
        raise ReaderError("No machine-readable text found; scanned PDFs require separately approved OCR")
    return text

CHAPTER_RE = re.compile(r"(?m)^\s*((?:第[零〇一二三四五六七八九十百千万两0-9]+[章节回卷]|Chapter\s+\d+)[^\n]{0,65})\s*$", re.IGNORECASE)

def split_chapters(text: str) -> list[dict]:
    """Deterministic chapter index. Not an episode adaptation algorithm."""
    hits = list(CHAPTER_RE.finditer(text))
    if not hits:
        return [{"ordinal": 1, "title": "全文（未检测到章节标题）", "start_offset": 0,
                 "end_offset": len(text), "excerpt": text[:140]}]
    parts: list[dict] = []
    if hits[0].start() > 0 and text[:hits[0].start()].strip():
        parts.append({"ordinal": 1, "title": "序章 / 前言", "start_offset": 0,
                      "end_offset": hits[0].start(), "excerpt": text[:140]})
    for i, match in enumerate(hits):
        start = match.start()
        end = hits[i + 1].start() if i + 1 < len(hits) else len(text)
        parts.append({"ordinal": len(parts) + 1, "title": match.group(1).strip(),
                      "start_offset": start, "end_offset": end, "excerpt": text[start:min(end,start+140)].strip()})
    return parts
