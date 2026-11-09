#!/usr/bin/env python3
from pathlib import Path
import csv,json,statistics,os
ROOT=Path(__file__).resolve().parent;D=ROOT/'results'
def read(n):return list(csv.DictReader((D/n).open()))
def table(p,rows):
 with p.open('w') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def txt(headers,rows):return '\n'.join([' | '.join(headers),*[' | '.join(map(str,r)) for r in rows]])
r=read('per-chain.csv');summ=read('budget-summary.csv');pair=read('paired-summary.csv');decomp=read('decomposition-summary.csv');bins=read('readout-offsets.csv');js=json.loads((D/'summary.json').read_text());B=['p01','p02','full'];labels=['0.984%','1.968%','9.912%']
def stat(b,m,field='mean'):return float(next(x for x in summ if x['budget']==b and x['metric']==m)[field])
readout=[]
for w in [1,2,10,50,300]:
 for b in B:
  vals=[statistics.mean(float(x['normalized']) for x in bins if x['budget']==b and int(x['width_slots'])==w and int(x['offset_slots'])==o) for o in range(w)]
  readout.append(dict(budget=b,width_slots=w,zero_offset_mean=vals[0],all_offset_mean_min=min(vals),all_offset_mean_max=max(vals)))
table(D/'readout-budget-summary.csv',readout)
os.environ.setdefault('MPLCONFIGDIR','/tmp/score-factor-mpl')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False,'pdf.fonttype':42})
fig,axes=plt.subplots(2,2,figsize=(11.8,8.4),layout='constrained');cols=plt.cm.tab10(np.arange(10));x=np.array([28,56,282])/2845*100
for ax,metric,title,ylabel in [(axes[0,0],'X','A  Raw-slot discrepancy','Dslot / original spike count (%)'),(axes[0,1],'Y','B  Whole-window count discrepancy','Dcount / original spike count (%)'),(axes[1,0],'Rcount','C  Fraction retained after time accumulation','Dcount / Dslot (%)')]:
 for i in range(10):
  ys=[float(next(z for z in r if int(z['block'])==i and z['budget']==b)[metric])*100 for b in B];ax.plot(x,ys,'o-',color=cols[i],alpha=.7,linewidth=1,markersize=4)
 ax.plot(x,[stat(b,metric)*100 for b in B],'s-',color='black',linewidth=2.7,markersize=6,label='Mean across 10 chains');ax.set_xticks(x,labels);ax.set_xlabel('Replaced original adjacencies');ax.set_ylabel(ylabel);ax.set_title(title,loc='left',fontweight='bold');ax.set_xscale('log');ax.set_xlim(.8,12);ax.set_xticks(x,labels);ax.xaxis.set_minor_formatter(matplotlib.ticker.NullFormatter())
 if metric=='Rcount':ax.legend(frameon=False,loc='upper left')
a=axes[1,1];x=np.arange(3);vals1=[float(z['mean_magnitude_component'])*100 for z in decomp];vals2=[float(z['mean_retained_fraction_component'])*100 for z in decomp];a.bar(x-.18,vals1,width=.36,color='#3f7f9e',label='Discrepancy-magnitude term');a.bar(x+.18,vals2,width=.36,color='#d89343',label='Retained-fraction term');a.plot(x,[float(z['mean_delta_Y'])*100 for z in decomp],'kD',markersize=6,label='Total count-error change');a.axhline(0,color='gray',linewidth=1);a.set_xticks(x,['28 → 56','56 → 282','28 → 282']);a.set_xlabel('Replaced original adjacency counts');a.set_ylabel('Mean paired change (percentage points)');a.set_title('D  Exact symmetric product decomposition',loc='left',fontweight='bold');a.legend(frameon=False,fontsize=9,loc='upper left');a.set_ylim(-1.2,23)
fig.suptitle('Ten archived random paired chains under the same focal input\nPost hoc analysis; colored lines are chains; no new simulations',fontsize=13)
fig.savefig(ROOT/'paired-dose-summary.png',dpi=180);fig.savefig(ROOT/'paired-dose-summary.pdf',metadata={'CreationDate':None,'ModDate':None});plt.close(fig)
fig,ax=plt.subplots(figsize=(7.5,4.6),layout='constrained');widths=[1,2,10,50,300]
for b,label,color in zip(B,labels,['#2166ac','#dd7b25','#168376']):
 z=[next(q for q in readout if q['budget']==b and q['width_slots']==w) for w in widths];ax.plot(np.array(widths)*.1,[v['zero_offset_mean']*100 for v in z],'o-',color=color,label=label);ax.fill_between(np.array(widths)*.1,[v['all_offset_mean_min']*100 for v in z],[v['all_offset_mean_max']*100 for v in z],color=color,alpha=.18)
ax.set_xscale('log');ax.set_xticks(np.array(widths)*.1,['0.1','0.2','1','5','30']);ax.set_xlabel('Bin width (ms); lines use zero offset');ax.set_ylabel('Mean identified-bin L1 / reference spikes (%)');ax.legend(title='Edited adjacency budget',frameon=False);ax.set_title('Time aggregation changes the observed error\nBands: all bin offsets, not confidence intervals',fontsize=12);fig.savefig(ROOT/'readout-sensitivity.png',dpi=180);fig.savefig(ROOT/'readout-sensitivity.pdf',metadata={'CreationDate':None,'ModDate':None});plt.close(fig)
p=[]
p.append('10条随机配对链的剂量与误差组成分析\n2026-11-08\n结论：建议纳入论文，但作为对旧误差组成主张的配对检验与修正，不作为新的普遍剂量定律。')
p.append('范围\n严格使用上轮已确认的10条完整随机链，三种预算共30条既有轨迹。所有轨迹来自同一125块原图、相同Focal输入、30ms窗口与同一参考。各链预算为按通道嵌套交换前缀：28/56/282个原邻接被替换，实际为14/28/141次双边交换。没有新增仿真、参数选择、点回放或认证，也没有修改论文。方案在本轮计算前锁定，但原始结果此前已存在，因此所有本轮发现是事后分析。原始选择规则为每个候选池固定随机抽取一个编号，不是本轮根据结果挑选。')
p.append('1. 三预算的主要结果\n误差均以共同参考总计数147,600归一。X=Dslot/Nref为逐槽逐块L1，Y=Dcount/Nref为每块30ms总计数L1，R=Dcount/Dslot为时间累积后的保留比例。下面均为10条链的均值。')
p.append(txt(['预算','X/百分比','Y/百分比','R/百分比','时间抵消比例/百分比'],[[label,*[f'{100*stat(b,m):.2f}' for m in ['X','Y','Rcount']],f'{100*(1-stat(b,"Rcount")):.2f}'] for b,label in zip(B,labels)]))
p.append('归一L1可超过100%，并非概率或独立性指标；不能据X约1断言动力学或指标已经饱和。三个预算均无逐槽零误差和累计计数零误差，30条轨迹全部保留。共同零编辑原图的X=Y=0，但R为0/0、未定义；它不是10个独立零剂量样本。')
p.append('每链R的中位数分别为25.24%、28.06%、36.65%；按误差量加权的总体比值sum(Dcount)/sum(Dslot)为26.11%、26.84%、38.21%。无论使用均值、中位数还是总体比值，较高预算组的时间累计保留比例更大，但其分布存在明显重叠，不能宣称按编辑量完全分离。尤其9.91%组仍有平均61.67%的逐槽差异被节点内时间累积抵消，不能从“编辑更大”直接推出“计数偏差已经主导”。本组9.91%也不等同于旧实验约76%的广泛重连。')
p.append('2. 配对变化与非单调性')
p.append(txt(['预算变化','指标','平均变化/百分点','增加/不变/减少'],[[x['from_budget']+'→'+x['to_budget'],x['metric'],f'{100*float(x["mean"]):+.2f}',f'{x["increase"]}/{x["tie"]}/{x["decrease"]}'] for x in pair if x['metric'] in ['X','Y','Rcount']]))
p.append('1%→2%没有一致改善或恶化：逐槽误差7/10条链下降，累计计数误差5增5减。2%→10%时Y与R均9增1减；1%→10%时Y为9增1平，R为9增1减。跨全部三个预算，X仅2条链单调不减、1条单调不增、7条非单调；Y有4条单调不减、6条非单调；R有5条单调不减、5条非单调。不能把组均值的上升写成每条链的单调剂量反应。')
p.append('更大的编辑范围也涉及更多节点：出现逐槽差异的块数均值为40.6、45.0、63.4；累计计数不同的块数为34.5、38.7、55.7。所有10条链的逐槽差异块数都随这两步预算扩大而增加。这是描述性空间范围变化，不是新增的因果传播机制证明。')
p.append('3. 区分误差总量与时间抵消组成\n对每个节点统计正差异质量P_k与负差异质量N_k，有Dslot=sum(P_k+N_k)，Dcount=sum|P_k−N_k|，Ctime=2sum min(P_k,N_k)。因此Dslot=Ctime+Cspace+Dglobal，其中Cspace=Dcount−Dglobal。逐节点表保留了所有质量项；这不会把抵消自动解释成纯时间平移或稳态速率保持。')
p.append('对同一链两个预算，Y=X R的精确对称分解为：\nΔY = ((R_a+R_b)/2) ΔX + ((X_a+X_b)/2) ΔR。\n第一项描述逐槽差异总量变化，第二项描述累计保留比例变化；两项都是算术分解，不是对编辑量和时间机制的因果贡献估计。各分量先在每条链内计算，再平均；不把中位数相加。')
p.append(txt(['预算变化','总ΔY/百分点','差异总量项','保留比例项'],[[x['from_budget']+'→'+x['to_budget'],*[f'{100*float(x[k]):+.2f}' for k in ['mean_delta_Y','mean_magnitude_component','mean_retained_fraction_component']]] for x in decomp]))
p.append('从约1%到约10%，Y平均增加15.97个百分点，其中差异总量项为2.29个百分点、保留比例项为13.68个百分点。相应X只增加8.04个百分点，绝对时间抵消量Ctime/Nref反而平均减少7.93个百分点。因此，该组配对数据中的累计计数误差增加，不只是“原来差异更多”的比例放大；误差的正负抵消结构也变了。该结论限于算术组成，不证明新增边数量独立于新增边位置的作用。')
p.append('4. 时间分箱检查\n对0.1、0.2、1、5和30ms宽度检查全部整数槽偏移，保留两端边界，合计10,890个重复读数。')
p.append(txt(['宽度/ms',*labels],[[str(w*.1),*[f'{100*next(z for z in readout if z["budget"]==b and z["width_slots"]==w)["zero_offset_mean"]:.2f}' for b in B]] for w in [1,2,10,50,300]]))
p.append('表中是零偏移的平均归一L1百分比。10%组的均值在这些宽度的全部偏移下都高于1%和2%组；不是各个链的区间完全分离，也不是新增独立样本。1ms时各预算均值的偏移范围分别为32.41–33.14%、34.29–35.05%、49.87–50.60%。30ms宽度只有偏移0等于完整窗口总计数，其他偏移会把窗口切成两段，不能冒充Dcount。')
p.append('5. 是否加入论文\n建议加入，但以一段配对结果和一张紧凑图/表，放在原误差组成结果之后；详细链表、分箱偏移与分解推导放补充材料。它把旧的“单次交换与广泛重连两个不同规模极端”补充为同输入、同链嵌套预算的检验，直接回应编辑量混淆；不应再增加一条主线。可以用它替换一部分反复描述1,089个重复读出的文字。')
p.append('建议正文主张（尚未写入论文）：\n“在10条随机选择的嵌套交换链上，扩大编辑预算改变了误差的时间组成。约1%至约10%预算之间，逐槽误差的平均变化较小，而节点累计计数误差与其保留比例上升；精确配对分解显示后者不能仅由逐槽差异总量的同比放大描述。不过，低预算间及单链轨迹存在非单调性，因此这些结果不支持普遍单调的编辑量—保真度关系。”')
p.append('必须保留的界限：同一人工图、单一Focal输入、10条已存在随机链、三个非零剂量、事后分析。旧19个最小交换不是这些链的第一剂量点，不能连接成一条连续剂量曲线。新增边的位置与数量同时变化，尚未因果分离。不要据三个剂量拟合幂律、定位饱和拐点或宣称“几何结构决定最优保真”。这些证据不改变认证方向评分是另一类固定支持权重扰动实验的事实。')
p.append('科学价值判断\n这是有用的主张校准与配对支持：它显示误差量和时间抵消比例可以变化不同步，也暴露了小预算下不单调的负结果。它没有把工作升级成普遍结构定律。与评分因子消融一起，适合支撑“需要明确输入、扰动范围和观测量”的主线，而非把每轮追加分析都包装成独立新发现。')
p.append('6. 验证与文件\n全部30条轨迹的整数端点与历史per_graph.csv吻合；120项运行/图哈希、90项标量归约、30项精确有理数分解通过。独立按槽标签重新分箱，10,890个读数全部一致。新进程分析结果按字节核对；原双语稿件哈希核对保持不变。\nper-chain.csv：30条轨迹完整端点。per-node.csv：3,750个节点的正负误差质量。paired-decomposition.csv：30个预算配对分解。readout-offsets.csv：全部偏移。PROTOCOL.txt保留本轮方案及事后性质。')
(ROOT/'REPORT.zh.txt').write_text('\n\n'.join(p)+'\n');print(ROOT/'REPORT.zh.txt')
