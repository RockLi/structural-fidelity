"""Tables drawn directly from the three incorporated evidence directories."""
import csv,json,collections
from docx.shared import Pt

def read(p):return list(csv.DictReader(p.open()))
def render(key,args,zh,h,cap):
 def title(en,cn):cap(cn if zh else en)
 def t(headers,rows,widths):
  tab=h.table(headers,rows,widths)
  for i,row in enumerate(tab.rows):
   for cell in row.cells:
    for pp in cell.paragraphs:
     if zh and key=='22':pp.paragraph_format.line_spacing=Pt(12)
     pp.paragraph_format.keep_together=True
     pp.paragraph_format.keep_with_next=i<len(tab.rows)-1
 if key=='17':
  title('Table 17. Ten paired random chains at three nested edit budgets. Values are means; X and Y use the same original spike total. R is the mean of individual ratios, not a ratio of means.','表17 三个嵌套编辑预算的10条随机配对链。数值为均值；X和Y共享原图总脉冲归一。R为各链比值均值，不是均值之比。')
  rs=read(args.dose_dir/'budget-summary.csv');rows=[]
  for b,e in [('p01',28),('p02',56),('full',282)]:
   def v(m):return float(next(x['mean'] for x in rs if x['budget']==b and x['metric']==m))
   rows.append([f'{100*e/2845:.3f}',str(e),str(e//2),f'{v("Dslot")/147600:.4f}',f'{v("Dcount")/147600:.4f}',f'{100*v("Rcount"):.2f}'])
  t(['编辑 %' if zh else 'Edit %','原邻接' if zh else 'Adjacencies','交换' if zh else 'Exchanges','X','Y','R / %'],rows,[1.05,1.15,1.1,1.05,1.05,1.16])
 elif key=='18':
  title('Table 18. Post hoc score-factor ablation on identical eligible slots and resolved pairs. Macro concordance; mean and shuffle rows retain the original locked full-window definitions.','表18 相同有效时点及可分辨方向对上的事后评分因子消融。宏平均一致率；平均及打乱行保留原锁定完整窗口定义。')
  rs=read(args.score_audit_dir/'rank-summary.csv');methods=[('original_f0m0','Neither factor','无滤波无裕度'),('original_f1m0','Filter only','仅滤波'),('original_f0m1','Margin only','仅裕度'),('original_f1m1','Filter + margin','滤波与裕度'),('mean_f1m1','Mean + both','平均活动与双因子'),('shuffle_f1m1','Shuffled + both','打乱活动与双因子')]
  rows=[[cn if zh else en]+[f"{float(next(x['macro'] for x in rs if x['probe']==u and x['method']==m)):.3f}" for u in ['tonic','global_burst','focal_burst']] for m,en,cn in methods]
  t(['评分' if zh else 'Score','Tonic','Global','Focal'],rows,[2.8,1.25,1.25,1.26])
 elif key=='19':
  title('Table 19. Paired spike visibility under controlled inputs. Same and different refer to each swap versus its own input reference. All rows include nineteen fixed swaps.','表19 控制输入下的配对脉冲可见性。同、异指各交换相对其自身输入参考；每行包含同19个固定交换。')
  rs=read(args.input_control_dir/'visibility-contrasts.csv');rows=[]
  for r in rs:rows.append([r['input_a']+' / '+r['input_b']]+[r[k] for k in ['same/same','different/different','same/different','different/same']]+[str(int(r['same/different'])+int(r['different/same']))])
  t(['输入对' if zh else 'Inputs','同/同' if zh else 'Same/same','异/异' if zh else 'Diff/diff','同/异' if zh else 'Same/diff','异/同' if zh else 'Diff/same','切换' if zh else 'Switch'],rows,[1.66,.98,.98,.98,.98,.98])
 elif key=='20':
  title('Table 20. Reference-conditioned factor scores under the controlled inputs. Target-level macro concordance on the same resolved sets; controls use the delivered source window.','表20 控制输入下的参考条件评分。相同可分辨集合上的目标对宏平均；对照采用到达源窗口。')
  d=json.loads((args.input_control_dir/'directions/detailed-summary.json').read_text());inputs=['G_B','F_B','F_H','G_T','F_HT'];rs=d['rank'];methods=[('f0m0','Neither','无双因子'),('f1m0','Filter only','仅滤波'),('f0m1','Margin only','仅裕度'),('temporal','Joint score','联合评分'),('mean','Mean control','平均对照'),('shuffle','Shuffle control','打乱对照'),('full','Full sensitivity','完整敏感度')];rows=[]
  for m,en,cn in methods:rows.append([cn if zh else en]+[f"{next(x['macro'] for x in rs if x['input']==u and x['method']==m):.3f}" for u in inputs])
  rows.append(['覆盖 %' if zh else 'Coverage %']+[f"{100*d['coverage'][u]['resolved']/2280:.2f}" for u in inputs]);rows.append(['目标对' if zh else 'Target pairs']+[str(19-len(d['coverage'][u]['excluded_targets'])) for u in inputs])
  t(['评分' if zh else 'Score']+inputs,rows,[1.81,.95,.95,.95,.95,.95])
 elif key=='21':
  title('Table 21. Unresolved-order categories in the post hoc score audit. Categories are mutually exclusive; proof-gap overlap takes precedence over other finite overlap. Each input has 2,280 comparisons.','表21 事后评分审计的未决分类。类别互斥，证明间隙重叠优先于其他有限重叠；每输入共2,280个比较。')
  rs=read(args.score_audit_dir/'coverage-by-target.csv');rows=[]
  for u in ['tonic','global_burst','focal_burst']:
   z=[x for x in rs if x['probe']==u];rows.append([u.replace('_burst','').title()]+[str(sum(int(x[k]) for x in z)) for k in ['resolved','both_capped','proof_gap_overlap','finite_overlap','cap_overlap']])
  t(['输入' if zh else 'Input','已分辨' if zh else 'Resolved','双上限' if zh else 'Both cap','间隙重叠' if zh else 'Gap overlap','有限重叠' if zh else 'Finite overlap','其他上限' if zh else 'Other cap'],rows,[1.1,1.05,1.05,1.15,1.15,1.06])
 elif key=='23':
  title('Table 23. All controlled-input direction search outcomes, 304 per input. Refinement limit means the existing eight-step budget was exhausted.','表23 输入控制全部方向搜索结果，每输入304个。细分上限表示原8步预算耗尽。')
  rs=read(args.input_control_dir/'directions/radii.csv');rows=[]
  for u in ['G_B','F_B','F_H','G_T','F_HT']:
   c=collections.Counter(x['stop'] for x in rs if x['probe']==u);rows.append([u]+[str(c[k]) for k in ['bracket_tolerance','proof_gap','cap_certified','refinement_limit']])
  t(['输入' if zh else 'Input','达到容差' if zh else 'Tolerance','证明间隙' if zh else 'Proof gap','认证上限' if zh else 'Certified cap','细分上限' if zh else 'Step limit'],rows,[1.1,1.4,1.4,1.4,1.26])
 elif key=='22':
  title('Table 22. Frozen G_B selections transferred to all inputs. Joint-score choice versus frozen controls; ties combine same direction and joint cap, with unresolved cases separate.','表22 冻结G_B选择迁移至各输入。联合评分选择对冻结对照；平局合并同方向及共同上限，未决单列。')
  rs=read(args.input_control_dir/'directions/selection-transfer.csv');rows=[]
  for u in ['G_B','F_B','F_H','G_T','F_HT']:
   for v in ['random','mean','shuffle']:
    c=collections.Counter(x['outcome'] for x in rs if x['probe']==u and x['control']==v);rows.append([u,{'random':'随机','mean':'平均','shuffle':'打乱'}[v] if zh else v.title()]+[str(c['win']),str(c['loss']),str(c['tie_same_direction']+c['tie_at_cap']),str(c['unresolved'])])
  t(['输入' if zh else 'Input','对照' if zh else 'Control','胜' if zh else 'Win','负' if zh else 'Loss','平' if zh else 'Tie','未决' if zh else 'Unresolved'],rows,[1,1.56,1,1,1,1])
