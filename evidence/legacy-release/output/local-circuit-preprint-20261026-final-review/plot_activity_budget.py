#!/usr/bin/env python3
"""Present all locked selectors and zero outcomes; no new model selection."""
from pathlib import Path
import argparse,csv,hashlib,json,os
import numpy as np

ROOT=Path(__file__).resolve().parent
POLICIES=['random','mean','coactivity','shuffled']
def rows(p):
    with Path(p).open() as f:return list(csv.DictReader(f))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def main():
    p=argparse.ArgumentParser();p.add_argument('--retention-dir',type=Path,default=ROOT/'evidence/activity-guided-retention');p.add_argument('--budget-dir',type=Path,default=ROOT/'evidence/budget-boundary');p.add_argument('--output-dir',type=Path,default=ROOT/'activity-figures');a=p.parse_args()
    out=a.output_dir;out.mkdir(parents=True,exist_ok=True);assert not list(out.iterdir())
    small=rows(a.budget_dir/'analysis-train/per_policy.csv');old=rows(a.retention_dir/'analysis/per_policy.csv')
    protocol=json.loads((a.budget_dir/'protocol.json').read_text());gate=json.loads((a.budget_dir/'gate.json').read_text())
    data=[]
    for r in small:
        assert r['probe']=='train'
        data.append(dict(r,budget_percent=100*protocol['budgets'][r['budget']]['fraction']))
    for r in old:
        if r['probe']=='train':data.append(dict(r,budget='prior',budget_percent=100*282/2845))
    by={(r['budget'],r['policy'],int(r['block'])):r for r in data};assert len(by)==120
    table=[];paired=[]
    for budget in ['p01','p02','prior']:
        for policy in POLICIES:
            rr=[by[budget,policy,b] for b in range(10)]
            table.append(dict(budget=budget,budget_percent=rr[0]['budget_percent'],policy=policy,n=10,
                J_coactivity_mean=float(np.mean([float(r['J_coactivity']) for r in rr])),score_zero_count=sum(float(r['J_coactivity'])==0 for r in rr),
                raw_slot_l1_mean=float(np.mean([float(r['raw_slot_l1']) for r in rr])),
                raw_slot_l1_median=float(np.median([float(r['raw_slot_l1']) for r in rr])),spike_zero_count=sum(float(r['Dslot'])==0 for r in rr),
                bin_zero_count=sum(float(r['D1ms'])==0 for r in rr),count_zero_count=sum(float(r['Dcount'])==0 for r in rr)))
        for b in range(10):
            c,r=by[budget,'coactivity',b],by[budget,'random',b];j=float(r['J_coactivity'])
            paired.append(dict(budget=budget,block=b,budget_percent=c['budget_percent'],J_random=j,J_coactivity=float(c['J_coactivity']),
                score_relative_reduction=1-float(c['J_coactivity'])/j if j else None,
                raw_error_difference=float(c['raw_slot_l1'])-float(r['raw_slot_l1']),
                random_zero=float(r['Dslot'])==0,coactivity_zero=float(c['Dslot'])==0))
    # Recompute the frozen continuation rule from paired archived memberships.
    # Presentation rounding never participates in the decision.
    rule=protocol['continuation_gate'];eps=rule['epsilon']
    comparison=[];budget_passed={}
    for budget in ['p01','p02']:
        frozen=next(r for r in gate['budgets'] if r['budget']==budget)
        for comparator in ['random','mean','shuffled']:
            pairs=[(by[budget,'coactivity',b],by[budget,comparator,b]) for b in range(10)]
            delta=np.array([float(c['raw_slot_l1'])-float(r['raw_slot_l1']) for c,r in pairs])
            assert np.isfinite(delta).all()
            row=dict(budget=budget,budget_percent=pairs[0][0]['budget_percent'],comparator=comparator,n=len(pairs),
                mean_difference=float(np.mean(delta)),median_difference=float(np.median(delta)),
                wins=int(np.sum(delta < -eps)),ties=int(np.sum(np.abs(delta)<=eps)),losses=int(np.sum(delta>eps)),
                same_selected_graph=sum(c['canonical_graph']==r['canonical_graph'] for c,r in pairs))
            expected=frozen['observed'][comparator]
            for current,old in [('mean_difference','mean'),('median_difference','median'),('wins','coactivity_better'),('ties','tied'),('losses','coactivity_worse'),('same_selected_graph','same_selected_graph'),('n','n')]:
                assert row[current]==expected[old],(budget,comparator,current)
            complete=row['n']==rule['required_complete_pairs']
            if comparator=='random':
                check=rule['random']
                passed=complete and row['mean_difference']<check['mean_less_than'] and row['median_difference']<check['median_less_than'] and row['wins']>=check['minimum_strict_wins']
            else:
                check=rule['specificity']
                assert comparator in check['comparators'] and check['wins_at_least_losses']
                passed=complete and row['mean_difference']<=check['mean_at_most'] and row['wins']>=row['losses']
            row['comparison_passed']=bool(passed);comparison.append(row)
        budget_passed[budget]=all(r['comparison_passed'] for r in comparison if r['budget']==budget)
        assert budget_passed[budget]==frozen['passed']
    for row in comparison:row['budget_passed']=budget_passed[row['budget']]
    assert rule['both_budgets_required']
    proceed=all(budget_passed.values());assert proceed==gate['proceed_migration']
    decision=dict(epsilon=eps,both_budgets_required=True,budgets=budget_passed,proceed_migration=proceed,
        interpretation=rule['interpretation'])
    inputs={}
    for base,names in [(a.retention_dir,['analysis/per_policy.csv']), (a.budget_dir,['analysis-train/per_policy.csv','protocol.json','gate.json'])]:
        for n in names:inputs[('retention/' if base==a.retention_dir else 'budget/')+n]=sha(base/n)
    payload=dict(table_rows=table,paired=paired,comparison_rows=comparison,decision_summary=decision,gate=gate,input_hashes=inputs,
        scope='Presentation of locked training outcomes; 9.912% is prior evidence. All selectors, ties, zero scores and zero spike errors retained. No new scientific condition or independent replication.')
    save(out/'activity-budget-figure-data.json',payload)
    for name,rr in [('table-values',table),('paired-values',paired),('paired-comparison-values',comparison)]:
        with (out/(name+'.csv')).open('w') as f:w=csv.DictWriter(f,fieldnames=list(rr[0]),lineterminator='\n');w.writeheader();w.writerows(rr)
    os.environ.setdefault('MPLCONFIGDIR','/tmp/budget-boundary-paper-matplotlib')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':9,'axes.spines.top':False,'axes.spines.right':False,'pdf.fonttype':42})
    fig,axes=plt.subplots(1,2,figsize=(6.8,3.6))
    for j,field in enumerate(['score_relative_reduction','raw_error_difference']):
        ax=axes[j]
        for b in range(10):
            values=[next(x for x in paired if x['block']==b and x['budget']==q)[field] for q in ['p01','p02','prior']]
            yy=[100*v if v is not None else np.nan for v in values]
            ax.plot(range(3),yy,color='#72969d',alpha=.35,lw=.8)
            ax.scatter(np.arange(3)+(b-4.5)*.018,yy,color='#287e87',s=15,alpha=.8)
        for x,q in enumerate(['p01','p02','prior']):
            vals=[100*r[field] for r in paired if r['budget']==q and r[field] is not None]
            if vals:ax.plot([x-.18,x+.18],[np.mean(vals)]*2,c='#182b39',lw=2.5)
        ax.axhline(0,c='#777',ls='--',lw=.8);ax.grid(axis='y',alpha=.15)
        ax.set_xticks(range(3),['0.984%','1.968%','9.912%\n(prior)']);ax.set_xlabel('Original adjacency replaced')
    axes[0].set_title('A  Frozen-reference score',loc='left',fontsize=10,weight='bold');axes[0].set_ylabel('J reduction from random (%)')
    axes[1].set_title('B  Closed-loop spike error',loc='left',fontsize=10,weight='bold');axes[1].set_ylabel('Raw-slot L1 difference\n(coactivity − random, pp)')
    fig.subplots_adjust(left=.10,right=.98,top=.86,bottom=.28,wspace=.45)
    fig.text(.5,.025,'Matched candidate banks across nested budgets; horizontal bars are means.\nPanel B: negative favors coactivity; lines connect banks, not identical selections.',ha='center',fontsize=8)
    fig.savefig(out/'activity-budget-boundary.png',dpi=220,bbox_inches='tight')
    fig.savefig(out/'activity-budget-boundary.pdf',bbox_inches='tight',metadata={'CreationDate':None,'ModDate':None})
    plt.close(fig)
    save(out/'validation.json',dict(status='pass',table_rows=len(table),paired_rows=len(paired),comparison_rows=len(comparison),gate_recomputed_from_pairs=True,source_sha256=sha(Path(__file__)),outputs={x.name:sha(x) for x in sorted(out.iterdir()) if x.is_file()}))
    print('PASS: all selectors, zero outcomes and six paired comparisons; frozen stopping rule independently recomputed.')
if __name__=='__main__':main()
