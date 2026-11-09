#!/usr/bin/env python3
"""Exact-arithmetic checks of proposition assumptions and constructive examples.
These are implementation checks, not a substitute for the analytical proofs.
"""
from pathlib import Path
from fractions import Fraction as F
from collections import defaultdict
import argparse,csv,struct,json,hashlib

def graph(path):
    result=[defaultdict(F) for _ in range(4)]
    for row in csv.DictReader(path.open()):
        w=F.from_float(struct.unpack('<f',struct.pack('<I',int(row['weight_bits'])))[0])
        result[int(row['arm'])][int(row['target']),int(row['source'])]+=w
    return result

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rewiring-dir',type=Path,default=Path(__file__).resolve().parent/'evidence/rewiring')
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args();root=args.rewiring_dir
    partition=lambda k:0 if k<100 else 1
    s=[F((7*j+3)%101) for j in range(125)]
    means=[sum(s[:100])/100,sum(s[100:])/25]
    residual=[s[j]-means[partition(j)] for j in range(125)]
    checks=[];hashes={}
    for family in ['homogeneous','heterogeneous']:
        base_path=root/'graphs'/family/'original.csv';base=graph(base_path)
        hashes[str(base_path.relative_to(root))]=hashlib.sha256(base_path.read_bytes()).hexdigest()
        for path in sorted((root/'graphs'/family).glob('r*.csv')):
            hashes[str(path.relative_to(root))]=hashlib.sha256(path.read_bytes()).hexdigest()
            for arm,(a,b) in enumerate(zip(base,graph(path))):
                d={key:b.get(key,F(0))-a.get(key,F(0)) for key in set(a)|set(b)}
                incoming=defaultdict(F);outgoing=defaultdict(F)
                ds=[F(0)]*125;dr=[F(0)]*125;sync=[F(0)]*125
                for (k,j),w in d.items():
                    incoming[k,partition(j)]+=w;outgoing[partition(k),j]+=w
                    ds[k]+=w*s[j];dr[k]+=w*residual[j];sync[k]+=w*F(3+partition(j))
                left=all(x==0 for x in incoming.values());right=all(x==0 for x in outgoing.values())
                assert right
                assert sum(ds[:100])==sum(ds[100:])==0
                if family=='homogeneous':assert left and ds==dr and all(x==0 for x in sync)
                checks.append(dict(family=family,graph=path.stem,arm=arm,delta_W_P_zero=left,P_transpose_delta_W_zero=right,residual_identity_for_probe=(ds==dr),group_input_totals_zero=True))
    assert len(checks)==152 and sum(x['family']=='homogeneous' for x in checks)==76
    assert any(not x['delta_W_P_zero'] for x in checks if x['family']=='heterogeneous')
    examples=[]
    for w,sa,sc in [(F(1),F(1),F(0)),(F(3,5),F(100),F(0)),(F(1),F(7),F(7))]:
        i1=[F(0),F(0),w*sa,w*sc];i2=[F(0),F(0),w*sc,w*sa]
        midpoint=[(a+b)/2 for a,b in zip(i1,i2)]
        gap=sum(abs(a-b) for a,b in zip(i1,i2));bound=gap/2
        errors=[sum(abs(a-b) for a,b in zip(midpoint,x)) for x in [i1,i2]]
        assert gap==2*w*abs(sa-sc) and max(errors)==bound
        examples.append(dict(weight=str(w),source_a=str(sa),source_c=str(sc),input_l1_separation=str(gap),minimax_two_instance_input_l1=str(bound)))
    out=dict(status='pass',arithmetic='Exact Fractions from stored binary32 weights; no tolerance-based equality',homogeneous_arm_graph_checks=76,heterogeneous_arm_graph_checks=76,proposition_2_conditions_verified_for_primary_controls=True,heterogeneous_full_conditions_not_assumed=True,checks=checks,counterexamples=examples,graph_sha256=hashes,scope='Shared input operator identities and constructive examples; no nonlinear trajectory bound or spike divergence guarantee')
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(out,indent=2)+'\n')
    print('Theory checks passed: 76 primary constraints, 76 auxiliary checks, 3 exact examples.')
if __name__=='__main__':main()
