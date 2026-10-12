from io import BytesIO
from zipfile import ZipFile
from drama_factory.novels.reader import extract_text, split_chapters, ReaderError


def test_epub_spine_order():
    buf = BytesIO()
    with ZipFile(buf,'w') as z:
        z.writestr('META-INF/container.xml', '''<container xmlns="urn:oasis:names:tc:opendocument:xmlns:container"><rootfiles><rootfile full-path="OEBPS/content.opf"/></rootfiles></container>''')
        z.writestr('OEBPS/content.opf', '''<package xmlns="http://www.idpf.org/2007/opf"><manifest><item id="a" href="a.xhtml"/><item id="b" href="b.xhtml"/></manifest><spine><itemref idref="b"/><itemref idref="a"/></spine></package>''')
        z.writestr('OEBPS/a.xhtml','<html><body><p>第二章 后来的故事</p><p>第二段</p></body></html>')
        z.writestr('OEBPS/b.xhtml','<html><body><p>第一章 先前的故事</p></body></html>')
    text = extract_text(buf.getvalue(),'.epub')
    assert text.index('第一章') < text.index('第二章')
    assert len(split_chapters(text)) >= 2


def test_pdf_text_extraction():
    import fitz
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((30,30),'Chapter 1 example')
    raw=doc.tobytes()
    doc.close()
    assert 'Chapter 1 example' in extract_text(raw,'.pdf')


def test_scanned_pdf_without_text_fails_cleanly():
    import pytest
    import fitz
    doc = fitz.open()
    doc.new_page()
    raw=doc.tobytes()
    doc.close()
    with pytest.raises(ReaderError, match='machine-readable'):
        extract_text(raw,'.pdf')
