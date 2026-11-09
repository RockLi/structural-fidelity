"""Build either language as an independent, editable scientific preprint."""
from pathlib import Path
import argparse, re, csv, importlib, json, collections
from docx.shared import Pt, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
import docx_helpers as h
import paper_en
from document_labels import Labels

ROOT = Path(__file__).resolve().parent
LEGACY = ROOT.parent/'evidence/legacy-release'
ARCHIVED = LEGACY/'output/local-circuit-preprint-20261026-final-review'
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('language', choices=['en','zh'], nargs='?', default='en')
parser.add_argument('--data-dir', type=Path, default=ARCHIVED/'evidence/diagnostics')
parser.add_argument('--boundary-run-dir', type=Path, default=ARCHIVED/'evidence/execution-boundaries/final-run')
parser.add_argument('--figures-dir', type=Path, default=ROOT/'figures')
parser.add_argument('--rewiring-dir', type=Path, default=ARCHIVED/'evidence/rewiring')
parser.add_argument('--perturbation-dir', type=Path, default=ARCHIVED/'evidence/perturbation')
parser.add_argument('--sensitivity-figures-dir', type=Path, default=ROOT/'sensitivity-figures')
parser.add_argument('--sensitivity-dir', type=Path, default=ARCHIVED/'evidence/sensitivity')
parser.add_argument('--input-readout-dir', type=Path, default=ARCHIVED/'evidence/input-readout/analysis')
parser.add_argument('--activity-figures-dir', type=Path, default=ROOT/'activity-figures')
parser.add_argument('--conditional-figures-dir', type=Path, default=ROOT/'conditional-figures')
parser.add_argument('--mechanism-dir', type=Path, default=LEGACY/'research/experiments/paired-direction-mechanism-20261108')
parser.add_argument('--score-audit-dir', type=Path, default=LEGACY/'research/experiments/score-factor-coverage-audit-20261108/results')
parser.add_argument('--dose-dir', type=Path, default=LEGACY/'research/experiments/paired-dose-composition-20261108/results')
parser.add_argument('--input-control-dir', type=Path, default=LEGACY/'research/experiments/input-control-directions-20261108')
parser.add_argument('--output-dir', type=Path, default=ROOT)
parser.add_argument('--analysis',type=Path,default=ROOT.parent/'analysis')
parser.add_argument('--lif-dir',type=Path,default=ROOT.parent/'evidence/studies/atlas-heterogeneous-lif-horizon-20261109')
args = parser.parse_args()
LANG = args.language
ZH = LANG == 'zh'
paper = importlib.import_module('paper_zh' if ZH else 'paper_en')
labels = Labels(paper)
original_equation = h.equation
def labeled_equation(parts, label):
    return original_equation(parts, labels.equation(label))
h.equation = labeled_equation
doc = h.doc
doc.core_properties.title = paper.TITLE
doc.core_properties.author = paper.AUTHOR
doc.core_properties.subject = 'Input and horizon dependent structural fidelity and finite horizon certificates'
import datetime
doc.core_properties.created=doc.core_properties.modified=datetime.datetime(2026,11,9,0,0,0)
doc.core_properties.language = 'zh-CN' if ZH else 'en-US'
doc.styles['Normal'].font.size = Pt(10.5 if ZH else 11)
doc.styles['Normal'].paragraph_format.line_spacing = 1.12
doc.styles['Normal'].paragraph_format.space_after = Pt(6)
doc.styles['Title'].paragraph_format.space_after = Pt(10)
doc.styles['Caption'].paragraph_format.keep_with_next = False

def p(text='',style=None):
    pp = h.p(labels.rewrite(text),style,ZH)
    if style is None:
        pp.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    return pp

def cap(text): return h.caption(labels.rewrite(text))
def table_cap(text):
    pp=cap(text); pp.paragraph_format.keep_with_next=True
    return pp

def acc(base,char):
    node=OxmlElement('m:acc');pr=OxmlElement('m:accPr');ch=OxmlElement('m:chr');ch.set(qn('m:val'),char);pr.append(ch)
    element=OxmlElement('m:e');element.extend(h.seq(base));node.extend([pr,element]);return node

def norm(value,subscript=None):
    parts=h.seq('‖',value,'‖')
    return h.sub(parts,subscript) if subscript else parts

def eq(key):
    start=len(doc.paragraphs)
    if key in {'lif','lif_family','horizon_nested','lif_score','lif_decay_bound','lif_voltage_bound'}:
        from extension_render import equations
        equations(key,h)
    elif key=='branch_guard':
        h.equation(h.seq(h.sub('V','hi'),' < θ  (reference silent),     ',h.sub('V','lo'),' ≥ θ  (reference spike)'),'(18)')
    elif key=='direction_weight':
        h.equation(h.seq(h.sub('w','e'),'(t) = RN32[',h.sub('w','e,0'),'(1 + t ',h.sub('σ','e'),')],     |t| ≤ ρ ≤ 0.25'),'(19)')
    elif key=='direction_score':
        h.equation(h.seq(h.sub('z','k'),'[n] = d ',h.sub('z','k'),'[n − 1] + (1 − d)(',h.sub('ΔI','kE'),'[n] − ',h.sub('ΔI','kI'),'[n])'),'(20a)')
        h.equation(h.seq('J = ',h.sub('max','k,n eligible'),h.frac(h.seq('|',h.sub('z','k'),'[n]|'),h.seq('max{|',h.sub('v','ref,k,pre'),'[n] − θ|, ',h.sup('2','−20'),'}'))),'(20b)')
    elif key=='neuron': h.eqblock('neuron')
    elif key=='raw':
        h.equation(h.seq(h.sub('R','kq'),'[n] = ',h.sub('∑',h.seq('e∈',h.sub('P','kq'))),h.sub('w','e'),' ',h.sub('S','j'),'[n]'),'(2)')
    elif key=='history':
        h.equation(h.seq(h.sub('x','kqa'),'[n] = ',h.sub('d','qa'),h.sub('x','kqa'),'[n − 1] + (1 − ',h.sub('d','qa'),')',h.sub('R','kq'),'[n]'),'(3a)')
        h.equation(h.seq(h.sub('d','qa'),' = exp[−dt/max(',h.sub('τ','qa'),', 0.1)]'),'(3b)')
        h.equation(h.seq(h.sub('h','kq'),'[n] = (1 − α)',h.sub('h','kq'),'[n − 1] + α',h.sub('R','kq'),'[n]'),'(3c)')
    elif key=='modulation':
        h.equation(h.seq('c = ',h.frac(h.seq(h.sub('x','f'),' − h'),h.seq(h.sub('x','f'),' + h + ε')),',     s = clip(',h.frac(h.seq(h.sub('x','s')),h.seq('h + ε')),', 0, 1.5)'),'(4a)')
        h.equation(h.seq(h.sub('D','kq'),' = ',h.sub('κ','q'),'[1 − 0.03c + 0.01(s − 0.5)]',h.sub('R','kq')),'(4b)')
    elif key=='constraints':
        h.equation(h.seq(h.sup('ΔW','q'),'P = 0,     ',h.sup('P','T'),h.sup('ΔW','q'),' = 0'),'(5)')
    elif key=='residual':
        h.equation(h.seq(acc('s','̄'),' = ',h.sup(h.seq('(',h.sup('P','T'),'P)'),'−1'),h.sup('P','T'),'s,     r = s − P',acc('s','̄')),'(6a)')
    elif key=='redistribution':
        h.equation(h.seq(h.sup('ΔI','q'),' = ',h.sup('ΔW','q'),'s = ',h.sup('ΔW','q'),'r,     ',h.sup('P','T'),h.sup('ΔI','q'),' = 0'),'(6b)')
    elif key=='bound':
        h.equation(h.seq(norm(h.sup('ΔI','q'),'2'),' ≤ ',norm(h.sup('ΔW','q'),'2'),norm('r','2')),'(7)')
    elif key=='lowerbound':
        h.equation(h.seq('max{',norm(h.seq(acc('I','̂'),' − ',h.sub('W','1'),'s')),', ',norm(h.seq(acc('I','̂'),' − ',h.sub('W','2'),'s')),'} ≥ ',h.frac(h.seq('1'),h.seq('2')),norm(h.seq('(',h.sub('W','1'),' − ',h.sub('W','2'),')s'))),'(8)')
    elif key=='counterexample':
        h.equation(h.seq(norm(h.seq('(',h.sub('W','1'),' − ',h.sub('W','2'),')s'),'1'),' = 2w |',h.sub('s','a'),' − ',h.sub('s','c'),'|'),'(9)')
    elif key=='predictor':
        h.equation(h.seq(h.sub('F','5'),'(g) = ',h.frac(norm(h.seq(h.sub('ΔG','g'),h.sub('U','5')),'F'),norm(h.seq(h.sub('G','0'),h.sub('U','5')),'F'))),'(10)')
    elif key=='response':
        h.equation(h.seq(h.sup(h.sub('r','g'),'a'),'[n] = ',h.sup('D','−1'),'(',h.sup(h.sub('X','g'),'a'),'[n] − ',h.sup(h.sub('X','g'),'0'),'[n])'),'(11)')
    elif key=='fidelity':
        h.equation(h.seq(h.sub('Y','g'),'(a) = RMS(',h.sup(h.sub('r','g'),'a'),' − ',h.sup(h.sub('r','0'),'a'),')'),'(12)')
    elif key=='finite_horizon':
        h.equation(h.seq(h.sup(h.sub('ΔW','d'),'q'),' ',h.sub('s','ref'),'[n] = 0,     ∀q, d, 0 ≤ n < T'),'(13)')
    elif key=='composition':
        h.equation(h.seq(h.sub('D','slot'),' = ',h.sub('∑','n,k'),'|',h.sub('δ','kn'),'|,     ',
                         h.sub('D','count'),' = ',h.sub('∑','k'),'|',h.sub('∑','n'),h.sub('δ','kn'),'|'),'(14a)')
        h.equation(h.seq(h.sub('D','global'),' = |',h.sub('∑','n,k'),h.sub('δ','kn'),'|,     ',
                         h.sub('R','count'),' = ',h.frac(h.sub('D','count'),h.sub('D','slot')),
                         '  (',h.sub('D','slot'),' > 0)'),'(14b)')
    elif key=='composition_identity':
        h.equation(h.seq(h.sub('D','slot'),' − ',h.sub('D','count'),' = 2',h.sub('∑','k'),
                         ' min{',h.sub('∑','n'),h.sub(h.seq('[',h.sub('δ','kn'),']'),'+'),', ',
                         h.sub('∑','n'),h.sub(h.seq('[−',h.sub('δ','kn'),']'),'+'),'}'),'(15a)')
        h.equation(h.seq(h.sub('D','slot'),' = (',h.sub('D','slot'),' − ',h.sub('D','count'),
                         ') + (',h.sub('D','count'),' − ',h.sub('D','global'),') + ',h.sub('D','global')),'(15b)')
    elif key=='smoothdistance':
        h.equation(h.seq(h.sup(h.sub('V','τ'),'2'),' = ',h.frac('1','τ'),
                         h.sup(h.sub('∫','0'),'∞'),h.sub('∑','k'),
                         h.sup(h.seq('[',h.sub('f','k,τ'),'(t) − ',h.sub('f','ref,k,τ'),'(t)]'),'2'),' dt'),'(16a)')
        h.equation(h.seq(h.sub('R','τ'),' = ',h.frac(h.seq('2',h.sup(h.sub('V','τ'),'2')),h.sub('N','ref'))),
                   '(16b)')
    elif key=='activity_score':
        h.equation(h.seq(h.sub('J','mean'),' = L',h.sub('∑','q'),
                         h.sup(norm(h.seq(h.sup('ΔW','q'),'μ'),'2'),'2')),'(17a)')
        h.equation(h.seq(h.sub('J','co'),' = ',h.sub('∑','q'),
                         h.sup(norm(h.seq(h.sup('ΔW','q'),h.sub('S','ref')),'F'),'2')),'(17b)')
    else: raise ValueError(key)
    for pp in doc.paragraphs[start:-1]: pp.paragraph_format.keep_with_next=True

FIGS={'16':'fig1_graphs','17':'fig2_horizon','18':'fig3_bounds','15':'input-controls-paper','14':'mechanism-summary','1':'fig1_execution','2':'fig2_e1','3':'fig3_budget','4':'fig6_e3_trajectories','S1':'fig4_edge_classes','S2':'fig5_calibration','5':'wiring-effects','6':'proxy-errors','S3':'messages-and-error','S4':'example-traces','7':'phase-preservation','8':'prediction-and-coverage','9':'sensitivity-calibration','S5':'cancellation-calibration','S6':'swap-activation','S7':'sensitivity-time-course','10':'input-switching','11':'error-composition','12':'binning-robustness','13':'activity-budget-boundary'}
def figure(key):
    pp=p();pp.paragraph_format.keep_with_next=True;pp.paragraph_format.space_after=Pt(5)
    folder=args.activity_figures_dir if key=='13' else args.input_readout_dir if key in {'10','11','12'} else args.sensitivity_figures_dir if key in {'9','S5','S6','S7'} else args.conditional_figures_dir if key in {'7','8'} else (args.rewiring_dir/'analysis' if key in {'5','6','S3','S4'} else args.figures_dir)
    figure_width=6.0 if key=='5' and not ZH else h.WIDTH
    pp.paragraph_format.alignment=WD_ALIGN_PARAGRAPH.CENTER
    pp.add_run().add_picture(str(folder/f'{FIGS[key]}.png'),width=Inches(figure_width))
    caption=cap(paper.FIG_CAPTIONS[key]);caption.paragraph_format.keep_together=True

rows=list(csv.DictReader((args.data_dir/'primary-comparison-exact.csv').open()))
def counterpart(r, variant):
    return next(x for x in rows if x['variant']==variant and x['benchmark']==r['benchmark'] and x['label']==r['label'])

def tab(key):
    if key in {'24','25','26','27','28'}:
        from extension_render import table
        return table(key,args,ZH,h,table_cap)
    if key in {'17','18','19','20','21','22','23'}:
        from revision_tables import render
        render(key, args, ZH, h, table_cap)
    elif key=='14':
        table_cap('表14 可确定安全半径顺序的方向对上的宏观一致率。非独立样本；完整敏感度为代数上限。' if ZH else 'Table 14. Macro ordering concordance on resolved radius pairs. Comparisons are dependent; full sensitivity is an algebraic ceiling.')
        data=json.loads((args.mechanism_dir/'results/analysis.json').read_text())['rank']
        methods=[('random','随机顺序','Random order'),('raw','原始投影','Raw projection'),('mean','平均活动','Mean activity'),('shuffle','独立时间平移','Independent shifts'),('temporal','时序与裕量','Temporal margin'),('full','完整敏感度','Full sensitivity')]
        vals=[]
        for key2,zh,en in methods:
            vals.append([zh if ZH else en]+[f"{next(r['macro_concordance'] for r in data if r['probe']==u and r['subgroup']=='all' and r['method']==key2):.3f}" for u in ['tonic','global_burst','focal_burst']])
        h.table(['评分' if ZH else 'Score','Tonic','Global','Focal'],vals,[2.8,1.25,1.25,1.26])
    elif key=='15':
        table_cap('表15 固定Tonic时序选择相对于三个对照的配对半径结果。平局为同方向或均达上限；重叠记未决。' if ZH else 'Table 15. Radius comparisons for the fixed tonic temporal choice against three controls. Ties denote identical directions or joint cap certification; overlap is unresolved.')
        rs=list(csv.DictReader((args.mechanism_dir/'results/selection-transfer.csv').open()))
        vals=[]
        for u in ['tonic','global_burst','focal_burst']:
            for c in ['random','mean','shuffle']:
                counter=collections.Counter(r['outcome'] for r in rs if r['probe']==u and r['control']==c)
                vals.append([u.replace('_burst','').title(),{'random':'随机','mean':'平均','shuffle':'打乱'}[c] if ZH else c.title(),str(counter['win']),str(counter['loss']),str(counter['tie_same_direction']+counter['tie_at_cap']),str(counter['unresolved'])])
        h.table(['输入' if ZH else 'Input','对照' if ZH else 'Control','胜' if ZH else 'Win','负' if ZH else 'Loss','平' if ZH else 'Tie','未决' if ZH else 'Unresolved'],vals,[1.1,1.46,1,1,1,1])
    elif key=='16':
        table_cap('表16 前序认证审计的匹配工作量成本，单位ms。前两行是单点，其余为二维参数族；不能跨组解释为同一工作量。' if ZH else 'Table 16. Matched-work costs from preceding audits, in ms. First two rows concern singletons; remaining rows concern two-parameter families and are a different workload.')
        vals=[('单点认证内核','Singleton certificate kernel','0.13115','单候选','One candidate'),('单点局部回放内核','Singleton local replay kernel','0.003430','单候选','One candidate'),('准备与支持函数认证','Preparation + support certificate','0.15839','整个参数盒','Whole box'),('准备与严格角点包络','Preparation + rigorous corners','0.20909','整个参数盒','Whole box'),('四角点回放含事件生成','Four-point replay + generation','0.01706','四个参数点','Four points'),('25点回放含事件生成','25-point replay + generation','0.10372','25个参数点','25 points')]
        h.table(['方法' if ZH else 'Method','ms','覆盖' if ZH else 'Coverage'],[[v[0] if ZH else v[1],v[2],v[3] if ZH else v[4]] for v in vals],[3.7,1.1,1.76])
    elif key=='1':
        table_cap('表 1  实验规模与观测时长。每块 100 个单元，时间步为 0.1 ms。' if ZH else 'Table 1. Workload dimensions and observation windows. Each chunk has 100 units and dt = 0.1 ms.')
        h.table(['实验' if ZH else 'Workload','单元 N' if ZH else 'Units N','块数 C' if ZH else 'Chunks C','时间槽' if ZH else 'Slots','时长 / ms' if ZH else 'Time / ms'],[
          ('E1 主实验' if ZH else 'E1 principal','50,000','500','500','50'),
          ('E1 增益扫描' if ZH else 'E1 gain scan','12,500','125','200','20'),
          ('E3 异质权重' if ZH else 'E3 heterogeneous','12,500','125','200','20'),
          ('E3 均质权重' if ZH else 'E3 homogeneous','12,500','125','300','30'),
          ('E4 三种权重状态' if ZH else 'E4 weight settings','5,000','50','200','20'),
          ('E5 脉冲与恢复' if ZH else 'E5 pulse and recovery','5,000','50','300','30'),
          ('E3 重连扩展' if ZH else 'E3 rewiring extension','12,500','125','300','30'),
          ('阶段诊断原轨迹' if ZH else 'Phase diagnostic archive','12,500','125','300','30'),
          ('扰动响应扩展' if ZH else 'Perturbation response','12,500','125','1000','100'),
          ('灵敏度标定' if ZH else 'Sensitivity calibration','12,500','125','300','30')],[2.65,1.02,.95,.95,.99])
    elif key=='2':
        table_cap('表 2  E1 方法比较。保留比例指单独投递的块间边；Q 为循环消息入队量之比。' if ZH else 'Table 2. E1 comparison. Retention is the fraction of chunk edges routed individually; Q is the recurrent queue-insertion ratio.')
        data=[('原始求和' if ZH else 'Raw sum','0','1.000','0.0','0.157'),
          ('原始求和混合' if ZH else 'Raw-sum hybrid','24.0','1.000','0.0','0.494'),
          ('静态增益' if ZH else 'Static gain','0','0.996','−5.9','0.159'),
          ('静态增益混合' if ZH else 'Static-gain hybrid','24.0','0.998','−4.1','0.488'),
          ('历史调制' if ZH else 'History modulation','0','0.992','−8.4','0.164'),
          ('历史调制混合' if ZH else 'History-modulated hybrid','24.0','0.980','−16.0','0.451'),
          ('四通道滤波' if ZH else 'Filtered four-channel','0','0.435','−9.7','0.405'),
          ('四通道滤波混合' if ZH else 'Filtered hybrid','24.0','0.183','−52.6','0.636'),
          ('双通道' if ZH else 'Two-channel','0','−0.217','+323.6','0.388')]
        t=h.table(['方法' if ZH else 'Method','保留 / %' if ZH else 'Retained / %','r','δFR / %','Q'],data,[2.8,1.1,.78,.94,.94])
        for row in t.rows[:-1]:
            for cell in row.cells:
                for pp in cell.paragraphs: pp.paragraph_format.keep_with_next=True
        cap('原始求和两种设置均在全部 500 个时间槽中保持群体计数一致；对应显式参考的累计脉冲数为 1,606,400。' if ZH else 'Both raw-sum settings match the reference population count in all 500 slots. The reference emits 1,606,400 spikes.')
    elif key=='3':
        table_cap('表 3  不同工作负载中的保真度与消息量。所有原始求和设置均有 r = 1、δFR = 0，且无群体计数不匹配。' if ZH else 'Table 3. Fidelity and message counts across workloads. Every raw-sum setting has r = 1, δFR = 0 and zero mismatching population-count slots.')
        labels=['E3 异质' if ZH else 'E3 heterogeneous','E3 均质' if ZH else 'E3 homogeneous','E4 稳定' if ZH else 'E4 stable','E4 平衡' if ZH else 'E4 balanced','E4 易激发' if ZH else 'E4 excitable','E5 脉冲' if ZH else 'E5 pulse']
        base=[r for r in rows if r['variant']=='original_instrumented' and not r['benchmark'].startswith('E1')]
        data=[]
        for r,label,ret in zip(base,labels,['11.2','22.8','26.4','26.4','26.4','27.7']):
            raw=counterpart(r,'raw_sum')
            data.append([label,ret,f'{float(r["psth_r"]):.3f}',f'{float(r["fr_delta"]):+.1f}',f'{float(r["event_ratio_from_counts"]):.3f}',f'{float(raw["event_ratio_from_counts"]):.3f}'])
        t=h.table(['配置' if ZH else 'Setting','保留 / %' if ZH else 'Retained / %','调制 r' if ZH else 'History r','调制 δFR / %' if ZH else 'History δFR / %','调制 Q' if ZH else 'History Q','求和 Q' if ZH else 'Raw Q'],data,[1.70,.85,.86,1.20,.98,.97])
        for row in t.rows[:-1]:
            for cell in row.cells:
                for pp in cell.paragraphs: pp.paragraph_format.keep_with_next=True
    elif key=='4':
        table_cap('表 4  受控投递测试。首次差异采用从零开始的时间槽编号；破折号表示 12 槽内无差异。消息数包含预设唤醒事件。' if ZH else 'Table 4. Controlled delivery fixtures. First differences use zero-based slots; a dash denotes no difference in 12 slots. Message counts include prescribed wake-up events.')
        fixture_rows=list(csv.DictReader((args.boundary_run_dir/'summary.csv').open()))
        labels_en=['B1 Positive aligned','B2 Heterogeneous initial state','B3 Drop zero wake-up','B4 Preserve zero wake-up',
                   'B5 Separate E/I channels','B6 Cancel E/I channels','B7 Separate arrival slots','B8 Move later input earlier']
        labels_zh=['B1 正输入对齐','B2 异质初始状态','B3 丢弃零幅值唤醒','B4 保留零幅值唤醒',
                   'B5 分离 E/I 通道','B6 抵消 E/I 通道','B7 分离到达时间槽','B8 提前较晚输入']
        data=[]
        for i,(row,label) in enumerate(zip(fixture_rows,labels_zh if ZH else labels_en),1):
            assert row['case_id']==f'B{i}'
            data.append([label,f'{row["reference_messages"]} / {row["candidate_messages"]}',
                         row['first_state_divergence_slot'] or '—',
                         row['first_activation_divergence_slot'] or '—',
                         row['first_spike_divergence_slot'] or '—'])
        assert len(data)==8
        t=h.table(['测试' if ZH else 'Fixture','消息\n参考 / 候选' if ZH else 'Messages\nref / test',
                   '首次状态差异' if ZH else 'First state difference',
                   '首次激活差异' if ZH else 'First activation difference',
                   '首次脉冲差异' if ZH else 'First spike difference'],data,[2.56,.8,1.05,1.1,1.05])
        # Keep the fixture table and its explanatory note together, with
        # compact padding so the Chinese note fits on the same page.
        for side in ('top','bottom'):
            t._tbl.tblPr.find(qn('w:tblCellMar')).find(qn('w:'+side)).set(qn('w:w'),'40')
        spacer=doc.paragraphs[-1]
        spacer.paragraph_format.line_spacing=Pt(1)
        spacer.paragraph_format.space_before=Pt(0)
        spacer.paragraph_format.space_after=Pt(0)
        spacer.paragraph_format.keep_with_next=True
        for row in t.rows:
            for cell in row.cells:
                for pp in cell.paragraphs: pp.paragraph_format.keep_with_next=True
        cap('状态比较涵盖全部记录的逐单元动力学变量及块局部场；激活比较包括是否步进和步后状态。脉冲比较逐单元进行。' if ZH else 'State comparisons cover all recorded unit dynamical variables and chunk fields; activation compares stepping and post-step status. Spikes are compared per unit.')
    elif key=='5':
        table_cap('表 5  同质主对照的归一化 L1 误差（%）。重连列为 19 个对照的中位数（最小–最大）；结构差异比较显式执行，trace 误差使用各自图的显式参考。' if ZH else 'Table 5. Homogeneous controls, normalized L1 errors (%). Rewiring columns give median (minimum–maximum) over 19 controls. Structural differences compare explicit runs; trace uses each graph’s own explicit reference.')
        summaries=[x for x in json.loads((args.rewiring_dir/'analysis/summary.json').read_text()) if x['family']=='homogeneous']
        data=[]
        def display(a):return f'{100*a["median"]:.2f} ({100*a["minimum"]:.2f}–{100*a["maximum"]:.2f})'
        names={'tonic':('持续','Tonic'),'global_burst':('全局短时','Global burst'),'focal_burst':('局部短时','Focal burst')}
        for x in summaries:
            data.append([names[x['probe']][0 if ZH else 1],display(x['wiring_effect']['population_bin_l1_relative']),display(x['wiring_effect']['chunk_bin_l1_relative']),f'{100*x["proxy"]["trace"]["original"]["chunk_bin_l1_relative"]:.2f}',display(x['proxy']['trace']['rewired']['chunk_bin_l1_relative'])])
        t=h.table(['输入' if ZH else 'Input','重连全网' if ZH else 'Rewired population','重连分块' if ZH else 'Rewired chunks','原图 trace' if ZH else 'Original trace','重连 trace' if ZH else 'Rewired trace'],data,[1.0,1.40,1.40,1.12,1.64])
        if not ZH:
            for row in t.rows[:-1]:
                for cell in row.cells:
                    for pp in cell.paragraphs: pp.paragraph_format.keep_with_next=True
    elif key=='6':
        table_cap('表 6  module_burst 三阶段状态误差。每组 5 张条件重连图的中位数；V、gE、gI 使用该刺激原图全 30 ms 的固定通道尺度。数值越低越好。' if ZH else 'Table 6. State error across three windows of module_burst. Medians over five conditional rewires per group; V, gE and gI use fixed channel scales from the original 30 ms trajectory. Lower values indicate closer trajectories.')
        rr=list(csv.DictReader((args.perturbation_dir/'legacy_diagnostics/phase-state-errors.csv').open()))
        import statistics
        data=[]
        for arm,label in [('A_degree','A E/I'),('B_aligned','B aligned'),('C_random','C random')]:
            vals=[]
            for window in ['conditioning','early_recovery','late_recovery']:
                values=[float(r['state_score']) for r in rr if r['probe']=='module_burst' and r['treatment']==arm and r['phase']==window]
                assert len(values)==5
                vals.append(f'{statistics.median(values):.4f}')
            data.append([label]+vals)
        t=h.table(['重连约束' if ZH else 'Rewiring constraint','0–8 ms','8–15 ms','15–30 ms'],data,[2.06,1.5,1.5,1.5])
        for row in t.rows[:-1]:
            for cell in row.cells:
                for pp in cell.paragraphs: pp.paragraph_format.keep_with_next=True
    elif key=='7':
        table_cap('表 7  预设结构指标与扰动响应误差的 Spearman 相关。每个幅度分别使用 15 张条件重连图；原图不参与相关。对照指标的较高相关仍为探索性结果。' if ZH else 'Table 7. Spearman associations between fixed structural predictors and perturbation-response error. Each amplitude uses 15 conditional rewires, excluding the original. Larger correlations among the controls remain exploratory.')
        rr=list(csv.DictReader((args.perturbation_dir/'analysis/prediction-associations.csv').open()))
        specs=[('activity_rank5','活动 rank 5（主）','Activity rank 5 (primary)'),('activity_training90','活动 rank 19（次）','Activity rank 19 (secondary)'),('training_replay_distortion','完整训练活动重放','Full training replay'),('directed_triangle_change','有向三环数量变化','Directed three-cycle change'),('singular_value_distance','奇异值谱距离','Singular-value distance'),('old_module_state_error','旧刺激状态误差','Old stimulus state error')]
        data=[]
        for predictor,zh,en in specs:
            vals=[]
            for cond in ['small','double']:
                match=[r for r in rr if r['predictor']==predictor and r['condition']==cond and r['subset']=='all15' and r['target']=='response_fidelity'];assert len(match)==1
                vals.append(f'{float(match[0]["spearman"]):.3f}')
            data.append([zh if ZH else en]+vals)
        t=h.table(['指标' if ZH else 'Predictor','幅度 1.5' if ZH else 'Amplitude 1.5','幅度 3.0' if ZH else 'Amplitude 3.0'],data,[3.56,1.5,1.5])
        for row in t.rows[:-1]:
            for cell in row.cells:
                for pp in cell.paragraphs: pp.paragraph_format.keep_with_next=True
    elif key=='8':
        table_cap('表 8  具名块的 1 ms 分箱 L1 误差（%）。广泛重连与单次交换各有 19 个对照，数值为中位数（最小–最大）。最后一列检验更细的 0.1 ms 逐槽脉冲一致性。' if ZH else 'Table 8. Identified-chunk L1 error in 1 ms bins (%). Broad rewiring and one-swap groups each contain 19 controls; entries are median (minimum–maximum). The final column tests finer 0.1 ms per-slot spike agreement.')
        sr=list(csv.DictReader((args.sensitivity_dir/'analysis/summary.csv').open()))
        names={'tonic':('持续','Tonic'),'global_burst':('全局短时','Global burst'),'focal_burst':('局部短时','Focal burst')}
        data=[]
        for probe in names:
            values=[]
            for group in ['extensive','swap']:
                r=next(r for r in sr if r['probe']==probe and r['group']==group)
                assert int(r['n'])==19
                values.append(f'{100*float(r["chunk_bin_l1_relative_median"]):.2f} ({100*float(r["chunk_bin_l1_relative_minimum"]):.2f}–{100*float(r["chunk_bin_l1_relative_maximum"]):.2f})')
            data.append([names[probe][0 if ZH else 1]]+values+[f'{r["spike_identical_runs"]}/19'])
        t=h.table(['输入' if ZH else 'Input','广泛重连' if ZH else 'Broad rewiring','单次交换' if ZH else 'One swap','交换后逐槽一致' if ZH else 'Swap slot agreement'],data,[1.06,1.90,1.90,1.70])
        for row in t.rows:
            for cell in row.cells:
                for pp in cell.paragraphs: pp.paragraph_format.keep_with_next=True
        doc.paragraphs[-1].paragraph_format.keep_with_next=True
        cap('三种微小初值剂量下的 171 次运行均保持逐槽脉冲一致；单次交换的分箱零误差数依次为 10、7、8，不能与逐槽一致数混同。' if ZH else 'All 171 runs across three small initial-voltage doses preserve per-slot spikes. One-swap bin-zero counts are 10, 7 and 8, respectively, and must be distinguished from per-slot agreement.')
    elif key=='9':
        table_cap('表 9  57 个最小交换／输入组合的四类观测结果。输入相等指以原图源活动计算的窗口内投递增量相等；状态指十项已记录字段。' if ZH else 'Table 9. Four observed outcomes across 57 swap/input comparisons. Input equality uses common original-source activity and arrivals within the window; state equality covers the ten recorded fields.')
        summary=json.loads((args.input_readout_dir/'summary.json').read_text())
        categories=[('input_zero_state_equal','共享源输入相等，记录状态逐位相等','Shared-source input equal; recorded states bitwise equal'),
                    ('input_changed_spikes_equal','共享源输入改变，逐槽脉冲相等','Shared-source input changed; raw-slot spikes equal'),
                    ('spikes_changed_1ms_equal','逐槽脉冲改变，1 ms 分箱计数相等','Raw-slot spikes changed; 1 ms binned counts equal'),
                    ('1ms_changed','1 ms 分箱计数也改变','1 ms binned counts also changed')]
        h.table(['观测类别' if ZH else 'Observed category','比较数' if ZH else 'Comparisons'],
                [[c[1 if ZH else 2],str(summary['category_counts'][c[0]])] for c in categories], [5.45,1.11])
    elif key=='10':
        table_cap('表 10  逐节点 30 ms 累计计数保留的逐槽误差比例 R_count（%），中位数（最小–最大）。分母为零时比例未定义；每种输入的最小交换保留 12/19 个比较，广泛重连保留 19/19 个。' if ZH else 'Table 10. Raw-slot error retained in per-node 30 ms counts, R_count (%), median (minimum–maximum). Ratios are undefined for zero raw-slot error: 12/19 swap and 19/19 extensive comparisons contribute under each input.')
        summary=json.loads((args.input_readout_dir/'summary.json').read_text())
        by={(r['probe'],r['group']):r for r in summary['composition']}
        display=lambda r:'%.2f (%.2f–%.2f)'%tuple(100*r['count_retained_fraction_'+k] for k in ['median','minimum','maximum'])
        names={'tonic':('持续','Tonic'),'global_burst':('全局突发','Global burst'),'focal_burst':('局部突发','Focal burst')}
        h.table(['输入' if ZH else 'Input','最小交换，n = 12' if ZH else 'One swap, n = 12','广泛重连，n = 19' if ZH else 'Extensive, n = 19'],
                [[names[q][0 if ZH else 1],display(by[q,'swap']),display(by[q,'extensive'])] for q in names], [1.5,2.53,2.53])
    elif key=='11':
        table_cap('表 11  活动引导选图的训练输入结果。每预算与规则各有 10 个候选池成员；重合选图保留为并列。J_co 为固定参考活动上的共活动评分；脉冲误差为归一化具名块逐槽 L1。9.912% 为之前完成的已知结果。' if ZH else 'Table 11. Training-input outcomes of activity-guided graph selection. Each budget and rule has ten candidate-bank memberships; overlapping selections remain as ties. J_co is the frozen-reference coactivity score; spike error is normalized identified raw-slot L1. The 9.912% condition is the previously completed result.')
        data=json.loads((args.activity_figures_dir/'activity-budget-figure-data.json').read_text())['table_rows']
        names={'random':('随机','Random'),'mean':('平均活动','Mean activity'),'coactivity':('共活动','Coactivity'),'shuffled':('时间打乱','Shuffled')}
        assert all(r['score_zero_count']==r['spike_zero_count']==0 for r in data)
        cells=[[f'{r["budget_percent"]:.3f}',names[r['policy']][0 if ZH else 1],f'{r["J_coactivity_mean"]:.3g}',f'{r["raw_slot_l1_mean"]:.4f}'] for r in data]
        t=h.table(['替换 / %' if ZH else 'Replaced / %','规则' if ZH else 'Selector','平均 J_co' if ZH else 'Mean J_co','平均脉冲误差' if ZH else 'Mean spike error'],cells,[1.15,1.81,1.70,1.90])
        for row in t.rows:
            for cell in row.cells:
                for pp in cell.paragraphs: pp.paragraph_format.keep_with_next=True
        doc.paragraphs[-1].paragraph_format.keep_with_next=True
        cap('所有行（包括此前的 9.912% 条件）中，零共活动评分与零逐槽脉冲误差均为 0/10；分母为候选池成员数。' if ZH else 'In every row, including the prior 9.912% condition, zero coactivity scores and zero raw-slot spike discrepancies each occur in 0/10 candidate-bank memberships.')
    elif key=='12':
        table_cap('表 12  小预算下的配对差与停止判定。差值为共活动减去对照的归一化逐槽 L1，以百分点（pp）表示；负值有利于共活动。每行含 10 个候选池配对。同图数单独列出，重合选图仍保留在平局中。' if ZH else 'Table 12. Paired small-budget differences and stopping decision. Differences are coactivity minus comparator in normalized raw-slot L1, expressed in percentage points (pp); negative favors coactivity. Each row contains ten candidate-bank pairs. Same-graph counts are reported separately; overlapping selections remain among ties.')
        payload=json.loads((args.activity_figures_dir/'activity-budget-figure-data.json').read_text())
        data=payload['comparison_rows'];decision=payload['decision_summary'];assert len(data)==6 and not decision['proceed_migration']
        names={'random':('随机','Random'),'mean':('平均活动','Mean activity'),'shuffled':('时间打乱','Shuffled')}
        result=lambda yes:('通过' if yes else '未通过') if ZH else ('Pass' if yes else 'Fail')
        number=lambda value:'0.00' if value==0 else f'{100*value:+.2f}'
        cells=[[f'{r["budget_percent"]:.3f}',names[r['comparator']][0 if ZH else 1],number(r['mean_difference']),number(r['median_difference']),f'{r["wins"]}/{r["ties"]}/{r["losses"]}',f'{r["same_selected_graph"]}/10',result(r['comparison_passed'])] for r in data]
        for budget in ['p01','p02']:
            percent=next(r['budget_percent'] for r in data if r['budget']==budget)
            label=(f'{percent:.3f}% 预算：三个对照条件均须通过' if ZH else f'{percent:.3f}% budget: all three comparator conditions required')
            cells.append([label,'','','','','',result(decision['budgets'][budget])])
        cells.append(['联合判定：两个预算均须通过' if ZH else 'Joint continuation: both budgets must pass','','','','','','停止' if ZH else 'Stop'])
        t=h.table(['替换 / %' if ZH else 'Replaced / %','对照' if ZH else 'Comparator','均值 / pp' if ZH else 'Mean / pp','中位数 / pp' if ZH else 'Median / pp','胜/平/负' if ZH else 'W/T/L','同图' if ZH else 'Same graph','判据' if ZH else 'Criterion'],cells,[.75,1.14,.90,.90,.84,.91,1.12])
        for row in t.rows[7:]:
            label=row.cells[0].text
            merged=row.cells[0].merge(row.cells[5]);merged.text=label
            for pp in merged.paragraphs:
                pp.paragraph_format.space_after=Pt(0);pp.paragraph_format.line_spacing=1.05
                for rr in pp.runs:rr.font.size=Pt(9)
        for row in t.rows:
            for cell in row.cells:
                for pp in cell.paragraphs:pp.paragraph_format.keep_with_next=True
        doc.paragraphs[-1].paragraph_format.keep_with_next=True
        cap('胜/平/负按换算为百分点之前、未舍入的归一化 L1 差值 Δ 与冻结容差 ε = 10⁻¹² 判定：Δ < −ε、|Δ| ≤ ε、Δ > ε。随机对照要求均值、中位数均 < −ε，且至少 7 胜；平均活动与打乱对照要求均值 ≤ ε，且胜数 ≥ 负数，不设中位数门槛。所有判据均要求 10 个完整配对。这是继续实验的操作判据，不是显著性或非劣效性检验；本轮新增迁移运行数为 0。' if ZH else 'W/T/L uses unrounded normalized-L1 differences Δ before conversion to percentage points and frozen tolerance ε = 10⁻¹²: Δ < −ε, |Δ| ≤ ε, Δ > ε. Random requires mean and median < −ε and at least seven wins. Mean activity and shuffled require mean ≤ ε and wins ≥ losses, with no median threshold. Every condition requires ten complete pairs. These are operational continuation criteria, not significance or noninferiority tests; no new migration runs were performed.')
    elif key=='A1':
        table_cap('表 A1  图生成参数。概率和权重均按 EE、EI、IE、II 排列；spread 为基础权重的变化幅度。' if ZH else 'Table A1. Graph parameters. Probability and weight tuples use EE, EI, IE, II order; spread is the fractional variation around the base weight.')
        data=[('E1 / E1 gain scan','(.10, .20, .20, .15)','(.8, .8, 1.2, .6)','42 / 0%'),
          ('E3 heterogeneous','(.15, .25, .25, .20)','(.6, .8, 1.4, .5)','200 / 50%'),
          ('E3 homogeneous','(.15, .25, .25, .20)','(.6, .8, 1.4, .5)','99 / 0%'),
          ('E4 stable','(.10, .20, .20, .15)','(.3, .5, 1.6, .3)','42 / 0%'),
          ('E4 balanced','(.10, .20, .20, .15)','(.8, .8, 1.2, .6)','42 / 0%'),
          ('E4 excitable','(.10, .20, .20, .15)','(1.2, 1.0, .8, .4)','42 / 0%'),
          ('E5','(.10, .30, .30, .15)','(.3, 1.0, 1.8, .4)','55 / 0%')]
        t=h.table(['配置' if ZH else 'Setting','连接概率 p' if ZH else 'Connection probabilities p','基础权重 w' if ZH else 'Base weights w','种子 / spread' if ZH else 'Seed / spread'],data,[1.45,2.0,2.0,1.11])
        for row in t.rows[:2]:
            for cell in row.cells:
                for pp in cell.paragraphs: pp.paragraph_format.keep_with_next=True
    elif key=='A2':
        table_cap('表 A2  显式保留边的条件。I-source 表示抑制性源端；并集中的边仅保留一次。' if ZH else 'Table A2. Explicit-edge selection. I-source denotes an inhibitory source; an edge in both union components is retained once.')
        t=h.table(['配置' if ZH else 'Setting','保留条件' if ZH else 'Retention predicate'],[
          ('E1 / E1 gain scan / E3 homogeneous','I-source w ≥ 1.0; pure E1: none'),
          ('E3 heterogeneous main','I-source w ≥ 1.4'),
          ('E3 budget sweep','None (0%); I-source w ≥ θ; θ ∈ {2.0, 1.75, 1.4, 1.1, 0.8}'),
          ('E3 edge classes','I-source w ≥ 1.0; I→I w ≥ 0.25; E→I w ≥ 0.70; union of first two'),
          ('E4 stable / balanced / excitable','I-source w ≥ 0.8w_IE = 1.28 / 0.96 / 0.64'),
          ('E5','I-source w ≥ 1.5')],[2.35,4.21])
        if not ZH:
            for row in t.rows[:-1]:
                for cell in row.cells:
                    for pp in cell.paragraphs: pp.paragraph_format.keep_with_next=True
    elif key=='B1':
        pp=table_cap('表 B1  输出规则对照。r / δFR 给出相关系数与发放率百分比误差。所有原始求和设置均无群体计数差异。' if ZH else 'Table B1. Output-rule controls. Each r / δFR entry reports correlation and percent rate error. Raw-sum population counts agree in every setting.')
        data=[]
        labels=['E1 pure','E1 hybrid','E3 heterogeneous','E3 homogeneous','E4 stable','E4 balanced','E4 excitable','E5 pulse']
        for r,label in zip([r for r in rows if r['variant']=='original_instrumented'],labels):
            k=counterpart(r,'kappa_only');raw=counterpart(r,'raw_sum')
            data.append([label,f'{float(r["psth_r"]):.3f} / {float(r["fr_delta"]):+.1f}',f'{float(k["psth_r"]):.3f} / {float(k["fr_delta"]):+.1f}',f'{float(raw["event_ratio_from_counts"]):.3f}',f'0 / {r["steps"]}'])
        t=h.table(['配置' if ZH else 'Setting','调制 r / δFR%' if ZH else 'History r / δFR%','κR r / δFR%','求和 Q' if ZH else 'Raw Q','求和差异槽 / 总槽数' if ZH else 'Raw mismatches / slots'],data,[1.70,1.35,1.35,.70,1.46])
        if key=='B1':
            for row in t.rows[:-1]:
                for cell in row.cells:
                    for pp in cell.paragraphs: pp.paragraph_format.keep_with_next=True
    else: raise ValueError(key)

def sections(items):
    for heading,body in items:
        section_start=len(doc.paragraphs)
        pp=p(heading,'Heading 1')
        blocks=body.split('\n\n')
        for index,block in enumerate(blocks):
            m=re.fullmatch(r'\[\[(EQ|FIG|TABLE):([^\]]+)\]\]',block)
            if m:
                {'EQ':eq,'FIG':figure,'TABLE':tab}[m[1]](m[2]); continue
            if re.match(r'^\d+\.\d+ ',block): p(block,'Heading 2'); continue
            pp=p(block)
            if re.match(r'^[A-Z]\.\d+ ', block):
                pp.paragraph_format.keep_with_next=True
                pp.paragraph_format.keep_together=True
            if len(block)<250 and index+1<len(blocks) and blocks[index+1].startswith('[[EQ:'):
                pp.paragraph_format.keep_with_next=True
            if not ZH and block.startswith('Proposition 3') and index+1<len(blocks) and blocks[index+1].startswith('[[EQ:'):
                pp.paragraph_format.keep_with_next=True
            if block.startswith(('最初的静态增益运行', 'The first static-gain run')):
                pp.paragraph_format.keep_together=True
            label=re.match(r'^((?:Proposition [1234]|Corollary [12])(?: \([^)]*\))?\.|Proof\.)\s*',block) if not ZH else re.match(r'^((?:命题 [1234]|推论 [12])(?:（[^）]*）)?[。.．]|证明[。.．])\s*',block)
            if label:
                # Emphasize only the proposition/proof label, including its qualifier.
                rendered=labels.rewrite(block)
                prefix=label.group()
                pp.clear();pp.add_run(prefix).bold=True;pp.add_run(rendered[len(prefix):])
                pp.paragraph_format.keep_together=True
        if heading.startswith(('Appendix D', '附录 D')):
            for pp in doc.paragraphs[section_start:]:
                pp.paragraph_format.keep_together=True
            for pp in doc.paragraphs[section_start:-1]:
                pp.paragraph_format.keep_with_next=True

p(paper.TITLE,'Title')
pp=p(paper.AUTHOR);pp.paragraph_format.alignment=WD_ALIGN_PARAGRAPH.LEFT
pp.paragraph_format.space_after=Pt(2)
pp=p(paper.AFFILIATION);pp.paragraph_format.alignment=WD_ALIGN_PARAGRAPH.LEFT
pp.paragraph_format.space_after=Pt(8)
cap('预印本  2026 年 11 月 9 日' if ZH else 'Preprint  •  9 November 2026')
sections(paper.SECTIONS)
p('参考文献' if ZH else 'References','Heading 1')
for ref in paper_en.REFERENCES:
    pp=p(ref);pp.paragraph_format.line_spacing=1.05;pp.paragraph_format.space_after=Pt(6)
    pp.paragraph_format.keep_together=True
    pp.paragraph_format.alignment=WD_ALIGN_PARAGRAPH.LEFT
    for rr in pp.runs:rr.font.size=Pt(9.5)
sections(paper.APPENDIX)

# Render inline variable subscripts as editable Word math, not source notation.
inline_vars = ['p_A','p_B','S_T','T_1','T_2','g_E','g_I','L_30','U_300','U_long','L_short','L_i','U_j','h_0','b_0','h_i','τ_i','c_q','τ_q','r_1','r_2','r_3','r_4','w_0','S_ref','L_safer','U_less_safe','R_a','R_b','X_a','X_b','p_j','α_j','S_a','S_c','S_j','S_k','w_e','F_E','F_I','P_kq','D_kq','R_kq','x_kqa','h_kq','x_kqf','x_kqs','x_f','x_s',
               'x_qa','τ_qa','g_qa','κ_E','κ_I','κ_q','g_fE','g_fI','p_EE','p_EI',
               'p_IE','p_II','dt_s','y_approx','y_ref','M_approx','M_ref','δ_FR','w_IE','Σ_e',
               'ΔG_g','G_g','G_0','U_5','F_5','Y_g','S_train','M_arm',
               'D_slot','D_count','D_global','R_count','N_ref','R_τ','V_τ','h_τ','s_ref','δ_kn','e_b','e_d','[x]_+']
extra_math={
    'S_T₁':lambda:h.sub('S',h.sub('T','1')), 'S_T₂':lambda:h.sub('S',h.sub('T','2')),
    'T₁':lambda:h.sub('T','1'), 'T₂':lambda:h.sub('T','2'),
    **{f'2^−{n}': (lambda n=n: h.sup('2', f'−{n}')) for n in [4,6,8,12,16,20,24,149]},
    'Vlo':lambda:h.sub('V','lo'), 'Vhi':lambda:h.sub('V','hi'),
    'W_d^q':lambda:h.sup(h.sub('W','d'),'q'),
    'W̃_d^q':lambda:h.sup(h.sub(acc('W','̃'),'d'),'q'),
    'ΔW_d^q':lambda:h.sup(h.sub('ΔW','d'),'q'),
    'f_ref,k,τ':lambda:h.sub('f','ref,k,τ'),
    'f_k,τ':lambda:h.sub('f','k,τ'),
    'w(s_a − s_c)':lambda:h.seq('w(',h.sub('s','a'),' − ',h.sub('s','c'),')'),
    'X_g^a':lambda:h.sup(h.sub('X','g'),'a'),'r_g^a':lambda:h.sup(h.sub('r','g'),'a'),
    'q_g^a':lambda:h.sup(h.sub('q','g'),'a'),'W^E':lambda:h.sup('W','E'),'W^I':lambda:h.sup('W','I'),
    'ΔW^q':lambda:h.sup('ΔW','q'),'W̃^q':lambda:h.sup(acc('W','̃'),'q'),
    'W^q':lambda:h.sup('W','q'),'B^q':lambda:h.sup('B','q'),
    'Pᵀ':lambda:h.sup('P','T'),'P_kg':lambda:h.sub('P','kg'),
    's̄':lambda:acc('s','̄'),'s̃':lambda:acc('s','̃'),'Î':lambda:acc('I','̂'),
    'W₁':lambda:h.sub('W','1'),'W₂':lambda:h.sub('W','2'),
    's_a':lambda:h.sub('s','a'),'s_c':lambda:h.sub('s','c'),
    'B_tk':lambda:h.sub('B','tk'),'B_test':lambda:h.sub('B','test'),'B_ref':lambda:h.sub('B','ref')}
# Keep the proof's complete norm inequality in one native math object so its
# opening delimiter cannot be stranded at the previous line's right margin.
extra_math['‖W₁s − W₂s‖ ≤ ‖W₁s − Î‖ + ‖Î − W₂s‖'] = lambda: h.seq(
    norm(h.seq(h.sub('W','1'),'s − ',h.sub('W','2'),'s')), ' ≤ ',
    norm(h.seq(h.sub('W','1'),'s − ',acc('I','̂'))), ' + ',
    norm(h.seq(acc('I','̂'),' − ',h.sub('W','2'),'s')))
def inline_text(pp,text):
    label=re.match(r'^((?:Proposition [1234]|Corollary [12])(?: \([^)]*\))?\.|Proof\.)\s*',text) if not ZH else re.match(r'^((?:命题 [1234]|推论 [12])(?:（[^）]*）)?[。.．]|证明[。.．])\s*',text)
    if label:
        pp.add_run(label.group()).bold=True
        if len(text)>label.end():pp.add_run(text[label.end():])
    else:pp.add_run(text)

# ASCII subscript tokens may also occur inside literal CSV identifiers. Protect
# those identifiers while retaining adjacent mathematical products such as PᵀP.
inline_pattern=re.compile('|'.join(
    r'(?<![A-Za-z0-9_])'+re.escape(v)+r'(?![A-Za-z0-9_])'
    if re.fullmatch(r'[A-Za-z][A-Za-z0-9]*_[A-Za-z0-9,]+', v) else re.escape(v)
    for v in sorted(inline_vars+list(extra_math),key=len,reverse=True)))
for pp in doc.paragraphs:
    text=pp.text
    if not inline_pattern.search(text):continue
    pp.clear();pos=0
    for match in inline_pattern.finditer(text):
        if match.start()>pos:inline_text(pp,text[pos:match.start()])
        token=match.group()
        if token in extra_math:node=extra_math[token]()
        else:base,script=token.split('_',1);node=h.sub(base,script)
        pos=match.end()
        punctuation=text[pos:pos+1] if text[pos:pos+1] in {'.',',',';',':','。','，','；','：'} else ''
        if punctuation:pos+=1
        math=OxmlElement('m:oMath');math.extend(h.seq(node,punctuation));pp._p.append(math)
    if pos<len(text):inline_text(pp,text[pos:])

for pp in doc.paragraphs:
    if '9a266203cf86bbe4' in pp.text:
        pp.paragraph_format.alignment=WD_ALIGN_PARAGRAPH.LEFT

# The retention-predicate table uses the same subscript as the prose.
for tt in doc.tables:
    for row in tt.rows:
        for cell in row.cells:
            for pp in cell.paragraphs:
                if 'w_IE' not in pp.text: continue
                before,after=pp.text.split('w_IE',1)
                pp.clear()
                for text,subscript in [(before+'w',False),('IE',True),(after,False)]:
                    rr=pp.add_run(text);rr.font.size=Pt(9);rr.font.subscript=subscript

if ZH:
    title=doc.paragraphs[0]
    for rr in title.runs:
        rr.font.name='Songti SC';rr.font.bold=False
        rf=rr._r.get_or_add_rPr().get_or_add_rFonts()
        for key in list(rf.attrib):
            if 'theme' in key.lower():del rf.attrib[key]
        for attr in ['ascii','hAnsi','eastAsia','cs']:rf.set(qn('w:'+attr),'Songti SC')

# Keep all externally supplied identifiers and native math, and reject unexpanded markers.
assert not any('[[' in pp.text for pp in doc.paragraphs)
args.output_dir.mkdir(parents=True, exist_ok=True)
path=args.output_dir/f'input-and-horizon-dependent-structural-fidelity-preprint-{LANG}.docx'
doc.save(path)
(args.output_dir/f'document-labels-{LANG}.json').write_text(json.dumps(labels.report(),ensure_ascii=False,indent=2)+'\n')
print(path)
