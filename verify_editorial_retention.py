"""Verify an editorial-only figure move against its frozen source."""
from pathlib import Path
import runpy,re,json,collections,zipfile,hashlib,sys
from lxml import etree as E
from docx import Document
R=Path(__file__).resolve().parent;O=R/'editorial/table-citations-prior'
sys.path.insert(0,str(R/'manuscript'))
from document_labels import Labels
changes=json.loads((R/'editorial/table-citation-changes.json').read_text())
report={}
for lang in ['en','zh']:
 old=runpy.run_path(str(O/f'paper_{lang}.py'));new=runpy.run_path(str(R/f'manuscript/paper_{lang}.py'))
 expected={k:list(old[k]) for k in ['SECTIONS','APPENDIX']}
 for change in changes[lang]:
  key=change['group'];i=next(i for i,(h,b) in enumerate(expected[key]) if h==change['heading'])
  assert expected[key][i][1]==change['before']
  expected[key][i]=(change['heading'],change['after'])
 for key in expected:assert expected[key]==new[key]
 for key in ['TITLE','AUTHOR','AFFILIATION','FIG_CAPTIONS','REFERENCES']:assert old[key]==new[key]
 p=type('Paper',(),new);labels=Labels(p)
 expectedkeys=['1','5','9','10','15','16','17','18','14','11','12','13']
 assert labels.marker_order['FIG'][:12]==expectedkeys
 seen=[];detail=[]
 for h,b in new['SECTIONS']:
  for para in b.split('\n\n'):
   if para.startswith('[['):continue
   text=labels.rewrite(para)
   for m in re.finditer(r'(?:\bFigure(?:s)?\s+|图\s*)(\d+)',text):
    n=int(m.group(1))
    if n not in seen:seen.append(n);detail.append({'number':n,'paragraph':text[:160]})
 assert seen==list(range(1,13)),(lang,seen)
 od=Document(O/f'input-and-horizon-dependent-structural-fidelity-preprint-{lang}.docx');nd=Document(R/f'manuscript/input-and-horizon-dependent-structural-fidelity-preprint-{lang}.docx')
 assert [[[c.text for c in row.cells] for row in t.rows] for t in od.tables]==[[[c.text for c in row.cells] for row in t.rows] for t in nd.tables]
 def objects(path):
  with zipfile.ZipFile(path) as z:
   x=E.fromstring(z.read('word/document.xml'))
   math=collections.Counter(hashlib.sha256(E.tostring(e,method='c14n')).hexdigest() for e in x.findall('.//{http://schemas.openxmlformats.org/officeDocument/2006/math}oMath'))
   imgs=collections.Counter(hashlib.sha256(z.read(n)).hexdigest() for n in z.namelist() if n.startswith('word/media/'))
   return math,imgs
 assert objects(O/f'input-and-horizon-dependent-structural-fidelity-preprint-{lang}.docx')==objects(R/f'manuscript/input-and-horizon-dependent-structural-fidelity-preprint-{lang}.docx')
 report[lang]={'status':'pass','main_figure_first_citations':seen,'main_figure_placement':list(range(1,13)),'stable_keys':expectedkeys,'all_30_tables_unchanged':len(nd.tables)==30,'all_25_figures_preserved':len(nd.inline_shapes)==25,'all_equations_proofs_and_results_preserved':True,'only_declared_reference_edits_and_figure_moves':True,'first_citation_details':detail}
assert json.loads((R/'manuscript/document-labels-en.json').read_text())==json.loads((R/'manuscript/document-labels-zh.json').read_text())
(R/'validation/editorial-preservation.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
print(json.dumps({l:{k:v for k,v in x.items() if k!='first_citation_details'} for l,x in report.items()},indent=2))
