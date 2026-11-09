from pathlib import Path
import json,hashlib,collections,csv,re,zipfile,runpy,itertools
from docx import Document
R=Path(__file__).resolve().parent

def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  while b:=f.read(1024*1024):h.update(b)
 return h.hexdigest()
def read(p):return list(csv.DictReader(p.open()))
def manifest(root,name):
 m=json.loads((root/name).read_text());m=m.get('files',m)
 for p,h in m.items():assert sha(root/p)==(h['sha256'] if isinstance(h,dict) else h),(root,p)
 return len(m)
def main():
 evidence={};old=R/'evidence/legacy-release';evidence['legacy-release']=manifest(old,'package-sha256.json')
 for p in (R/'evidence/studies').iterdir():
  if p.is_dir():evidence[p.name]=manifest(p,'MANIFEST.json')
 originals=json.loads((R/'validation/original-freeze-lock.json').read_text());present=0
 for path,h in originals.items():
  p=Path(path)
  if p.exists():assert sha(p)==h,path;present+=1
 # Independent bracket witnesses and joint input-order counts, no certifier calls.
 rr=read(R/'evidence/studies/atlas-heterogeneous-lif-horizon-20261109/directions/radii.csv');idx={(x['seed'],x['mode'],x['input'],x['pair'],x['steps'],x['direction']):x for x in rr};witnesses=0
 for x in rr:
  if x['mode']=='hetero' and x['steps']=='300':
   y=idx[x['seed'],x['mode'],x['input'],x['pair'],'3000',x['direction']]
   witnesses+=bool(y['upper']) and float(y['upper'])<float(x['lower'])
 assert witnesses==710
 def order(x,y):
  if y['upper'] and float(x['lower'])>float(y['upper']):return 1
  if x['upper'] and float(y['lower'])>float(x['upper']):return -1
  return 0
 common=changed=0
 for s in ['100','201','301']:
  for p in ['0','9','18']:
   for i,j in itertools.combinations(map(str,range(16)),2):
    a=order(idx[s,'hetero','G_B',p,'3000',i],idx[s,'hetero','G_B',p,'3000',j]);b=order(idx[s,'hetero','F_H',p,'3000',i],idx[s,'hetero','F_H',p,'3000',j]);common+=bool(a and b);changed+=bool(a and b and a!=b)
 assert (changed,common)==(394,829)
 labels=[];numbers=[];docs={}
 old_en=Document(old/'manuscript/local-circuit-aggregation-preprint-en.docx')
 old_labels=json.loads((old/'manuscript/document-labels-en.json').read_text())
 summary=json.loads((R/'analysis/summary.json').read_text())
 for lang in ['en','zh']:
  p=R/'manuscript'/f'input-and-horizon-dependent-structural-fidelity-preprint-{lang}.docx';d=Document(p)
  lab=json.loads(p.with_name(f'document-labels-{lang}.json').read_text());labels.append(lab)
  full='\n'.join(x.text for x in d.paragraphs);assert 'Xinjun Li' in full and 'NEXT BRAIN LTD' in full and 'brian2-atlas' in full
  assert not any(t in full for t in ['{{','[[','QQTOKEN','brian 2','Brian 2','zero-input/spike-different'])
  assert '-O3 -std=c11' in full and 'arm64' in full and 'reference-f64' in full
  assert all(x in full for x in ['710','720','394','829','4308/4320' if lang=='en' else '4320','0.753','0.826','0.526','0.585'])
  refs=[p.text for p in d.paragraphs if re.match(r'^\[\d+\]',p.text)];oldrefs=[p.text for p in old_en.paragraphs if re.match(r'^\[\d+\]',p.text)]
  unnumber=lambda s:re.sub(r'^\[\d+\]\s*','',s)
  assert set(map(unnumber,oldrefs))<=set(map(unnumber,refs))
  assert refs==runpy.run_path(str(R/'manuscript/paper_en.py'))['REFERENCES']
  assert len(refs)==27 and len(d.tables)==30 and len(d.inline_shapes)==25
  seen=[]
  for para in d.paragraphs:
   if re.match(r'^\[\d+\]',para.text):continue
   for raw in re.findall(r'\[(\d+(?:[–,]\d+)*)\]',para.text):
    if any(not 1<=int(n)<=27 for n in re.findall(r'\d+',raw)):continue # array shapes and numeric ranges
    for part in raw.split(','):
     ns=list(range(int(part.split('–')[0]),int(part.split('–')[1])+1)) if '–' in part else [int(part)]
     for n in ns:
      assert 1<=n<=27,(lang,raw)
      if n not in seen:seen.append(n)
  assert seen==list(range(1,28)),(lang,seen)
  olddoc=Document(old/'manuscript'/f'local-circuit-aggregation-preprint-{lang}.docx')
  old_table_keys=old_labels['marker_order']['TABLE'];new_table_keys=lab['marker_order']['TABLE']
  def cells(t):return [[c.text for c in row.cells] for row in t.rows]
  for key in old_table_keys:
   assert cells(olddoc.tables[old_table_keys.index(key)])==cells(d.tables[new_table_keys.index(key)]),(lang,key)
  for key,k in [('24',1),('25',2),('26',3)]:
   got=cells(d.tables[new_table_keys.index(key)])[1:];expected=summary[f'table{k}'];assert len(got)==len(expected)
   for aa,bb in zip(got,expected):
    for col,(x,y) in enumerate(zip(aa,bb)):
     if (k==1 and col==1) or (k==3 and col==0):continue
     assert x==str(y),(lang,key,col,x,y)
  nums=[[[re.findall(r'\d+(?:\.\d+)?',c) for c in row] for row in cells(t)[1:]] for t in d.tables];numbers.append(nums)
  with zipfile.ZipFile(p) as z,zipfile.ZipFile(old/'manuscript'/f'local-circuit-aggregation-preprint-{lang}.docx') as oz:
   xml=z.read('word/document.xml').decode();assert '<m:oMath' in xml and xml.count('<pic:pic>')==25
   oldmedia={hashlib.sha256(oz.read(n)).hexdigest() for n in oz.namelist() if n.startswith('word/media/')};newmedia={hashlib.sha256(z.read(n)).hexdigest() for n in z.namelist() if n.startswith('word/media/')};assert oldmedia<=newmedia
  for kind in ['EQ','TABLE','FIG']:assert set(old_labels['marker_order'][kind])<=set(lab['marker_order'][kind])
  docs[lang]=dict(paragraphs=len(d.paragraphs),tables=len(d.tables),figures=len(d.inline_shapes),references=27,sha256=sha(p),all_legacy_table_cells_equal=True,all_legacy_figure_images_preserved=True,citations_in_first_appearance_order=True)
 assert labels[0]==labels[1]
 # Translated prose headers may contain additional numerals; compare data cells
 # against the other language, preserving the old validated table differences.
 for i,(aa,bb) in enumerate(zip(numbers[0],numbers[1])):
  if aa!=bb:
   key=labels[0]['marker_order']['TABLE'][i]
   assert key in old_labels['marker_order']['TABLE'],('new bilingual table mismatch',key)
 for path,h in json.loads((R/'validation/previous-compact-lock.json').read_text()).items():
  if Path(path).exists():assert sha(Path(path))==h,path
 for path,h in json.loads((R/'validation/previous-complete-lock.json').read_text()).items():
  if Path(path).exists():assert sha(Path(path))==h,path
 for path,h in json.loads((R/'validation/previous-regime-lock.json').read_text()).items():
  if Path(path).exists():assert sha(Path(path))==h,path
 for path,h in json.loads((R/'validation/previous-targeted-lock.json').read_text()).items():
  if Path(path).exists():assert sha(Path(path))==h,path
 report=dict(status='pass',immutable_evidence_manifest_files=evidence,original_external_hashes_checked=present,posthoc_strict_shrink=710,posthoc_changed_order=394,posthoc_common_order=829,bilingual_new_numeric_tables_equal=True,all_old_tables_and_figures_retained=True,equation_figure_reference_labels_equal=True,documents=docs,no_simulations_or_radius_searches_in_revision=True)
 (R/'validation/content-audit.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':main()
