from pathlib import Path
import csv,json,re
base=Path('/tmp/local-circuit-repro-diagnostics')
rows=[]
selected=['4ch+trace (pure)','4ch+trace (hybrid)','4ch+trace-strong-inh (11.2%)','4ch+trace-strong-inh (homo, 22.8%)','stable','balanced','excitable','E5']
for variant in ['original_instrumented','raw_sum','kappa_only']:
 log=base/variant/'logs/closure-complete.log'
 for line in log.read_text().splitlines():
  if '[DIAGNOSTIC]' not in line and '[DIAGNOSTIC_E45]' not in line:continue
  label,values=line.split('label=',1)[1].split(' psth_r=',1)
  values='psth_r='+values
  row={'variant':variant,'label':label,'source_log':str(log)}
  for key,val in re.findall(r'(\w+)=([+-]?[0-9]+(?:\.[0-9]+)?)',values):row[key]=float(val) if '.' in val else int(val)
  row['event_ratio_from_counts']=row['approx_events']/row['explicit_events']
  row['event_reduction_pct']=100*(1-row['event_ratio_from_counts'])
  if label in ['2ch','4ch-default','4ch+trace (pure)','4ch+trace (hybrid)']: row.update(benchmark='E1 50k',units=50000,steps=500,dt_ms=.1)
  elif label=='4ch+trace-strong-inh (homo, 22.8%)':row.update(benchmark='E3 homogeneous',units=12500,steps=300,dt_ms=.1)
  elif label in ['stable','balanced','excitable']:row.update(benchmark='E4 '+label,units=5000,steps=200,dt_ms=.1)
  elif label=='E5':row.update(benchmark='E5 perturbation',units=5000,steps=300,dt_ms=.1)
  elif label.startswith(('4ch+trace-strong','stateful_thr','Strong','Fast','Short')):row.update(benchmark='E3 heterogeneous',units=12500,steps=200,dt_ms=.1)
  else:row.update(benchmark='E1 medium calibration',units=12500,steps=200,dt_ms=.1)
  row['duration_ms']=row['steps']*row['dt_ms']
  row['explicit_mean_fr_hz']=row['explicit_spikes']/(row['units']*row['duration_ms']/1000)
  row['approx_mean_fr_hz']=row['approx_spikes']/(row['units']*row['duration_ms']/1000)
  rows.append(row)
fields=['variant','benchmark','label','units','steps','dt_ms','duration_ms','psth_r','fr_delta','explicit_events','approx_events','event_ratio_from_counts','event_reduction_pct','explicit_spikes','approx_spikes','explicit_mean_fr_hz','approx_mean_fr_hz','mismatch_steps','max_step_spike_delta','event_ratio','source_log']
for name,data in [('diagnostic-results-exact',rows),('primary-comparison-exact',[r for r in rows if r['label'] in selected])]:
 (base/(name+'.json')).write_text(json.dumps(data,indent=2)+'\n')
 with (base/(name+'.csv')).open('w') as f:
  w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(data)
print('exact rows',len(rows),'primary rows',sum(r['label'] in selected for r in rows))
