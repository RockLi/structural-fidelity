"""Native equations and tables for the completed graph and LIF validations."""
import json,csv
from pathlib import Path
from docx.shared import Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement

def equations(key,h):
 s=h.sub;u=h.sup;q=h.seq;f=h.frac
 def e(parts,n):h.equation(q(parts),'('+n+')')
 if key=='lif':
  e(q(u(s('v','i'),'+'),' = ',s('v','i'),' + ',f('dt',s('τ','i')),'(',s('E','L'),' + ',s('I','b'),' + ',s('g','Ei'),' − ',s('g','Ii'),' + ',s('d','i'),' − ',s('v','i'),')'),'30a')
  e(q(u(s('g','qi'),'+'),' = (1 − dt/',s('τ','q'),')',s('g','qi'),',   q ∈ {E,I}'),'30b')
 elif key=='lif_family':
  e(q(s('w','e'),'(α) = ',s('RN','64'),'[',s('w','e,0'),s('RN','64'),'(1 + ',s('σ','e'),'α)],   |α| ≤ ρ ≤ 0.25'),'31')
 elif key=='horizon_nested':
  e(q(s('S',s('T','2')),' ⊆ ',s('S',s('T','1')),' (',s('T','2'),' ≥ ',s('T','1'),'),   ',s('U','long'),' < ',s('L','short')),'32')
 elif key=='lif_score':
  e(q(s('y','iq'),'[n] = ',s('c','q'),s('y','iq'),'[n−1] + ',s('δI','iq'),'[n]'),'33a')
  e(q(s('z','i'),'[n] = (1−',s('h','i'),')',s('z','i'),'[n−1] + ',s('h','i'),'(',s('y','iE'),'[n]−',s('y','iI'),'[n])'),'33b')
  e(q('J = ',s('max','i,n eligible'),f(q('|',s('z','i'),'[n]|'),q('max{|',s('v','ref,i,pre'),'[n] − ',s('θ','i'),'|, ε}'))),'33c')
 elif key=='lif_decay_bound':e(q('e′ := Eval↑[(|b| + ',s('d','b'),')e + ρ ',s('d','s'),' + 2R]'),'34')
 elif key=='lif_voltage_bound':e(q('e′ := Eval↑[(|',s('b','0'),'| + ',s('d','b'),' + ',s('d','h'),')',s('e','v'),' + ',s('h','u'),'(',s('e','E'),' + ',s('e','I'),') + ρ ',s('d','s'),' + 2',s('R','v'),']'),'35')
 else:raise ValueError(key)

def table(key,args,zh,h,cap):
 summary=json.loads((args.analysis/'summary.json').read_text())
 def make(title,cn,heads,chs,rows,widths,keep=True):
  cap(cn if zh else title);t=h.table(chs if zh else heads,rows,widths)
  for i,row in enumerate(t.rows):
   row._tr.get_or_add_trPr().append(OxmlElement('w:cantSplit'))
   for cell in row.cells:
    for p in cell.paragraphs:
     p.alignment=WD_ALIGN_PARAGRAPH.CENTER
     p.paragraph_format.keep_with_next=(i<len(t.rows)-1) if keep else i==0
     p.paragraph_format.keep_together=True
  return t
 if key=='24':
  rows=[list(x) for x in summary['table1']]
  if zh:
   for r in rows:r[1]={'Independent':'独立','Module':'模块','Ring':'环形'}[r[1]]
  make('Table 24. Visibility switches out of nineteen fixed swaps on each original. The first row is discovery; the other nine originals were prospectively fixed. A zero is retained, not replaced by resampling. Counts depend on marginal visibility rates and do not rank input dependence across columns or test excess switching above independence.','表24 每张原图十九个固定交换中的可见性切换数。首行为发现图，其余九图预先固定；保留零值，不以重采样替换。计数依赖边际可见率，不能跨列排列输入依赖强弱，也不检验切换是否超过独立期望。',['Seed','Rule','GB/FH','GT/FHT','GB/GT','FH/FHT','FB/FH'],['种子','规则','GB/FH','GT/FHT','GB/GT','FH/FHT','FB/FH'],rows,[.50,.90,1.00,1.10,1.00,1.06,1.00])
 elif key=='25':
  make('Table 25. Heterogeneous LIF G_B/F_H switches and F_H score agreement. Own and frozen scores use the same resolved pairs; coverage has 360 possible pairs per graph/horizon. Macro n counts contributing target pairs.','表25 异质 LIF 的 G_B/F_H 切换与 F_H 评分一致率。自身与冻结评分使用同一已分辨集合，每图每时域有360个可能方向对；宏 n 为贡献目标对数。',['Seed','ms','Switch /19','Own','Frozen','Cover %','Macro n'],['种子','ms','切换/19','自身','冻结','覆盖%','宏 n'],summary['table2'],[.60,.60,1.08,.90,.90,1.08,1.00])
 elif key=='26':
  rows=[list(x) for x in summary['table3']]
  if zh:
   for r in rows:r[0]={'hom':'同质','hetero':'异质'}[r[0]]
  make('Table 26. LIF certified interval coverage. Medians include zeros and the 25% cap among 720 dependent conditions per row; Limit denotes the eight-refinement limit.','表26 LIF 认证区间覆盖。每行720个相关条件的中位数包含零下界与25%上限；限次表示八次细化预算用尽。',['Model','ms','Positive','Total','Median %','Cap','Limit'],['模型','ms','正下界','总数','中位%','上限','限次'],rows,[.80,.55,.90,.70,1.55,1.00,.66])
 elif key=='27':
  rr=list(csv.DictReader((args.lif_dir/'analysis/visibility-switches.csv').open()));rows=[]
  for mode in ['hom','hetero']:
   for seed in ['100','201','301']:
    for contrast in ['G_B/F_H','G_T/F_HT','G_B/G_T','F_H/F_HT','F_B/F_H']:
     vals=[next(r['switches'] for r in rr if r['mode']==mode and r['seed']==seed and r['contrast']==contrast and r['readout']=='unit' and r['steps']==n) for n in ['300','1000','3000']]
     rows.append([{'hom':'同质','hetero':'异质'}[mode] if zh else mode,seed,contrast]+vals)
  make('Table 27. Complete per-unit visibility switch counts, out of nineteen swaps in every cell. Each horizon is a prefix of the same trajectory. At heterogeneous 300 ms all zeros mean different under both inputs.','表27 完整逐单元可见性切换数，每格分母均为十九。各时域是同一轨迹前缀；异质300 ms 的全部零均表示两输入下都不同。',['Model','Seed','Contrast','30 ms','100 ms','300 ms'],['模型','种子','对照','30 ms','100 ms','300 ms'],rows,[.80,.60,1.80,1.12,1.12,1.12],False)
 elif key=='28':
  rr=list(csv.DictReader((args.lif_dir/'analysis/score-macro.csv').open()));rows=[]
  for mode in ['hom','hetero']:
   for seed in ['100','201','301']:
    for n in ['300','1000','3000']:
     r=next(r for r in rr if r['mode']==mode and r['seed']==seed and r['steps']==n and r['input']=='F_H')
     def v(k):return f'{float(r[k]):.3f}' if r[k] else '—'
     rows.append([{'hom':'同质','hetero':'异质'}[mode] if zh else mode,seed,str(int(n)//10)]+[v(k) for k in ['joint','GB_frozen','mean','shuffle']]+[f'{100*float(r["coverage"]):.1f}',r['macro_target_pairs']])
  make('Table 28. F_H score controls and resolved coverage across both LIF variants. Entries are target-level macro agreement; absent scores are undefined. The possible denominator is 360 per row.','表28 两类LIF的F_H评分对照与可分辨覆盖。数值为目标对宏平均一致率，缺失评分为未定义，每行可能分母为360。',['Model','Seed','ms','Own','Frozen','Mean','Shuffle','Cover %','n'],['模型','种子','ms','自身','冻结','平均','打乱','覆盖%','n'],rows,[.70,.50,.50,.78,.78,.78,.78,.80,.44],False)
 else:raise ValueError(key)
