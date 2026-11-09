#!/usr/bin/env python3
"""Relocation-safe evidence, numeric, cross-reference and bilingual document audit."""
from pathlib import Path
import hashlib,json,runpy,re,csv,collections,sys,zipfile
from docx import Document
R=Path(__file__).resolve().parent;M=R/'manuscript';B=R/'output/local-circuit-preprint-20261026-final-review';P=R/'research/experiments/paired-direction-mechanism-20261108'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def j(p):return json.loads(p.read_text())
def assert_manifest(root,filename):
 m=j(root/filename)
 for name,want in m.items():assert sha(root/name)==want,str(root/name)
 return len(m)
def main():
 counts={'october':assert_manifest(B,'package-sha256.json')}
 for name in ['finite-horizon-certificate-audit-20261108','finite-horizon-certificate-cost-20261108','finite-horizon-family-prototype-20261108','paired-direction-mechanism-20261108','score-factor-coverage-audit-20261108','paired-dose-composition-20261108','input-control-directions-20261108']:
  counts[name]=assert_manifest(R/'research/experiments'/name,'MANIFEST.json')
 sys.path.insert(0,str(M));from document_labels import Labels
 langs={};maps=[];tables={}
 for lang in ['en','zh']:
  ns=runpy.run_path(str(M/f'paper_{lang}.py'));labels=Labels(type('Paper',(),ns));maps.append(labels.report())
  for _,body in ns['SECTIONS']+ns['APPENDIX']:labels.rewrite(body)
  d=Document(M/f'local-circuit-aggregation-preprint-{lang}.docx');text='\n'.join(p.text for p in d.paragraphs)
  assert '[[' not in text and 'NEXT BRAIN LTD' in text
  assert ('Proposition 4' if lang=='en' else '命题 4') in text
  assert '912' in text and '9,133' in text and '1,787,790' in text and '90,000' in text
  assert not any(x in text for x in ['sup V','2^−'])
  refs=[p.text for p in d.paragraphs if re.match(r'^\[\d+\] ',p.text)]
  assert [int(re.match(r'^\[(\d+)\]',x)[1]) for x in refs]==list(range(1,24))
  cite=set()
  for p in d.paragraphs:
   if re.match(r'^\[\d+\] ',p.text):continue
   for s in re.findall(r'\[([1-9]\d*(?:\s*[,–-]\s*[1-9]\d*)*)\]',p.text):
    if s in {'300,125,10','1000,125,14'}:continue  # recorded array dimensions
    if '–' in s or '-' in s:
     ns2=list(map(int,re.findall(r'\d+',s)));cite.update(range(ns2[0],ns2[-1]+1))
    else:cite.update(map(int,re.findall(r'\d+',s)))
  assert cite==set(range(1,24)),cite
  tables[lang]=[[[c.text for c in row.cells] for row in t.rows] for t in d.tables]
  with zipfile.ZipFile(M/f'local-circuit-aggregation-preprint-{lang}.docx') as z:xml=z.read('word/document.xml').decode()
  assert '<m:oMath' in xml and '>hi<' in xml and '>lo<' in xml
  langs[lang]={'paragraphs':len(d.paragraphs),'tables':len(d.tables),'references':len(refs),'all_references_cited':True,'native_math':True,'docx_sha256':sha(M/f'local-circuit-aggregation-preprint-{lang}.docx')}
 assert maps[0]==maps[1]
 A=j(P/'results/analysis.json')
 for lang in ['en','zh']:
  tabs=tables[lang]
  rank=next(t for t in tabs if len(t)==7 and len(t[0])==4 and t[0][1:]==['Tonic','Global','Focal'])
  for row,method in zip(rank[1:],['random','raw','mean','shuffle','temporal','full']):
   wanted=[f"{next(x['macro_concordance'] for x in A['rank'] if x['probe']==u and x['subgroup']=='all' and x['method']==method):.3f}" for u in ['tonic','global_burst','focal_burst']];assert row[1:]==wanted
  transfer=next(t for t in tabs if len(t)==10 and len(t[0])==6 and t[1][0]=='Tonic')
  raw=list(csv.DictReader((P/'results/selection-transfer.csv').open()));expected=[]
  for u in ['tonic','global_burst','focal_burst']:
   for c in ['random','mean','shuffle']:
    counts2=collections.Counter(x['outcome'] for x in raw if x['probe']==u and x['control']==c)
    expected.append([str(counts2['win']),str(counts2['loss']),str(counts2['tie_same_direction']+counts2['tie_at_cap']),str(counts2['unresolved'])])
  assert [r[2:] for r in transfer[1:]]==expected
  cost=next(t for t in tabs if len(t)==7 and len(t[0])==3 and t[0][1]=='ms')
  single=j(R/'research/experiments/finite-horizon-certificate-cost-20261108/results/summary.json')['groups']['certified_nonzero16'];fam=j(R/'research/experiments/finite-horizon-family-prototype-20261108/results/analysis.json')['costs']['d2_nonzero_input_certified']
  values=[f"{single['new_certificate_seconds']*1000:.5f}",f"{single['native_replay_seconds']*1000:.6f}"]+[f'{fam[k]:.5f}' for k in ['support_compute_ms','certified_corner_compute_ms','plain_corner_compute_ms','grid_compute_ms']]
  assert [x[1] for x in cost[1:]]==values
 assert A['radii_stops']=={'bracket_tolerance':652,'proof_gap':98,'cap_certified':162}
 from verify_incorporated import verify
 incorporated=verify(R,tables)
 report={'incorporated':incorporated,'status':'pass','immutable_manifest_files':counts,'current_documents':langs,'bilingual_label_maps_equal':True,'all_new_table_values_independently_checked':True,'completed_analysis_status_and_boundaries_checked':True,'scope':'Content and evidence check; visual rendering is a separate recorded gate.'}
 (R/'validation/content-audit.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':main()
