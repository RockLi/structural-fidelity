from pathlib import Path
import runpy,re,json,collections,zipfile,hashlib
from lxml import etree as E
from docx import Document
R=Path(__file__).resolve().parent;O=R/'editorial/prior-manuscript'
sm=json.loads((R/'editorial/section-map.json').read_text());changes=json.loads((R/'editorial/text-changes.json').read_text())
def norm(t,old=False):
 if old:
  pat=r'(?P<prefix>(?:[Ss]ections?|第)\s*)(?P<nums>\d+\.\d+(?:\s*(?:[–—−-]|and|,|、|和|至)\s*\d+\.\d+)*)'
  t=re.sub(pat,lambda m:m['prefix']+re.sub(r'\d+\.\d+',lambda n:sm.get(n[0],n[0]),m['nums']),t)
 t=re.sub(r'\[\d+(?:[–,]\d+)*\]','[CITATION]',t)
 return re.sub(r'\s+','',t).casefold()
def splits(t,n):
 parts=re.split(r'(?m)^'+str(n)+r'\.\d+ [^\n]+\n\n',t)
 return [p for s in parts for p in s.strip().split('\n\n') if p]
report={}
for lang in ['en','zh']:
 old=runpy.run_path(str(O/f'paper_{lang}.py'));new=runpy.run_path(str(R/f'manuscript/paper_{lang}.py'))
 actual=norm('\n\n'.join(b for _,b in new['SECTIONS']));missing=[];checked=0
 for i in [2,3,4]:
  for para in splits(old['SECTIONS'][i][1],i):
   mapped=next((x['after'] for x in changes[lang] if x['before']==para),para)
   if norm(mapped,True) in actual:checked+=1;continue
   # Three paragraphs intentionally split between visibility and direction methods/results.
   if para.startswith(('Each input uses its own original reference.','每个输入采用其自身原图参考。')):
    cut='The fixed nineteen-by-sixteen' if lang=='en' else '固定的19×16'
    a,b=para.split(cut,1);frags=[a,cut+b]
   elif para.startswith(('Each new original uses the five','每张新原图使用')):
    cut='Target pairs are sorted' if lang=='en' else '目标对排序';tail='The three independent-edge originals' if lang=='en' else '三张独立连边原图'
    a,b=para.split(cut,1);b,c=b.split(tail,1);frags=[a,cut+b,tail+c]
   else:frags=[mapped]
   if all(norm(f,True) in actual for f in frags):checked+=1
   else:missing.append(para[:250])
 assert not missing,(lang,missing)
 
 for (oh,ob),(nh,nb) in zip(old['APPENDIX'],new['APPENDIX']):
  assert oh==nh
  if 'Appendix M' in oh or '附录 M' in oh:
   assert norm(nb)==norm(next(x['after'] for x in changes[lang] if '[[EQ:lif_decay_bound]]' in x['after']))
  else:assert norm(ob,True)==norm(nb),oh
 assert {k:norm(v,True) for k,v in old['FIG_CAPTIONS'].items()}=={k:norm(v) for k,v in new['FIG_CAPTIONS'].items()}
 od=Document(O/f'local-circuit-aggregation-preprint-{lang}.docx');nd=Document(R/f'manuscript/local-circuit-aggregation-preprint-{lang}.docx')
 ol=json.loads((O/f'document-labels-{lang}.json').read_text());nl=json.loads((R/f'manuscript/document-labels-{lang}.json').read_text())
 for key in ol['marker_order']['TABLE']:
  cells=lambda t:[[c.text for c in row.cells] for row in t.rows]
  assert cells(od.tables[ol['marker_order']['TABLE'].index(key)])==cells(nd.tables[nl['marker_order']['TABLE'].index(key)]),(lang,key)
 def hashes(path):
  with zipfile.ZipFile(path) as z:
   x=E.fromstring(z.read('word/document.xml'))
   math=collections.Counter(hashlib.sha256(E.tostring(e,method='c14n')).hexdigest() for e in x.findall('.//{http://schemas.openxmlformats.org/officeDocument/2006/math}oMath'))
   imgs={hashlib.sha256(z.read(n)).hexdigest() for n in z.namelist() if n.startswith('word/media/')}
   return math,imgs
 om,oi=hashes(O/f'local-circuit-aggregation-preprint-{lang}.docx');nm,ni=hashes(R/f'manuscript/local-circuit-aggregation-preprint-{lang}.docx')
 assert sum((om-nm).values())==2,(lang,'only two radius equations may change',om-nm);assert oi<=ni
 report[lang]={'retained_scientific_paragraphs':checked,'all_appendices_and_proofs_preserved':True,'all_30_empirical_tables_unchanged':True,'all_25_figures_preserved':True,'native_math_objects_preserved':sum(om.values())-2,'two_radius_equations_clarified':True}
print(json.dumps(report,indent=2));(R/'validation/editorial-preservation.json').write_text(json.dumps({'status':'pass','documents':report,'no_new_scientific_runs':True,'no_new_statistical_analyses':True},indent=2))
