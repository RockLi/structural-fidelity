#!/usr/bin/env python3
from pathlib import Path
import csv,json,statistics
R=Path(__file__).resolve().parent

def read(n):return list(csv.DictReader((R/'results'/n).open()))
scores=read('rank-summary.csv');strata=read('separation-strata.csv');diffs=read('factor-differences.csv');width=read('bracket-widths.csv');tie=read('tie-rule-audit.csv');cover=json.loads((R/'results/summary.json').read_text())['coverage'];dose=json.loads((R/'dose/summary.json').read_text());validation=json.loads((R/'validation.json').read_text())
probes=['tonic','global_burst','focal_burst'];names=['Tonic','Global burst','Focal burst']
def score(u,m):return next(x for x in scores if x['probe']==u and x['method']==m)
def tab(headers,rows):return '\n'.join([' | '.join(headers),*[' | '.join(map(str,row)) for row in rows]])
p=[]
p.append('评分因子消融、排序覆盖与剂量数据审计\n2026-11-08\n')
p.append('结论\n本轮完全使用归档数据，没有新网络仿真、扰动回放、证书调用或半径细化，也没有修改论文。结果支持一个更具体的模型内观察：时间滤波与逐时点阈值裕度共同使用时，方向排序远好于任何一个因子单独使用；这不是“裕度单独决定安全性”的证据。优势主要体现在可判定且有较大保证分离的方向对，不能把约0.9推广为全部候选对的准确率。剂量部分找到了10条完整的三预算随机选择链，具备后续离线三点比较条件，但不是640张候选都已有仿真，也没有同链单次交换剂量点。')
p.append('1. 分析设计与可信度\n本轮方案在计算新分析结果前写入PROTOCOL.txt并存SHA256；既有结果此前已知，因此所有新分析仍为事后分析。912个既有方向×输入条件、19个目标对、每对16方向保持不变。F0/F1分别表示不过滤/使用原d≈0.9滤波，M0/M1表示不除裕度/除以max(|v_pre−30|,2^-20)。四种方法统一在原参考执行且不应期允许的时点取最大值。原raw对照曾覆盖所有时点，单独保留legacy_raw，不冒充公平的F0M0。原Mean和Shuffle已同时包含滤波与裕度；本轮还为两者计算相同2×2因子组合。全部方向/目标/CSV均保留。')
p.append(f'复核：重构并核对112,500个参考块×时间槽；2,736个原Temporal/Mean/Shuffle分数逐值一致；18个原宏平均结果复现。独立向量化核查{validation["independent_rank_and_completion_checks"]}组排序与完成范围，另以矩阵投影和卷积核查192个分数。档案输入哈希检查{validation["input_file_checks"]}次。参考状态重构只是读取既有轨迹并核对其更新，不推进任何新扰动条件。')
p.append('2. 主因子消融\n以下为各目标对内一致率的宏平均，仅使用该输入下相同的可判定方向对；预测平局计0.5。')
p.append(tab(['方法',*names],[[label,*[f'{float(score(u,m)["macro"]):.4f}' for u in probes]] for m,label in [('original_f0m0','都不用'),('original_f1m0','仅滤波'),('original_f0m1','仅裕度'),('original_f1m1','滤波＋裕度'),('mean_f1m1','平均活动＋相同滤波/裕度'),('shuffle_f1m1','独立移位＋相同滤波/裕度')]]))
p.append('单独加入裕度在Tonic/Focal几乎没有平均提升，Global有约5.10个百分点的提升；仅滤波约提升1.39–6.70个百分点。相比之下，已有滤波时再加入裕度提升26.77–32.11个百分点。不能把联合收益归为一个因子的普遍主效应。')
p.append(tab(['比较', '输入','均值差/百分点','目标对胜/平/负'],[[{'filter_with_margin':'已有裕度时加入滤波','margin_with_filter':'已有滤波时加入裕度','interaction':'一致率尺度的因子交互'}[x['contrast']],x['probe'],f'{100*float(x["mean"]):+.2f}',f'{x["wins"]}/{x["ties"]}/{x["losses"]}'] for x in diffs if x['source']=='original' and x['contrast'] in ['filter_with_margin','margin_with_filter','interaction']]))
p.append('这里的“交互”仅指一致率表的差中差 C11−C10−C01+C00，不是生物学因果交互或统计显著性结论。51个输入×目标对条目复用同一原图与目标，不是51个独立网络样本。各输入中联合评分均优于只含单一因子的平均结果，但并非在每个目标对上都严格占优。')
p.append('平局诊断（在看到高平局数后追加的数值核查）：仅裕度的可判定比较中有863/1353、1146/1811、740/1624个评分平局，均为浮点数值完全相等，不是1e-10容差人为合并。把判平改为严格数值相等，联合评分和仅裕度宏平均均不变；仅滤波的Tonic由0.5873变为0.5952，Global由0.5883变为0.5887，Focal不变，主要结论不变。此检查不能证明为什么分数相等，更不能据此断言所有无滤波方法无效。')
p.append('3. 覆盖率与未决比较\n每种输入共19×C(16,2)=2,280个方向对。以下类别互斥；证明间隙重叠优先归入该类。')
p.append(tab(['输入','可判定','覆盖率','双上限','证明间隙重叠','有限区间重叠','其他上限重叠'],[[x['probe'],x['resolved'],f'{100*x["resolved"]/x["total"]:.2f}%',x['both_capped'],x['proof_gap_overlap'],x['finite_overlap'],x['cap_overlap']] for x in cover]))
p.append('未决不等于“真实半径接近”：Tonic和Focal分别有506和335个比较因为两侧都认证到25%上限而无法排序。上限截断可能遮蔽更大的差异；它不是半径相等。证明间隙也不能填成失败或不安全。')
p.append(tab(['输入','联合宏平均（可判定）','联合微平均（可判定）','全部比较的宽松完成范围'],[[u,f'{float(score(u,"original_f1m1")["macro"]):.4f}',f'{float(score(u,"original_f1m1")["micro"]):.4f}',f'[{float(score(u,"original_f1m1")["all_pair_completion_lower"]):.4f}, {float(score(u,"original_f1m1")["all_pair_completion_upper"]):.4f}]'] for u in probes]))
p.append('完成范围不是置信区间，也不是准确率估计：对每个未决比较，未知排序的得分允许取0至1；预测为平局的取0.5。该范围忽略真实排序的传递约束，故刻意宽松，不保证端点可同时达到。它防止把可判定子集的好成绩直接推广到全部比较。已判定方向对也不是独立样本。')
for x in cover:
 ex=x['excluded_targets'];p.append(x['probe']+'没有可判定比较的目标对：'+('无。' if not ex else '；'.join(f'[{y["target_a"]},{y["target_b"]}]（目标脉冲槽计数{y["target_spike_slots"]}，上限条件{y["cap_conditions"]}/16）' for y in ex)+'。'))
p.append('Focal的[107,114]有活动，但16方向的区间完全重合于约[0.00310516,0.00321960]，不能据此断言真实半径相等。另两个Focal目标对静默。Tonic三个被排除目标对并非静默。')
p.append('4. 区间分离程度\n有已知排序时，定义g=L_较安全/U_较不安全。g是真实安全半径比的保守下界，不是实际半径比；低g也不保证实际半径接近。分箱边界在本轮结果计算前固定，未用区间中点代替真值。')
levels=['1-1.10','1.10-1.25','1.25-1.50','1.50-2','>2']
p.append(tab(['g分箱',*names],[[level,*[f'{float(next(x for x in strata if x["probe"]==u and x["method"]=="original_f1m1" and x["dimension"]=="ratio_bin" and x["level"]==level)["macro"]):.3f} (n={next(x for x in strata if x["probe"]==u and x["method"]=="original_f1m1" and x["dimension"]=="ratio_bin" and x["level"]==level)["n"]})' for u in probes]] for level in levels]))
p.append('小保证分离组的一致率约0.71–0.74，明显低于整体0.88–0.91；g>2组约0.93–0.99。这说明整体成绩不能代表细微差异的辨识精度。各分箱的目标组成不同，也不能把曲线当成因果剂量关系。排除所有涉及上限截断的比较后，联合评分宏平均为0.9096/0.8604/0.8963，优势不完全由“一侧上限、另一侧较小”的容易比较造成。全部方法、每箱目标数及微平均见separation-strata.csv。')
p.append('有限区间的相对宽度(U−L)/U：')
p.append(tab(['输入','停止类型','条件数','最小/中位/最大'],[[u,st,len(z),'/'.join(f'{f(z):.4f}' for f in [min,statistics.median,max])] for u in probes for st in ['bracket_tolerance','proof_gap'] for z in [[float(x['relative_width']) for x in width if x['probe']==u and x['stop']==st]]]))
p.append('5. 跨输入评分\n沿用Tonic的联合评分到Global/Focal，宏平均仍为0.6068/0.5385；换用各输入自身参考重新计算相同评分后为0.8805/0.9110。该结果不意味着无需目标输入参考的迁移预测成功；本轮消融没有改变既有固定Tonic选图迁移失败的结论。')
p.append('6. 剂量数据可用性与配对\n逐项核查1,920个候选图与记录的按通道交换前缀，90个已完成训练变体的CSV/NPZ/JSON哈希通过。三个预算的外部输入逐字节相同、原图参考状态逐位相同，且与早期Focal参考逐位一致。')
p.append(tab(['替换原邻接数','比例','实际双边交换数','候选数','已运行变体数'],[[x['replaced_adjacencies'],f'{100*x["fraction"]:.3f}%',x['accepted_swaps'],x['candidate_seeds'],x['unique_completed_graphs']] for x in dose['budgets']]))
p.append(tab(['预算组合','同链且有轨迹','其中随机策略'],[[x['budgets'],x['available_chains'],x['random_policy_chains']] for x in dose['intersections']]))
p.append('全部10条完整三预算链均为原随机选择（每候选池一条）；平均活动、共活动和打乱策略在同一池内都没有三个预算保持同一候选链的实例。可以据现有数据做14→28→141次交换的10条配对三点描述，也可纳入共同原图零剂量点。该分析只代表一个原图、一个已知Focal训练输入和这个候选生成规则。不能把跨预算各自挑选的最好图当作同链剂量比较。早期19个最小交换虽然输入相同，但属于不同候选链，不能伪装成这10条链的第一剂量点。这里没有计算R_count或剂量曲线；后续若做，不需要新增这三个预算的仿真，但不能据三个非零剂量断言饱和拐点或普遍剂量定律。')
p.append('7. 对科学主张的建议\n可以加强的主张：在同支持、同预算和同评价时点的既有方向集合中，滤波与逐时点参考裕度具有一致率层面的互补作用；联合评分在可判定的方向对上明显强于任一单因子，但辨别小保证分离的能力较弱。\n应收紧的主张：不再单独强调“阈值裕度是核心机制”，不写“全部方向约90%可预测”，不把完整敏感度的一致性当作独立预测，也不把分数消融当作网络层面的因果干预。\n后续优先级：本轮已足以重写评分解释和覆盖边界。若需要支撑旧误差组成主线，现有10条随机配对链可支持有限的三预算离线检查；不应为保留“强发现”的措辞而扩展成大量新仿真。机制分离或跨模型外推仍需独立证据，本轮不声称已完成。')
p.append('文件\nPROTOCOL.txt / protocol-lock.json：本轮事后分析方案与锁定时间。\nresults/：912行因子分数、方向对级比较、覆盖、分箱、目标内配对差与跨输入结果。\ndose/：全部640条候选链的可用性、1,920次前缀核对及策略配对。\nvalidation.json：独立数值核查。\nanalysis-summary.png/.pdf：结果概览。\nREADME.txt：复算命令与范围。\n原稿、已发布到本地的双语文件及原复现包均保持不变。')
(R/'REPORT.zh.txt').write_text('\n\n'.join(p)+'\n')
print(R/'REPORT.zh.txt')
