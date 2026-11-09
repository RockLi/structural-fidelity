#!/usr/bin/env python3
"""Read-only manuscript/DOCX preservation audit; never executes experiments or renders."""
import argparse
import ast
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET
import zipfile

DEFAULT_ROOT = Path('/Users/rock/workspace/next-brain.ai/next-brain.ai/output/local-circuit-preprint-20261022')
DEFAULT_BASELINE = Path('/tmp/local-circuit-pipeline-revision/before')
NS = {'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main',
      'm':'http://schemas.openxmlformats.org/officeDocument/2006/math',
      'wp':'http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing'}
CITE = re.compile(r'\[(\d+(?:[,–-]\d+)*)\]')
FORMULAS = ['(1a)','(1b)','(2)','(3a)','(3b)','(3c)','(4a)','(4b)']
TABLES = ['1','2','3','4','A1','A2','B1']
FIGURES = ['1','2','3','4','S1','S2']

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def load_source(path):
    return {n.targets[0].id: ast.literal_eval(n.value)
            for n in ast.parse(path.read_text()).body if isinstance(n, ast.Assign)}

def norm(text):
    return ' '.join(text.replace('_','').split())

def expand(group):
    out=[]
    for part in group.split(','):
        ends=re.split('[–-]',part)
        out.extend(range(int(ends[0]), int(ends[-1])+1))
    return out

def citation_info(text):
    raw=CITE.findall(text); numbers=[n for group in raw for n in expand(group)]
    return {'citation_groups':['['+g+']' for g in raw],
            'first_appearance_order':list(dict.fromkeys(numbers)),
            'occurrences_by_number':dict(Counter(numbers))}

def body_text(source):
    return '\n\n'.join(body for _,body in source['SECTIONS']+source['APPENDIX'])

def para_text(node):
    return ''.join(n.text or '' for n in node.iter()
                   if n.tag in {f'{{{NS["w"]}}}t',f'{{{NS["m"]}}}t'})

def read_docx(path):
    with zipfile.ZipFile(path) as z:
        root=ET.fromstring(z.read('word/document.xml'))
    body=root.find('w:body',NS)
    paragraphs=[para_text(p) for p in body.findall('w:p',NS)]
    tables=[[ [para_text(cell) for cell in row.findall('w:tc',NS)]
              for row in table.findall('w:tr',NS)] for table in body.findall('w:tbl',NS)]
    equations=[]
    for p in body.findall('w:p',NS):
        t=para_text(p); m=re.search(r'(\([1-4][abc]?\))$',t)
        if m and p.find('m:oMath',NS) is not None:
            equations.append((m.group(1),t,[ET.tostring(x,encoding='unicode') for x in p.findall('m:oMath',NS)]))
    return {'paragraphs':paragraphs,'tables':tables,'equations':equations,
            'inline_drawing_count':len(root.findall('.//wp:inline',NS))}

def section_slice(paras,start,end=None):
    i=paras.index(start)
    j=paras.index(end,i+1) if end is not None else len(paras)
    return paras[i:j]

def proposition(source,zh):
    blocks=source['SECTIONS'][2][1].split('\n\n')
    return [b for b in blocks if b.startswith(('命题 1','证明。') if zh else ('Proposition 1','Proof.'))]

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=DEFAULT_ROOT)
    parser.add_argument('--baseline',type=Path,default=DEFAULT_BASELINE)
    parser.add_argument('--docx-dir',type=Path,help='Optional staged DOCX directory; source remains under --root.')
    parser.add_argument('--output',type=Path)
    parser.add_argument('--source-only',action='store_true')
    parser.add_argument('--fresh-report',type=Path)
    args=parser.parse_args()
    checks=[]
    def check(name,condition):
        checks.append({'check':name,'pass':bool(condition)})
    current={lang:load_source(args.root/f'paper_{lang}.py') for lang in ['en','zh']}
    baseline={lang:load_source(args.baseline/f'paper_{lang}.py') for lang in ['en','zh']}
    refs=current['en']['REFERENCES']
    check('bibliography exactly unchanged',refs==baseline['en']['REFERENCES'])
    check('10 references numbered consecutively',[int(re.match(r'\[(\d+)\]',r).group(1)) for r in refs]==list(range(1,11)))
    dois=[r.split('https://doi.org/',1)[1] for r in refs]
    check('10 unique DOI strings',len(dois)==len(set(dois))==10)
    result={'generated_at_utc':datetime.now(timezone.utc).isoformat(),
      'scope':{'description':'Minor prose clarification and a fresh end-to-end reproduction run; no new references, mathematical claims or experimental designs.',
               'baseline_directory':str(args.baseline),'validator_executed_experiments':False,
               'validation_performed':'Read-only AST, bibliography, citation and OOXML checks. Visual layout review is recorded separately.',
               'no_fresh_bibliographic_web_lookup':True},
      'bibliography':{'entries':len(refs),'shared_source':'paper_en.py:REFERENCES',
                      'entries_and_numbering_unchanged':refs==baseline['en']['REFERENCES'],
                      'unique_doi_count':len(set(dois)),'added_references':[]},
      'languages':{},'docx':{},'checks':checks}
    for lang in ['en','zh']:
        zh=lang=='zh'; a=baseline[lang]; b=current[lang]
        check(lang+' model Section 2 unchanged',a['SECTIONS'][2]==b['SECTIONS'][2])
        check(lang+' proposition and proof unchanged',proposition(a,zh)==proposition(b,zh) and len(proposition(b,zh))==2)
        check(lang+' all appendices unchanged',a['APPENDIX']==b['APPENDIX'])
        check(lang+' all figure captions unchanged',a['FIG_CAPTIONS']==b['FIG_CAPTIONS'])
        check(lang+' title author affiliation unchanged',all(a[k]==b[k] for k in ['TITLE','AUTHOR','AFFILIATION']))
        permitted={0,3,4,7}
        changed=[i for i,(x,y) in enumerate(zip(a['SECTIONS'],b['SECTIONS'])) if x!=y]
        check(lang+' only authorized sections changed',len(a['SECTIONS'])==len(b['SECTIONS']) and set(changed)<=permitted)
        text=body_text(b); cit=citation_info(text)
        check(lang+' citation groups unchanged',cit==citation_info(body_text(a)))
        check(lang+' all references first appear consecutively',cit['first_appearance_order']==list(range(1,11)))
        markers={key:re.findall(r'\[\['+key+r':([^]]+)\]\]',text) for key in ['EQ','FIG','TABLE']}
        check(lang+' equation figure table markers unchanged',all(v==re.findall(r'\[\['+k+r':([^]]+)\]\]',body_text(a)) for k,v in markers.items()))
        check(lang+' 7 table and 6 figure markers',markers['TABLE']==TABLES and markers['FIG']==FIGURES)
        clauses=(['500 个块','50,000 个分配单元','不含额外过程噪声','HashMap','跨运行','独立分组辅助函数','Scheduler/Chunk','LpuTopologyIndex','递归反馈','f32','一般舍入压力测试'] if zh else
                 ['500 chunks','50,000 allocated units','without additional process noise','HashMap','across runs','separate grouping helper','Scheduler/Chunk','LpuTopologyIndex','recurrent feedback','f32','general rounding-stress test'])
        check(lang+' all requested clarifications present',all(c in text for c in clauses))
        avail=b['SECTIONS'][-1][1]
        if args.fresh_report:
            driver_clauses=['可移植驱动','新运行','归档结果'] if zh else ['portable driver','fresh runs','archived results']
            check(lang+' driver and historical evidence explained',all(c in avail for c in driver_clauses))
        result['languages'][lang]={**cit,'changed_section_indices':changed,
          'model_proposition_proof_appendices_captions_unchanged':all([a['SECTIONS'][2]==b['SECTIONS'][2],a['APPENDIX']==b['APPENDIX'],a['FIG_CAPTIONS']==b['FIG_CAPTIONS']]),
          'markers':markers,'source_sha256':sha(args.root/f'paper_{lang}.py'),
          'requested_clarification_checks':{c:c in text for c in clauses}}
        if args.source_only:
            continue
        filename=f'local-circuit-aggregation-preprint-{lang}.docx'
        docx_path=(args.docx_dir or args.root)/filename
        d=read_docx(docx_path); old=read_docx(args.baseline/filename)
        paras=d['paragraphs']; refheading='参考文献' if zh else 'References'
        start=paras.index(refheading)+1
        end=paras.index(b['APPENDIX'][0][0],start)
        actual_refs=[x for x in paras[start:end] if x.strip()]
        check(lang+' DOCX bibliography exactly matches shared source',actual_refs==refs)
        main_and_appendix=paras[:start-1]+paras[end:]
        check(lang+' DOCX citations exactly match source',citation_info('\n'.join(main_and_appendix))==cit)
        check(lang+' no numeric citations hidden in tables',not CITE.search('\n'.join(cell for tab in d['tables'] for row in tab for cell in row)))
        source_paras=[heading for heading,_ in b['SECTIONS']+b['APPENDIX']]
        source_paras += [block for _,body in b['SECTIONS']+b['APPENDIX'] for block in body.split('\n\n') if not block.startswith('[[')]
        actual_norm={norm(p) for p in paras}
        missing=[p for p in source_paras if norm(p) not in actual_norm]
        check(lang+' every source prose paragraph is present in DOCX',not missing)
        check(lang+' every figure caption present in DOCX',all(norm(c) in actual_norm for c in b['FIG_CAPTIONS'].values()))
        check(lang+' protected Section 2 DOCX content unchanged',section_slice(paras,b['SECTIONS'][2][0],b['SECTIONS'][3][0])==section_slice(old['paragraphs'],a['SECTIONS'][2][0],a['SECTIONS'][3][0]))
        check(lang+' appendix DOCX prose unchanged',section_slice(paras,b['APPENDIX'][0][0])==section_slice(old['paragraphs'],a['APPENDIX'][0][0]))
        check(lang+' all 8 equation labels retained',[e[0] for e in d['equations']]==FORMULAS)
        check(lang+' display equations and native math unchanged',d['equations']==old['equations'])
        check(lang+' 7 tables and 6 inline figures',len(d['tables'])==7 and d['inline_drawing_count']==6)
        check(lang+' table contents unchanged',d['tables']==old['tables'])
        check(lang+' no unexpanded template markers','[[' not in '\n'.join(paras))
        result['docx'][lang]={'path':str(docx_path),'sha256':sha(docx_path),
          'reference_entries':len(actual_refs),'formula_number_sequence':[e[0] for e in d['equations']],
          'tables':len(d['tables']),'table_rows_including_headers':[len(t) for t in d['tables']],
          'inline_drawing_count':d['inline_drawing_count'],'missing_source_paragraphs':missing}
    check('bilingual citation groups identical',result['languages']['en']['citation_groups']==result['languages']['zh']['citation_groups'])
    if args.fresh_report:
        fresh=json.loads(args.fresh_report.read_text())
        check('fresh pipeline report passed',fresh.get('status')=='pass')
        check('fresh pipeline built from fresh outputs',fresh.get('primary_tables_extracted_from_fresh_logs') and fresh.get('e3_and_boundary_tables_generated_from_fresh_runs') and fresh.get('archive_used_only_for_reference_verification'))
        check('fresh pipeline input hashes unchanged',fresh.get('all_package_input_hashes_unchanged') is True)
        result['scope']['fresh_existing_workloads_rerun_reported']=True
        if not args.source_only:
            for lang in ['en','zh']:
                artifact=f'documents/local-circuit-aggregation-preprint-{lang}.docx'
                check(lang+' DOCX hash matches fresh pipeline manifest',result['docx'][lang]['sha256']==fresh.get('deliverable_sha256',{}).get(artifact))
        result['scope']['fresh_rerun_report']={'path':str(args.fresh_report),'sha256':sha(args.fresh_report),
          'top_level_keys':list(fresh),'reported_status':fresh.get('status'),
          'completed_stages':fresh.get('completed_stages'),'reference_checks':fresh.get('reference_checks'),'counts':fresh.get('counts'),
          'note':'This artifact records the fresh run; the present reference/structure validator did not execute or independently reproduce it.'}
    result['reference_metadata']=[{'number':i,'doi':doi,'entry':ref} for i,(doi,ref) in enumerate(zip(dois,refs),1)]
    result['status']='pass' if all(c['pass'] for c in checks) else 'fail'
    result['failed_checks']=[c['check'] for c in checks if not c['pass']]
    payload=json.dumps(result,ensure_ascii=False,indent=2)+'\n'
    if args.output:
        args.output.write_text(payload)
    print(json.dumps({'status':result['status'],'checks':len(checks),'failed_checks':result['failed_checks'],
                      'output':str(args.output) if args.output else None},ensure_ascii=False))
    return 0 if result['status']=='pass' else 1

if __name__=='__main__':
    sys.exit(main())
