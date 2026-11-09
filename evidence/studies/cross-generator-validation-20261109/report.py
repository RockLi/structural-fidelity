"""Report predeclared outputs; does not modify scientific code or manuscripts."""
from pathlib import Path
import json,csv,statistics,collections
R=Path(__file__).resolve().parent;A=R/'analysis';SEEDS=[201,202,203,301,302,303];INPUTS=['G_B','F_B','F_H','G_T','F_HT']
def load(p):return json.loads(p.read_text())
def read(p):return list(csv.DictReader(p.open()))
def rng(xs,scale=1):return f'{min(xs)*scale:.3f}–{max(xs)*scale:.3f}'
J=load(A/'summary.json');ranks=read(A/'rank.csv');factors=read(A/'factor-deltas.csv');valid=[load(R/f'seed{s}/validation.json') for s in SEEDS];anal=[load(R/f'seed{s}/directions/analysis.json') for s in SEEDS];runs=[load(R/f'seed{s}/directions/run-summary.json') for s in SEEDS]
text=['跨图生成机制验证：结果与审稿判断','2026-11-09；单独保存，未修改冻结稿或旧实验。','', '一、结论与设计',
'这轮将证据从原先同一 E/I 独立连边生成器的多个种子，推进到两种预先固定的连接亲和规则。模块偏置和环形距离偏置共享新的加权无放回抽样实现，并非两个独立模拟器。内核仍是125个同步块、30 ms、确定性binary32执行核。',
'两类各3张原图，固定种子201/202/203和301/302/303。每张2845条边，四类边数1467/610/648/120，权重、延迟与输入相同。逐节点度和强度不在原图之间匹配；19个最小交换则分别严格保持各自原图的逐节点分通道度、强度及权重多重集。不能用两类结果的差异推断几何因果或哪种形态最好。',
'600个科学网络条件、35个技术桥接/重复条件；112个去重目标对×16个方向×5个输入=8960个方向条件。协议和图/样本先锁定，再运行网络；全部6图评分在任何半径搜索前锁定。研究是本地事前固定的有限设计，不是公开预注册或均匀图系综抽样。','', '二、可见性切换']
text.append('每格为19个固定交换中，在该输入对之间从脉冲完全相同变成不同或反向切换的个数。各图是重复单位，不能将所有交换视为独立原图。')
text.append('输入对                 201 202 203 | 301 302 303')
for z in J['visibility']:text.append(f"{z['input_a']+'/'+z['input_b']:<22}"+' '.join(f"{z['counts'][str(s)]:3}" for s in SEEDS))
text.extend(['G_B/F_H逐槽总驱动匹配：模块图8/13/8，环形图11/9/11。总驱动量不能单独决定本设计中固定交换的脉冲可见性，这一点在两类所有6张原图重现。',
'时间重排保持每节点幅度多重集，但不保持时序。全局重排在6图均有切换；焦点重排在环形seed303为0/19，因此该对比没有通过“跨两类全部原图出现切换”的预定判据。其他图的1/19等低频结果也保留。0/19仅表示这19个交换的二值可见性类别未变，不证明轨迹不变或时间统计足够。','', '三、固定评分的适用性与覆盖'])
for label,seeds in [('模块',[201,202,203]),('环形',[301,302,303])]:
 z=[x for x in ranks if int(x['seed']) in seeds and x['method']=='temporal'];text.append(f"{label}图15个图×输入单元：联合评分一致率{rng([float(x['macro_concordance']) for x in z])}；可分辨方向对覆盖率{rng([int(x['resolved_direction_pairs'])/int(x['possible_direction_pairs']) for x in z],100)}%。一致率仅在各方法共同可分辨子集上计算。")
text.append('每图先按目标对宏平均，再对5输入等权平均，联合评分减去预定对照：')
for s in SEEDS:
 vals=[x for x in factors if int(x['seed'])==s];text.append(str(s)+' '+', '.join(x['comparator']+' '+format(float(x['equal_input_mean_delta']),'+.4f') for x in vals))
for fam,gates in J['family_gates'].items():text.append(fam+'：5种评分对照在3张图各自等权输入平均上的正差判据 '+str([x['all_three_positive'] for x in gates['score']])+'。')
for comp in ['random','f1m0','f0m1','mean','shuffle']:
 vals=[float(x[u]) for x in factors if x['comparator']==comp for u in INPUTS];text.append(f'{comp}:30个图×输入单元正差 {sum(v>1e-12 for v in vals)}/30，最小差{min(vals):+.4f}。')
for label in ['1-1.1','1.1-1.25','1.25-1.5','1.5-2','>2']:
 z=[float(x['macro']) for s in SEEDS for x in read(R/f'seed{s}/directions/ratio-strata.csv') if x['method']=='temporal' and x['ratio_bin']==label and x['macro']];text.append(f'安全半径比的保证下界分层 {label}：联合评分宏一致率范围{rng(z)}，{len(z)}个非空图×输入单元。')
active=[x['macro_concordance'] for a in anal for x in a['rank'] if x['subgroup']=='active_nonnull' and x['method']=='temporal' and x['macro_concordance'] is not None];text.append('活跃且非零投影子集的联合宏一致率范围：'+rng(active)+'。')
text.extend(['这些是证书括号所决定的可分辨方向排序；未分辨方向对不算预测错误也不算成功。完整敏感度与评分共享参考活动和分支动力学，因此不能将高一致率称为独立因果机制证明；也未证明评分比直接认证更省计算。','', '四、跨输入迁移'])
for s in SEEDS:
 j=load(R/f'seed{s}/directions/analysis.json');z=next(x for x in j['conditioned_vs_frozen'] if x['probe']=='F_H' and x['method']=='temporal');rev=next(x for x in j['reversals'] if x['input_a']=='G_B' and x['input_b']=='F_H' and x['method']=='temporal');sel=next(x for x in j['selection_transfer'] if x['probe']=='F_H' and x['control']=='mean');text.append(f"{s}: G_B评分用于F_H={z['frozen_G_B']:.4f}，F_H自身评分={z['input_conditioned']:.4f}；两输入共同可分辨方向对相反排序{rev['reversals']}/{rev['resolved_both']}={rev['fraction']:.2%}；G_B所选方向相对G_B平均活动所选方向，在F_H的结果={sel['counts']}")
text.extend(['接近50%的相反排序比例表示排序近似去相关，不是系统性反转。胜平负和未分辨均报告，不预设冻结方向一定失败。上述排序用同一目标对的方向，不能作为跨图安全半径的同成本比较。','', '五、认证覆盖、失败与验证'])
stops=collections.Counter()
for a in anal:stops.update(a['radii_stops'])
text.append('全部停止结果：'+str(dict(stops)))
text.append(f"正认证下界{sum(v['rechecked_positive'] for v in valid)}/8960；零宽且未获区间认证{sum(len(v['zero_uncertified']) for v in valid)}；参考目标对静默条件{sum(a['silent_conditions'] for a in anal)}，零投影条件{sum(a['projection_null_conditions'] for a in anal)}。静默不是排除理由，也不是活跃动力学鲁棒性的证据。")
text.append('各图5输入认证下界中位数（%），顺序G_B,F_B,F_H,G_T,F_HT：')
for s,v in zip(SEEDS,valid):
 c=[next(z for z in J['coverage'] if z['seed']==s and z['input']==u) for u in INPUTS];text.append(f"{s}: "+', '.join(f"{z['lower_median']*100:.5f}" for z in c)+f"；正下界{v['rechecked_positive']}/{v['intervals']}；不同浮点权重/事件/状态区域{v['distinct_weights']}/{v['distinct_events']}/{v['distinct_states']}")
 if v['zero_uncertified']:
  groups=collections.Counter((x['pair'],x['input']) for x in v['zero_uncertified']);pp=load(R/f'seed{s}/pool-lock.json');desc=read(R/f'seed{s}/directions/mechanistic-descriptors.csv');queries=read(R/f'seed{s}/directions/queries.csv')
  for (pair,u),n in groups.items():
   dd=next(x for x in desc if int(x['pair'])==pair and x['input']==u);qq=next(x for x in queries if int(x['pair'])==pair and x['probe']==u and float(x['rho'])==0);text.append(f"  未获零宽认证：目标对{pair}、节点{pp[pair]['targets']}、输入{u}、{n}方向；零扰动区间原因{qq['cert_reason']}，零扰动点回放通过；参考最小阈值裕度{dd['margin_min']}。这是已观测的包络分支无法判定，不能反推真实不安全或只凭此唯一归因于某种余项。")
text.append(f"三点见证(-L,0,+L)中，正区域包含实际不同权重配置{sum(v['distinct_weights'] for v in valid)}、事件流{sum(v['distinct_events'] for v in valid)}、状态轨迹{sum(v['distinct_states'] for v in valid)}。原生点回放端点{sum(v['endpoint_replays'] for v in valid)}，有效包络的包含检查端点{sum(v['containment_endpoint_replays'] for v in valid)}；二者不混称。")
text.append(f"精确有理数校验{sum(len(v['exact_cases']) for v in valid)}个固定案例、{sum(v['exact_endpoint_values'] for v in valid)}个界端点值；失败见证的独立Python回放检查{sum(v['point_prefix_values_validated'] for v in runs)}个状态端点值；搜索共{sum(v['radius_queries'] for v in runs)}次条件内去重的半径查询。")
text.extend(['共同分支认证只保证指定固定连接支持、联合权重方向、有限窗口内的脉冲和执行分支；连续状态可以变化。L是已证安全区间的下界，U来自实际失败见证；中间证明间隙不说明真实安全集断裂，也不能未经诊断归因于某一种数值膨胀。25%上限是截尾，不是真实边界。',
'最小双边交换的可见性实验与固定支持权重扰动的认证实验是两类干预。本轮未给全部交换图提供集合认证，也没有复现旧17个单点交换案例的认证率。','', '六、成本和结构背景'])
for s in SEEDS:
 z=[x for x in J['cost'] if x['seed']==s];text.append(str(s)+' '+', '.join(x['method']+' '+f"{x['median_ms']:.4f} ms" for x in z))
text.append('上述包括权重/事件生成的Python封装同案例计时：有限点回放不能证明整个区间，认证成功率和早停也影响时间。未宣称相对优化后的原生批量回放有运行时间优势。')
for s in SEEDS:text.append(str(s)+' '+str(load(R/f'seed{s}/structure.json')))
minimum=min(float(x['min_voltage']) for s in SEEDS for x in read(R/f'seed{s}/reference-activity.csv'));text.append(f'新原图参考轨迹最低电压坐标{minimum}，无生物物理单位。更换图生成法没有解决无下界、块内同步、确定性及30 ms窗口限制。')
text.extend(['', '七、审稿判断与下一版取舍',
'值得纳入下一版：它排除了“只在原独立连边生成器里出现”的最直接替代解释，且没有根据新结果调整方向评分或认证规则。可加强的主张是：在这两种新连接亲和规则的固定样本上，总驱动匹配仍不足以决定交换可见性；输入条件评分与有限时域共同分支区域的关系可以跨这些图重现。',
'不加强为普适规律、最优拓扑或跨神经元模型结论。三个种子/图族很有限；两类共享加权抽样器和同一执行核；图之间逐节点统计不同，权重方向支持大小不同。不能把较大的半径称为更好的几何保真，更不能将本轮结果回溯性地推广到旧时间抵消/剂量、代理记忆或压缩收益。',
'建议下一版以一个跨生成机制验证小节合并前轮3图和本轮6图，报告图级数值、覆盖及负结果；不用再添加一套理论主张。此处只是分析建议，当前中英文冻结稿和复现ZIP均未改。',
'原多原图报告的8800端点勘误另存research/reviews/multigraph-review-20261109.txt；旧包未静默修改。本轮明确区分点回放与有效包络包含端点。',''])
(R/'REPORT.zh.txt').write_text('\n'.join(text))
print('Wrote REPORT.zh.txt')
