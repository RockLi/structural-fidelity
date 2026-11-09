"""Build the bilingual scientific manuscript as editable DOCX with native Word math."""
from pathlib import Path
from copy import deepcopy
import csv, re, json
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import qn, nsdecls
from paper_en import TITLE as TITLE_EN


ROOT=Path(__file__).resolve().parent
DEST=ROOT/'preprint-en.docx'
doc=Document()
# The library starter contains theme fonts and a blue title rule: clear them.
for node in doc.styles.element.iter():
    if node.tag==qn('w:rFonts'):
        for key in list(node.attrib):
            if 'theme' in key.lower():del node.attrib[key]
    if node.tag in (qn('w:pBdr'),):node.getparent().remove(node)
sec=doc.sections[0]
sec.page_width=Inches(8.2677);sec.page_height=Inches(11.6929)
sec.top_margin=sec.bottom_margin=Inches(.8)
sec.left_margin=sec.right_margin=Inches(.85)
sec.header_distance=sec.footer_distance=Inches(.35)
WIDTH=6.56
for name in ['Normal','Title','Subtitle','Heading 1','Heading 2','Heading 3','Caption']:
    st=doc.styles[name];st.font.name='Times New Roman';st.font.color.rgb=RGBColor(0,0,0)
    st.element.get_or_add_rPr().get_or_add_rFonts().set(qn('w:eastAsia'),'Songti SC')
normal=doc.styles['Normal'];normal.font.size=Pt(11)
normal.paragraph_format.line_spacing=1.12;normal.paragraph_format.space_after=Pt(6)
normal.paragraph_format.widow_control=True
for name,size in [('Title',19),('Subtitle',11),('Heading 1',13),('Heading 2',11.5),('Caption',9.5)]:
    doc.styles[name].font.size=Pt(size)
for name in ['Heading 1','Heading 2']:
    doc.styles[name].font.bold=True;doc.styles[name].paragraph_format.space_before=Pt(12)
    doc.styles[name].paragraph_format.space_after=Pt(6)
    doc.styles[name].paragraph_format.keep_with_next=True
doc.styles['Caption'].font.italic=False
doc.styles['Caption'].font.bold=False
doc.styles['Subtitle'].font.italic=False
doc.styles['Title'].font.bold=True
doc.styles['Caption'].paragraph_format.line_spacing=1.05
doc.styles['Caption'].paragraph_format.space_after=Pt(8)
settings=doc.settings.element
settings.append(parse_xml('<m:mathPr xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math"><m:mathFont m:val="Cambria Math"/></m:mathPr>'))
footer=sec.footer.paragraphs[0];footer.alignment=WD_ALIGN_PARAGRAPH.CENTER
r=footer.add_run();r.font.size=Pt(9)
fld=OxmlElement('w:fldSimple');fld.set(qn('w:instr'),'PAGE');r._r.addnext(fld)
doc.core_properties.title=TITLE_EN
doc.core_properties.subject='Delay aligned aggregation in a deterministic chunk coupled spiking model'
doc.core_properties.author='Xinjun Li'
doc.core_properties.keywords='local aggregation, spiking simulation, batching, retention, reproducibility'

def p(text='',style=None,zh=False):
    pp=doc.add_paragraph(text,style)
    if zh and style is None:
        for r in pp.runs:r.font.size=Pt(10.5)
    return pp

def caption(text): return p(text,'Caption')
def table(headers,rows,widths=None):
    t=doc.add_table(rows=1,cols=len(headers));t.alignment=WD_TABLE_ALIGNMENT.CENTER;t.autofit=False
    pr=t._tbl.tblPr
    borders=OxmlElement('w:tblBorders')
    for e in ['top','left','bottom','right','insideH','insideV']:
        b=OxmlElement('w:'+e);b.set(qn('w:val'),'single');b.set(qn('w:sz'),'4');b.set(qn('w:color'),'C8CDD2');borders.append(b)
    pr.append(borders)
    margins=OxmlElement('w:tblCellMar')
    for e,n in [('top',70),('bottom',70),('left',80),('right',80)]:
        item=OxmlElement('w:'+e);item.set(qn('w:w'),str(n));item.set(qn('w:type'),'dxa');margins.append(item)
    pr.append(margins)
    trpr=t.rows[0]._tr.get_or_add_trPr();trpr.append(OxmlElement('w:tblHeader'))
    for j,s in enumerate(headers): t.rows[0].cells[j].text=str(s)
    for row in rows:
        cc=t.add_row().cells
        for j,s in enumerate(row):cc[j].text=str(s)
    for i,row in enumerate(t.rows):
        row._tr.get_or_add_trPr().append(OxmlElement('w:cantSplit'))
        for j,c in enumerate(row.cells):
            if widths:c.width=Inches(widths[j])
            c.vertical_alignment=WD_CELL_VERTICAL_ALIGNMENT.CENTER
            if i==0:
                shade=OxmlElement('w:shd');shade.set(qn('w:fill'),'F0F2F4');c._tc.get_or_add_tcPr().append(shade)
            for pp in c.paragraphs:
                pp.paragraph_format.space_after=Pt(0);pp.paragraph_format.line_spacing=1.05
                for rr in pp.runs:rr.font.size=Pt(9);rr.bold=(i==0)
    if widths:
        for col,w in zip(t.columns,widths):col.width=Inches(w)
    p().paragraph_format.space_after=Pt(0)
    return t

# Native OMML: fractions, scripts and sums remain editable in Word.
def mr(s):
    e=OxmlElement('m:r');t=OxmlElement('m:t');t.text=s;t.set(qn('xml:space'),'preserve');e.append(t);return e
def seq(*parts):
    nodes = []
    for part in parts:
        if isinstance(part, str):
            nodes.append(mr(part))
        elif isinstance(part, (list, tuple)):
            nodes.extend(seq(*part))
        else:
            nodes.append(part)
    return nodes
def sub(base,script):
    e=OxmlElement('m:sSub');a=OxmlElement('m:e');a.extend(seq(base));b=OxmlElement('m:sub');b.extend(seq(script));e.extend([a,b]);return e
def sup(base,script):
    e=OxmlElement('m:sSup');a=OxmlElement('m:e');a.extend(seq(base));b=OxmlElement('m:sup');b.extend(seq(script));e.extend([a,b]);return e
def frac(num,den):
    e=OxmlElement('m:f');a=OxmlElement('m:num');a.extend(seq(num));b=OxmlElement('m:den');b.extend(seq(den));e.extend([a,b]);return e
def equation(parts,label=None):
    pp=p();pp.alignment=WD_ALIGN_PARAGRAPH.CENTER;pp.paragraph_format.space_after=Pt(5)
    eq=OxmlElement('m:oMath');eq.extend(parts);pp._p.append(eq)
    if label:pp.add_run('    '+label).font.size=Pt(10)
    return pp
def eqblock(key):
    start=len(doc.paragraphs)
    if key=='neuron':
        equation(seq(sup(sub('v','i'),'+'),' = ',sub('v','i'),' + dt(−',sub('v','i'),' + ',sub('g','Ei'),' − ',sub('g','Ii'),' + ',sub('g','Li'),')'),'(1a)')
        equation(seq(sup(sub('g','qi'),'+'),' = (1 − dt)',sub('g','qi'),',     q ∈ {E, I, L}'),'(1b)')
    elif key=='states':
        equation(seq(sub('R','kq'),'[n] = ',sub('∑',seq('e∈',sub('P','kq'))),sub('w','e'),' ',sub('S','j'),'[n]'),'(2a)')
        equation(seq(sub('x','kqa'),'[n] = ',sub('d','qa'),sub('x','kqa'),'[n − 1] + (1 − ',sub('d','qa'),')',sub('R','kq'),'[n]'),'(2b)')
        equation(seq(sub('d','qa'),' = exp[−dt/max(',sub('τ','qa'),', 0.1)]'),'(2c)')
        equation(seq(sub('h','kq'),'[n] = (1 − α)',sub('h','kq'),'[n − 1] + α',sub('R','kq'),'[n]'),'(2d)')

    elif key=='modulation':
        equation(seq('c = ',frac(seq(sub('x','f'),' − h'),seq(sub('x','f'),' + h + ε')),',     s = clip(',frac(seq(sub('x','s')),seq('h + ε')),', 0, 1.5)'),'(3a)')
        equation(seq(sub('D','kq'),' = ',sub('κ','q'),'[1 − 0.03c + 0.01(s − 0.5)]',sub('R','kq')),'(3b)')
    for pp in doc.paragraphs[start:-1]:pp.paragraph_format.keep_with_next=True

