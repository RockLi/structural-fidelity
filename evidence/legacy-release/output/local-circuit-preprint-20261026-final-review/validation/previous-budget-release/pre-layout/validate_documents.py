#!/usr/bin/env python3
"""Read-only bilingual source, citation and native Word-structure audit."""
import argparse,ast,collections,hashlib,json,re,unicodedata,zipfile
from pathlib import Path
from xml.etree import ElementTree as E
from types import SimpleNamespace
from document_labels import Labels, EQUATION_LABELS
p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=Path(__file__).resolve().parent);p.add_argument('--baseline',type=Path);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
NS={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main','m':'http://schemas.openxmlformats.org/officeDocument/2006/math','wp':'http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing'}
def src(path):return {n.targets[0].id:ast.literal_eval(n.value) for n in ast.parse(path.read_text()).body if isinstance(n,ast.Assign)}
def text(node):return ''.join(n.text or '' for n in node.iter() if n.tag in [f'{{{NS[k]}}}t' for k in ['w','m']])
def norm(s):return ''.join(c for c in unicodedata.normalize('NFKD',s) if not unicodedata.combining(c) and not c.isspace() and c not in '_^')
def cites(s, maximum=18):
 values=[]
 for group in re.findall(r'\[(\d+(?:[,–-]\d+)*)\]',s):
  nums=[]
  for token in group.split(','):
   ends=re.split('[–-]',token);nums.extend(range(int(ends[0]),int(ends[-1])+1))
  if all(1<=n<=maximum for n in nums):values.extend(nums)
 return values
source={x:src(a.root/f'paper_{x}.py') for x in ['en','zh']};old={x:src(a.baseline/f'paper_{x}.py') for x in ['en','zh']} if a.baseline else None;refs=source['en']['REFERENCES'];assert [int(re.match(r'\[(\d+)\]',r)[1]) for r in refs]==list(range(1,len(refs)+1))
if old:assert refs[:len(old['en']['REFERENCES'])]==old['en']['REFERENCES']
report={'status':'pass','references':len(refs),'previous_edition_comparison':bool(old),'languages':{}};marker_sets=[]
for lang,s in source.items():
 labels=Labels(SimpleNamespace(**s))
 if old:assert all(s[k]==old[lang][k] for k in ['AUTHOR','AFFILIATION'])
 blocks=[v for _,b in s['SECTIONS']+s['APPENDIX'] for v in b.split('\n\n')]
 source_text='\n'.join(blocks);citations=cites(source_text,len(refs));assert list(dict.fromkeys(citations))==list(range(1,len(refs)+1))
 markers={k:re.findall(r'\[\['+k+r':([^]]+)\]\]',source_text) for k in ['EQ','FIG','TABLE']};marker_sets.append(markers)
 assert set(markers['FIG'])==set([str(n) for n in range(1,14)]+['S1','S2','S3','S4','S5','S6','S7'])
 assert len(markers['FIG'])==len(set(markers['FIG']))
 assert set(markers['TABLE'])==set([str(n) for n in range(1,12)]+['A1','A2','B1'])
 assert len(markers['TABLE'])==len(set(markers['TABLE']))
 path=a.root/f'local-circuit-aggregation-preprint-{lang}.docx'
 with zipfile.ZipFile(path) as z:doc=E.fromstring(z.read('word/document.xml'))
 body=doc.find('w:body',NS);paras=[text(n) for n in body.findall('w:p',NS)];assert not any('[[' in t for t in paras)
 j=paras.index('References' if lang=='en' else '参考文献');k=paras.index(s['APPENDIX'][0][0],j+1)
 assert [t for t in paras[j+1:k] if t.strip()]==refs
 assert cites('\n'.join(paras[:j]+paras[k:]),len(refs))==citations
 actual={norm(t) for t in paras}
 missing=[b for b in blocks if not b.startswith('[[') and norm(labels.rewrite(b)) not in actual]
 assert not missing,missing
 assert all(norm(labels.rewrite(t)) in actual for t in s['FIG_CAPTIONS'].values())
 eq=[]
 for n in body.findall('w:p',NS):
  label=re.search(r'(\(\d+[abc]?\))$',text(n))
  if label and n.find('m:oMath',NS) is not None:eq.append(label[1])
 expected=[labels.equation(old) for key in markers['EQ'] for old in EQUATION_LABELS[key]];assert eq==expected,eq
 # A single OMML node must remain wrapped as a node, not be iterated into
 # m:e/m:sub children directly inside a fraction. Text extraction alone
 # cannot catch the empty-box rendering caused by that malformed structure.
 for fraction in doc.findall('.//m:f',NS):
  for name in ['num','den']:
   child=fraction.find('m:'+name,NS);assert child is not None and len(child)>0
   assert all(n.tag not in [f'{{{NS["m"]}}}e',f'{{{NS["m"]}}}sub',f'{{{NS["m"]}}}sup'] for n in child)
   assert text(child).strip()
 predictor=next(n for n in body.findall('w:p',NS) if text(n).endswith(labels.equation('(10)')))
 fraction=predictor.find('.//m:f',NS);assert fraction is not None
 assert text(fraction.find('m:num',NS))=='‖ΔGgU5‖F'
 assert text(fraction.find('m:den',NS))=='‖G0U5‖F'
 tables=body.findall('w:tbl',NS);figures=doc.findall('.//wp:inline',NS);assert len(tables)==len(markers['TABLE']) and len(figures)==len(markers['FIG'])
 report['languages'][lang]={'markers':markers,'reader_labels':labels.report(),'citation_counts':dict(collections.Counter(citations)),'every_source_paragraph_and_caption_present':True,'native_display_equation_labels':eq,'tables':len(tables),'figures':len(figures),'docx_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'source_sha256':hashlib.sha256((a.root/f'paper_{lang}.py').read_bytes()).hexdigest()}
assert marker_sets[0]==marker_sets[1]
assert report['languages']['en']['citation_counts']==report['languages']['zh']['citation_counts']
a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print('PASS: both languages; citations, sequential labels, native equations, tables and figures; all source paragraphs and captions retained.')
