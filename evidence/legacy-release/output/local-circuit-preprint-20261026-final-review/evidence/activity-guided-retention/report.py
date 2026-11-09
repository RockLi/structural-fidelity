#!/usr/bin/env python3
"""Post-outcome presentation only; does not change the locked analysis or design."""
from pathlib import Path
import base64,csv,html,json,statistics

R=Path(__file__).resolve().parent
def read(name): return json.loads((R/name).read_text())
def rows(name):
    with (R/name).open() as f:return list(csv.DictReader(f))
def main():
    s=read('analysis/summary.json');audit=read('audit.json');repro=read('reproduction-verification.json')
    assert audit['passed'] and repro['status']=='pass'
    selections={(r['block'],r['policy']):r for r in read('selection.json')}
    gains=[1-selections[b,'coactivity']['J_coactivity']/selections[b,'random']['J_coactivity'] for b in range(10)]
    metrics={(r['probe'],r['policy'],r['metric']):r for r in s['metric_summaries']}
    endpoints={r['policy']:r for r in s['heldout_policy_endpoints']}
    comparisons={(r['probe'],r['comparator']):r for r in s['contrasts']}
    policies=['random','mean','coactivity','shuffled'];labels=['随机','平均活动','共活动引导','逐源时间打乱']
    probes=['train','spatial','temporal','spatiotemporal'];plabels=['训练输入','更换输入位置','拆分脉冲时间','同时更换位置与时间']
    main_table=[]
    for p,label in zip(probes,plabels):
        main_table.append([label]+[f'{100*metrics[p,q,"raw_slot_l1"]["mean"]:.2f}%' for q in policies])
    main_table.append(['三个留出的等权平均']+[f'{100*endpoints[q]["mean"]:.2f}%' for q in policies])
    secondary=[]
    for p,label in zip(probes[1:],plabels[1:]):
        vals=[metrics[p,'coactivity',m]['mean']-metrics[p,'random',m]['mean'] for m in ['raw_slot_l1','bin1ms_l1','cumulative_l1','van_rossum_tau1','state_rms_standardized']]
        secondary.append([label]+[f'{100*v:+.2f}' for v in vals[:3]]+[f'{v:+.4f}' for v in vals[3:]])
    contrasts=[]
    for p,label in [('random','随机'),('mean','平均活动'),('shuffled','逐源打乱')]:
        c=comparisons['heldout_mean',p]
        contrasts.append([label,f'{100*c["mean"]:+.2f}',f'{100*c["median"]:+.2f}',f'{100*c["minimum"]:+.2f} 至 {100*c["maximum"]:+.2f}',f'{c["coactivity_better"]}/{c["tied"]}/{c["coactivity_worse"]}'])
    def tab(headers,data):return '<table><thead><tr>'+''.join('<th>'+html.escape(v)+'</th>' for v in headers)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+html.escape(v)+'</td>' for v in rr)+'</tr>' for rr in data)+'</tbody></table>'
    def image(name,caption):
        data=base64.b64encode((R/'analysis/figures'/f'{name}.png').read_bytes()).decode()
        return f'<figure><img alt="{html.escape(caption)}" src="data:image/png;base64,{data}"><figcaption>{caption}</figcaption></figure>'
    lead='活动引导选图没有改善预先指定的逐槽轨迹保真度；评分与闭环结果的脱节，在训练输入本身就已经出现。'
    text=f'''同预算活动引导结构保留：冻结设计后的实验结果
2026-10-25 | 结果分析稿，尚未写入 preprint

{lead}

实验范围
使用现有 seed 99 人工 E/I 网络：125块，每块100个同步单元（至多125条不同的单元轨迹），2845条边，dt=0.1 ms，300槽/30 ms。保持原神经元核、不应期、唤醒和排序路由，所有条件使用显式执行。
每张候选图移除原邻接282条（9.9121%），同时新增282条；原邻接保留2563条（90.0879%），边总数始终2845。EE/EI/IE/II分别替换146/60/64/12条。每节点分臂入出度、权重多重集、强度和延迟精确保留；无自环或重边。同预算是结构修改预算，不是实际运行成本预算或压缩。
共10个独立候选池，每池64张候选图。随机、平均活动、共活动和时间打乱四种规则从同一池选图。打乱固定32次逐源独立时间置换；各源计数分布保持，共活动关系改变。共活动评分是零滞后二阶量，不能解释为完整时间顺序或记忆。
训练输入：20个E块，幅度150，0–8 ms持续驱动。三个留出分别改变20块输入位置、将驱动拆成0–4和8–12 ms两段、同时改变两者；总外部幅度均为240000。新旧输入掩码重叠2块，只有一个新掩码；拆分条件的输入终止更晚，30 ms内恢复观察期也更短。
设计、源代码、规则、预算、输入和分析先锁定；640图与40次策略选择再次锁定后才运行新条件。33张唯一选中图加原图，四输入共136次科学运行，另有1次技术重复；160为策略×输入评估记录，并非160张独立图。10个候选池也不是10个原始网络。

主结果
主终点为每池三个留出输入的具名块逐槽L1等权平均，再比较共活动减对照。各输入用自身原图总脉冲数归一。它不是错误概率，漏发、增发和脉冲移位均计入，可超过100%。
条件 | 随机 | 平均活动 | 共活动引导 | 逐源时间打乱
'''+ '\n'.join(' | '.join(r) for r in main_table)+f'''

共活动相对对照的配对差（百分点；负数有利于共活动）
对照 | 均值 | 中位数 | 范围 | 较好/相同/较差
'''+ '\n'.join(' | '.join(r) for r in contrasts)+f'''

训练评分J在全部10池都低于随机选择，配对降幅均值{100*statistics.mean(gains):.3f}%，中位数{100*statistics.median(gains):.3f}%，范围{100*min(gains):.3f}%–{100*max(gains):.3f}%。这是从64候选取最小值的预期结果，只说明优化按设计执行。
同训练输入的闭环逐槽L1反而平均增加9.25个百分点，8/10池更差；留出主终点平均增加12.79个百分点，8/10池更差。主终点相对平均活动和时间打乱也没有平均收益，分别增加3.24和1.12个百分点。因此不能只称为跨输入泛化失败：训练目标与闭环目标本身已不一致。

预设次级读出的条件性反转
下表全部为共活动减随机；前三列单位为百分点，后两列为指标自身单位。负数表示误差更小。
条件 | 逐槽L1 | 1ms L1 | 累计计数L1 | 归一化平方van Rossum | 标准化状态RMS
'''+ '\n'.join(' | '.join(r) for r in secondary)+'''
仅改变时间安排时，1 ms、累计计数、van Rossum和状态RMS在同一批7/10候选池中改善，而逐槽L1仍在8/10池更差。这些相关指标不是四次独立验证，不能替代未获支持的主终点。误差分量比例Rcount较低也不等于总误差更小。
指标与所有输入在运行前固定；对上述排序反转的科学解释是在结果之后形成的。

科学解释与边界
在线性输入映射层并忽略浮点舍入，对每个E/I通道有 W' s' - W s = (W'-W)s + W'(s'-s)。本评分衡量沿冻结参考活动的第一项，没有约束候选网络改变活动后的反馈项。恒等式解释了为何降低评分不保证闭环误差降低；这次实验没有识别阈值、调度、反馈增益等具体失效机制，也没有测量混沌。
评分更低不等于输入差为零。本结果不违反现有有限时域推论的严格零失配条件，不构成一般活动引导方法无效、随机结构更优、必须引入记忆或已经实现压缩的证据。
绝对逐槽误差很大，四种规则都没有展示高保真逐槽保留。简化核的电压为未校准的模型坐标；休眠与不应期更新规则沿用旧实现，不能据此外推标准生物物理模型。只有一个原图、一个9.9121%修改预算、一个新空间掩码、固定候选生成规则和30 ms窗口；不能排除更小预算、其他输入评分或更丰富模型的不同结果。候选生成不是均匀图零分布，不作p值或总体区间推断。

如何使用这组结果
它比事后相关分析增加了一项前瞻性的、同结构预算的规则检验：一个明确的活动评分被成功优化，却未实现指定的闭环收益。科学增量在于限制一个合理选图准则的适用范围，并显示输入与读出依赖；尚不足以声称找到有效结构保留算法。
建议将其保留为独立研究模块。若纳入preprint，适合作为现有主线后的紧凑“活动引导选择的条件性失效”小节，主报告失败终点，完整展示次级反转；不将论文改成压缩或成功优化方法。按本次任务安排，现有中英文preprint未修改。

验证与交付
原训练轨迹与归档300×125×10个记录字段逐位相等，计数CSV逐字节相等。所有运行通过有限值、块内同步、外部输入剂量和边访问计数校验。
独立程序重建640张候选图，核算2560个分数、选图、图统计约束及全部关键运行指标。
在全新目录中重新生成候选、编译并运行所有136个条件：图/评分/选择、状态载荷、计数CSV和10份数值分析文件完全一致；运行JSON除测时字段外相同。该技术复现不增加科学样本量。
全部源代码、锁定协议、候选图、原始结果、分析、图和校验报告随复现包保存；编译器rustc1.98.1、edition2024、opt-level3，Apple arm64 Darwin。完整执行方式见README.txt。
'''
    (R/'RESULTS.zh.txt').write_text(text)
    sections=text.split('\n\n')
    body=''
    for section in sections:
        lines=section.splitlines()
        # Tables are rendered separately below; keep a complete plain-text version for inspection.
        if ' | ' in section:continue
        body+='<p>'+html.escape(section).replace('\n','<br>')+'</p>\n'
    content=f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>活动引导结构保留：实验结果</title><style>
body{{max-width:1100px;margin:40px auto;padding:0 24px;color:#182b39;background:#fbfcfd;font:17px/1.85 -apple-system,BlinkMacSystemFont,"PingFang SC",sans-serif}}h1{{font-size:30px;line-height:1.35}}h2{{font-size:22px;margin-top:38px}}.lead{{font-size:20px;background:#eaf2f3;padding:20px;border-left:5px solid #287e87}}.meta{{color:#607180;font-size:14px}}table{{width:100%;border-collapse:collapse;font-size:14px;background:white;margin:18px 0}}td,th{{padding:10px;border-bottom:1px solid #dce3e8;text-align:right}}th:first-child,td:first-child{{text-align:left}}th{{background:#eef3f6}}img{{max-width:100%;height:auto}}figure{{margin:25px 0;background:white}}figcaption{{color:#566674;font-size:14px}}.note{{font-size:14px;color:#566674}}pre{{white-space:pre-wrap;word-break:break-word;font:15px/1.8 -apple-system,BlinkMacSystemFont,"PingFang SC",sans-serif;background:white;padding:20px;border:1px solid #e0e7eb}}@media print{{body{{margin:0;font-size:11px}}figure,table{{break-inside:avoid}}}}
</style><h1>同预算活动引导结构保留</h1><p class="meta">2026-10-25 · 已冻结设计、完成运行与独立复现 · 结果分析稿，尚未写入 preprint</p><p class="lead">{lead}</p>
<h2>主结果：共活动引导未改善逐槽轨迹</h2>{tab(['条件']+labels,main_table)}<p class="note">每个数为10个候选池的均值。归一化具名块逐槽L1可超过100%，不是错误概率。三个留出先在每池等权平均，再在池间汇总。</p>
{tab(['共活动减该对照','均值差 / pp','中位数 / pp','范围 / pp','较好/相同/较差'],contrasts)}
{image('training-and-transfer','训练闭环与留出闭环均未得到共活动引导的主终点收益；点为各候选池，横线为均值。')}
<h2>次级读出：部分改善取决于输入和时间尺度</h2>{tab(['留出条件','逐槽L1 / pp','1ms L1 / pp','累计L1 / pp','van Rossum差','状态RMS差'],secondary)}<p class="note">均为共活动减随机，负数表示误差更小。这些是预先固定的次级指标；对排序反转的解释属于结果后的分析，不能替代主终点。</p>
<h2>完整设计、解释及边界</h2><pre>{html.escape(text)}</pre>
<h2>全部留出条件与配对差</h2>{image('heldout-policy-errors','四种选图规则在全部留出输入中的逐槽误差。')}{image('paired-heldout-contrasts','主终点的10个配对差；负数有利于共活动，重合选图保留为零差。')}{image('secondary-count-readouts','累计计数误差及误差中的计数组成；比例下降不等于保真度提高。')}
</html>'''
    (R/'RESULTS.zh.html').write_text(content)
    (R/'report-data.json').write_text(json.dumps(dict(presentation_status='Post-outcome summary of locked analysis; no rule changes',training_score_relative_reduction=dict(mean=statistics.mean(gains),median=statistics.median(gains),min=min(gains),max=max(gains),all_positive=all(v>0 for v in gains)),main_table=main_table,paired_table=contrasts,secondary_table=secondary,visual_QA='All four PNG figure sets inspected; no clipping or overlapping labels observed'),ensure_ascii=False,indent=2)+'\n')
    print('Wrote self-contained HTML, plain-text report and derived report tables.')
if __name__=='__main__':main()
