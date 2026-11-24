#!/usr/bin/env python3
"""Isolated Warwick TPC optical + V50 pipeline; never modifies input data."""
import argparse, csv, datetime, json, os, shutil, subprocess, sys, zipfile
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from scipy.signal import find_peaks, peak_widths

BINS=np.linspace(0,6000,200)
REQUIRED=['rawdata_000000.tpx3','settings.csv']

def parse_settings(path):
 with path.open(newline='') as f: row=next(csv.reader(f))
 if len(row)<8: raise ValueError(f'Invalid settings: {path}')
 p=float(row[1]); vs=list(map(float,row[2:7]));
 if not np.isfinite(p) or p<=0: raise ValueError(f'Invalid pressure: {p}')
 return dict(pressure_mbar=p,v_over_p=(vs[4]-vs[3]+vs[2]-vs[1])/p)

def run_cmd(cmd,cwd,log):
 with log.open('w') as f:
  f.write('Command: '+repr([str(x) for x in cmd])+'\n');f.flush()
  return subprocess.run([str(x) for x in cmd],cwd=cwd,stdout=f,stderr=subprocess.STDOUT).returncode

def v50_result(path,run,out):
 a=np.genfromtxt(path,skip_header=1,ndmin=2)
 if a.shape[1]<3:raise ValueError('pulseheights.csv has fewer than 3 columns')
 values=a[:,2];finite=values[np.isfinite(values)]
 if not len(finite):raise ValueError('No finite V50 values')
 h,_=np.histogram(finite,bins=BINS);outside=int(((finite<0)|(finite>6000)).sum())
 # Ignore the first bin when identifying peaks. Preserve the original histogram
 # for width estimation and counts; it is not discarded from the data.
 candidate=h.copy();candidate[0]=0
 peaks,_=find_peaks(candidate,prominence=.5,distance=15);peaks=peaks[peaks>0]
 top=peaks[np.argsort(h[peaks])[-2:]]
 peak=width=None;flags=[]
 if len(top)==0:flags.append('no peak found after ignoring first bin')
 else:
  if len(top)==1:flags.append('single-peak fallback; review')
  amps=h[top]-np.min(h);mus=np.where(amps<20,0.,BINS[top]);widths=peak_widths(candidate,top,rel_height=.5)[0]*np.mean(np.diff(BINS))/2.355;k=int(np.argmax(mus));peak=float(mus[k]);width=float(widths[k]);
  if top[k]==1:flags.append('peak touches ignored first bin; review')
  if not np.isfinite(width) or width<=0:width=None;flags.append('peak width unavailable')
  if (amps<20).any():flags.append('at least one candidate peak below 20 counts')
  if peak<=0:flags.append('notebook assigns zero; not a valid log-axis point')
 if outside:flags.append('events outside 0–6000 mV histogram')
 # The displayed range adapts to the data; peak selection always uses BINS above.
 xmax=min(max(10.,float(np.quantile(finite,.90))*1.3),max(8100.,float(np.max(finite))))
 displayed=int(((finite>=0)&(finite<=xmax)).sum());numbins=min(80,max(20,int(np.sqrt(len(finite)))))
 fig,ax=plt.subplots(figsize=(8,5));ax.hist(finite,bins=np.linspace(0,xmax,numbins+1),color='#247ca5',edgecolor='white',linewidth=.3);ax.set_xlim(0,xmax);ax.set_xlabel(r'Channel B $V_{50}$ (mV)');ax.set_ylabel('Entries');ax.set_title(f'{run} — V50 distribution');ax.text(.98,.97,f'Events: {len(finite):,}\nOutside shown range: {len(finite)-displayed:,}',transform=ax.transAxes,ha='right',va='top',bbox=dict(facecolor='white',edgecolor='0.8'));ax.grid(axis='y',alpha=.2);fig.tight_layout();fig.savefig(out/f'{run}_V50.png',dpi=150);plt.close(fig)
 return dict(v50_entries=len(values),v50_nonfinite=len(values)-len(finite),v50_outside_6000=outside,v50_peak=peak if peak and peak>0 else None,v50_width=width if peak and peak>0 else None,v50_status='; '.join(flags))

def plot_summary(rows,folder):
 folder.mkdir(parents=True,exist_ok=True); names=[r['run'] for r in rows]
 for metric in ['optical','v50','ratio']:
  for kind in ['streaming','physics']:
   for scale in (['linear'] if metric=='ratio' else ['linear','log']):
    fig,ax=plt.subplots(figsize=(max(8,len(rows)*.48),5.5) if kind=='streaming' else (8,5.5))
    found=0;plotted_values=[];plotted_points=[]
    for i,r in enumerate(rows):
     val=r.get(metric);err=r.get(metric+'_err');vp=r.get('v_over_p')
     if val is None or not np.isfinite(val) or (scale=='log' and val<=0) or (kind=='physics' and vp is None):continue
     x=i if kind=='streaming' else vp; flagged=bool(r.get('v50_status')) if metric in ('v50','ratio') else False
     ax.errorbar(x,val,yerr=err if err is not None and np.isfinite(err) else None,fmt='o',color='tab:blue',mfc='none' if flagged else 'tab:blue',capsize=3);found+=1;plotted_values.append(val);plotted_points.append((val,err))
    if not found:ax.text(.5,.5,'No valid results available',transform=ax.transAxes,ha='center',va='center')
    if kind=='streaming':ax.set_xticks(range(len(names)),names,rotation=65,fontsize=8);ax.set_xlabel('Run')
    else:ax.set_xlabel(r'$V_{43+21}/P$ (kV bar$^{-1}$)')
    ax.set_ylabel({'optical':r'$S_O^{\mathrm{norm}}$ (ms s$^{-1}$)','v50':r'$V_{50}$ peak estimate (mV)','ratio':r'$S_O^{\mathrm{norm}}/V_{50}$ (ms s$^{-1}$ mV$^{-1}$)'}[metric]);ax.set_yscale(scale)
    if plotted_values and max(plotted_values)>0:
     limit=1.1*max(plotted_values);ax.set_ylim(top=limit)
     if any(e is not None and np.isfinite(e) and v+e>limit for v,e in plotted_points):ax.text(.99,.99,'Error bars extend beyond axis',transform=ax.transAxes,ha='right',va='top',fontsize=8)
    if scale=='linear':ax.set_ylim(bottom=0)
    ax.grid(alpha=.2);fig.tight_layout();fig.savefig(folder/f'{metric}_{kind}_{scale}.png',dpi=150);plt.close(fig)

def comparisons(results,out,excluded,paper):
 # One latest completed execution per dataset. Read only the pipeline's own outputs.
 groups={}
 for meta in results.glob('*/dataset.json'):
  try:
   info=json.loads(meta.read_text()); data=meta.parent/'results.csv'
   if data.is_file() and (info['dataset'] not in groups or meta.parent.name>groups[info['dataset']].name):groups[info['dataset']]=meta.parent
  except (ValueError,KeyError,OSError):continue
 allrows=[]
 history=Path(__file__).resolve().parent.parent/'reference'/'history.csv'
 if history.is_file():
  with history.open(newline='') as f:
   for row in csv.DictReader(f):
    if row.get('run') in excluded or row.get('dataset') in groups:continue
    try:
     clean={key:(float(row[key]) if row.get(key) not in ('',None) else None) for key in ['v_over_p','optical','optical_err','v50','v50_err','ratio','ratio_err']}
     clean.update(dataset=row['dataset'],run=row['run'],flag=row.get('flag',''));allrows.append(clean)
    except (ValueError,KeyError):continue
 for name,folder in sorted(groups.items()):
  with (folder/'results.csv').open(newline='') as f:
   for row in csv.DictReader(f):
    if row.get('run') in excluded:continue
    try:
     clean={key:(float(row[key]) if row.get(key) not in ('',None) else None) for key in ['v_over_p','optical','optical_err','v50','v50_err','ratio','ratio_err']}
     clean.update(dataset=name,run=row['run'],flag=row.get('v50_status',''));allrows.append(clean)
    except (ValueError,KeyError):continue
 labels=sorted({r['dataset'] for r in allrows})
 dest=out/'comparisons';dest.mkdir()
 for metric in ['optical','v50','ratio']:
  fig,ax=plt.subplots(figsize=(9,6));anypoints=False
  for name in labels:
   subset=[r for r in allrows if r['dataset']==name and r[metric] is not None and r['v_over_p'] is not None and (metric=='ratio' or r[metric]>0)]
   if not subset:continue
   color=plt.rcParams['axes.prop_cycle'].by_key()['color'][labels.index(name)%10]
   for r in subset:
    ax.errorbar(r['v_over_p'],r[metric],yerr=r[metric+'_err'],fmt='o',color=color,mfc='none' if metric in ('v50','ratio') and r['flag'] else color,capsize=2)
   ax.scatter([],[],color=color,label=name);anypoints=True
  if not anypoints:ax.text(.5,.5,'No valid results available',ha='center',transform=ax.transAxes)
  if metric!='ratio':ax.set_yscale('log')
  else:ax.set_ylim(bottom=0)
  values=[r[metric] for r in allrows if r['v_over_p'] is not None and r[metric] is not None and np.isfinite(r[metric]) and (metric=='ratio' or r[metric]>0)]
  if values and max(values)>0:
   limit=1.1*max(values);ax.set_ylim(top=limit)
   if any(r['v_over_p'] is not None and r[metric] is not None and r[metric+'_err'] is not None and np.isfinite(r[metric]) and np.isfinite(r[metric+'_err']) and r[metric]+r[metric+'_err']>limit for r in allrows):ax.text(.99,.99,'Error bars extend beyond axis',transform=ax.transAxes,ha='right',va='top',fontsize=8)
  ax.set_xlabel(r'$V_{43+21}/P$ (kV bar$^{-1}$)');ax.set_ylabel({'optical':r'$S_O^{\mathrm{norm}}$ (ms s$^{-1}$)','v50':r'$V_{50}$ peak estimate (mV)','ratio':r'$S_O^{\mathrm{norm}}/V_{50}$ (ms s$^{-1}$ mV$^{-1}$)'}[metric]);ax.grid(alpha=.2)
  if anypoints:ax.legend(fontsize=8)
  fig.tight_layout();fig.savefig(dest/f'{metric}_physics_comparison.png',dpi=150);plt.close(fig)
 if paper:
  from PIL import Image, ImageDraw
  image=Image.open(paper).convert('RGB')
  if image.size!=(2750,2000):raise ValueError('Paper overlay must be the calibrated 2750x2000 Figure 26 image used in this project')
  draw=ImageDraw.Draw(image);colors=['#e07900','#0070bf','#8844aa','#008888','#c62828'];legend=[]
  for j,name in enumerate(labels):
   color=colors[j%len(colors)];legend.append((name,color))
   for r in allrows:
    if r['dataset']!=name or r['v_over_p'] is None or r['optical'] is None or not (0<=r['v_over_p']<=3 and 1e-4<=r['optical']<=100):continue
    x=480+(2386-480)*r['v_over_p']/3;y=1616-(np.log10(r['optical'])+4)/6*(1616-247);draw.ellipse((x-16,y-16,x+16,y+16),outline=color,width=5)
  from PIL import ImageFont
  font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',26) if Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf').exists() else ImageFont.load_default()
  y=40
  for name,color in legend:draw.text((1900,y),name,fill=color,font=font);y+=36
  image.save(dest/'optical_paper_overlay.png')
  omitted=[r for r in allrows if r['optical'] is not None and r['v_over_p'] is not None and not (0<=r['v_over_p']<=3 and 1e-4<=r['optical']<=100)]
  with (dest/'paper_overlay_out_of_range.csv').open('w',newline='') as f:
   w=csv.DictWriter(f,fieldnames=['dataset','run','v_over_p','optical']);w.writeheader();w.writerows([{k:r[k] for k in w.fieldnames} for r in omitted])

def main():
 ap=argparse.ArgumentParser(description='Analyse one extracted dataset without changing it.')
 ap.add_argument('dataset',type=Path,help='ZIP archive or extracted folder containing optical/ and charge/')
 ap.add_argument('--blackbox',type=Path,required=True,help='Blackbox code directory containing tpx3dump and optical-analysis.py')
 ap.add_argument('--results',type=Path,required=True,help='Parent directory for timestamped outputs')
 ap.add_argument('--exclude',default='prp2-04,prp3-04',help='Comma-separated run IDs to exclude from summary and comparison plots; per-run data are retained')
 ap.add_argument('--paper-overlay',type=Path,default=Path(__file__).resolve().parent.parent/'reference'/'figure26_reference.png',help='Calibrated 2750x2000 Figure 26 image (default: bundled reference)')
 ap.add_argument('--reuse-hdf5',action='store_true',help='Copy existing input output.hdf5 files rather than converting raw data; only use verified completed files')
 args=ap.parse_args();dataset=args.dataset.expanduser().resolve();code=args.blackbox.expanduser().resolve();results=args.results.expanduser().resolve()
 if not dataset.exists():ap.error(f'Dataset does not exist: {dataset}')
 if dataset.is_dir() and (not (dataset/'optical').is_dir() or not (dataset/'charge').is_dir()):ap.error('Dataset must contain optical/ and charge/ folders')
 if dataset.is_file() and not zipfile.is_zipfile(dataset):ap.error('Dataset file must be a ZIP archive')
 dataset_label=dataset.stem if dataset.is_file() else dataset.name
 for name in ['tpx3dump','optical-analysis.py']:
  if not (code/name).is_file():ap.error(f'Missing {code/name}')
 if not args.reuse_hdf5 and not os.access(code/'tpx3dump',os.X_OK):ap.error('tpx3dump is not executable')
 # ROOT dependency fails early instead of producing a false successful report.
 try:import ROOT
 except ImportError as e:ap.error(f'ROOT not available in this Python environment: {e}')
 now=datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f');out=results/f'{dataset_label}_{now}';out.mkdir(parents=True,exist_ok=False)
 if dataset.is_file():
  unpack=out/'input_extracted';unpack.mkdir()
  with zipfile.ZipFile(dataset) as z:
   entries=z.infolist();roots=set()
   for entry in entries:
    part=Path(entry.filename)
    if part.is_absolute() or '..' in part.parts or not part.parts or (entry.external_attr>>16)&0o170000==0o120000:raise ValueError(f'Unsafe ZIP entry: {entry.filename}')
    roots.add(part.parts[0])
   if len(roots)!=1:raise ValueError('ZIP must contain exactly one top-level dataset directory')
   z.extractall(unpack)
  dataset=unpack/next(iter(roots))
  if not (dataset/'optical').is_dir() or not (dataset/'charge').is_dir():raise ValueError('Extracted dataset must contain optical/ and charge/ folders')
 optical=out/'work'/'optical';(optical/'results').mkdir(parents=True);(out/'logs').mkdir();(out/'v50_distributions').mkdir();(out/'optical_per_run').mkdir();
 runnames=sorted({p.name for parent in [dataset/'optical',dataset/'charge'] for p in parent.iterdir() if p.is_dir() and p.name!='results'})
 rows=[]; failures=[];warnings=[]
 for run in runnames:
  print(f'Processing {run}',flush=True);r={'run':run,'optical':None,'optical_err':None,'v50':None,'v50_err':None,'ratio':None,'ratio_err':None,'v_over_p':None};orig=dataset/'optical'/run;charge=dataset/'charge'/run;rd=optical/run;rd.mkdir()
  settings=orig/'settings.csv' if (orig/'settings.csv').is_file() else charge/'settings.csv'
  try:r.update(parse_settings(settings))
  except Exception as e:failures.append(f'{run}: settings: {e}')
  if (charge/'pulseheights.csv').is_file():
   try:
    q=v50_result(charge/'pulseheights.csv',run,out/'v50_distributions');r.update(q);r['v50']=q['v50_peak'];r['v50_err']=q['v50_width']
   except Exception as e:failures.append(f'{run}: V50: {e}')
  else:failures.append(f'{run}: missing pulseheights.csv')
  try:
   if not orig.is_dir() or not (orig/'settings.csv').is_file():raise ValueError('missing optical directory or settings.csv')
   shutil.copy2(orig/'settings.csv',rd/'settings.csv');hdf=rd/'output.hdf5'
   if args.reuse_hdf5:
    source=orig/'output.hdf5'
    if not source.is_file() or not source.stat().st_size:raise ValueError('no nonempty existing HDF5')
    shutil.copy2(source,hdf)
   else:
    raw=orig/'rawdata_000000.tpx3'
    if not raw.is_file():raise ValueError('missing raw TPX3 file')
    rc=run_cmd([code/'tpx3dump','-i',raw,'-o',hdf],code,out/'logs'/f'{run}_conversion.log')
    if rc:raise RuntimeError(f'tpx3dump exit code {rc}')
   rc=run_cmd([sys.executable,code/'optical-analysis.py',optical,run,'output.hdf5'],code,out/'logs'/f'{run}_optical.log')
   if rc:raise RuntimeError(f'optical analysis exit code {rc}')
   per=rd/'integral.csv'
   with per.open(newline='') as f:vals=next(csv.reader(f))
   r['settings_id']=vals[0]
   if vals[0]!=run:warnings.append(f'{run}: settings ID is {vals[0]}; result associated with folder {run}. Verify metadata.')
   r['optical']=float(vals[8]);r['optical_err']=float(vals[9])
   targets={
     'Total-Stacked-signal-integral.png':'combined_integral_distribution.png',
     'signal-integral_x/2nd_degree/4to8/4to8_signal.png':'x_projection_signal.png',
     'signal-integral_y/2nd_degree/4to8/4to8_signal.png':'y_projection_signal.png',
     'signal-integral_x/2nd_degree/4to8/ToT-image.png':'2D_integrated_ToT.png',
   }
   dst=out/'optical_per_run'/run;dst.mkdir()
   for rel,name in targets.items():
    if (rd/rel).is_file():shutil.copy2(rd/rel,dst/name)
    else:failures.append(f'{run}: missing optical image {rel}')
   spectrum=rd/'diagnostics'/'tot-vs-time-before-sparks.png'
   if spectrum.is_file():shutil.copy2(spectrum,dst/spectrum.name)
  except Exception as e:failures.append(f'{run}: optical: {e}')
  if r['optical'] is not None and r['v50'] is not None and r['v50']>0:
   r['ratio']=r['optical']/r['v50'];r['ratio_err']=abs(r['ratio'])*np.hypot(r['optical_err']/r['optical'],r['v50_err']/r['v50']) if r['optical']!=0 and r['v50_err'] is not None else None
  rows.append(r)
 excluded={x.strip() for x in args.exclude.split(',') if x.strip()}
 plot_summary([r for r in rows if r['run'] not in excluded],out/'summary_plots')
 fields=sorted({key for r in rows for key in r});
 with (out/'results.csv').open('w',newline='') as f:
  writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader();writer.writerows(rows)
 (out/'status.txt').write_text('\n'.join(failures) if failures else 'No processing failures recorded.\n')
 # The requested y maximum depends on central values, so error bars can be clipped.
 for metric in ['optical','v50','ratio']:
  vals=[r for r in rows if r['run'] not in excluded and r.get(metric) is not None and np.isfinite(r[metric]) and r[metric]>0]
  if vals:
   limit=1.1*max(r[metric] for r in vals)
   clipped=[r['run'] for r in vals if r.get(metric+'_err') is not None and np.isfinite(r[metric+'_err']) and r[metric]+r[metric+'_err']>limit]
   if clipped:warnings.append(f'{metric}: upper error bar clipped by y limit for {", ".join(clipped)}')
 (out/'warnings.txt').write_text('\n'.join(warnings) if warnings else 'No metadata or plot warnings recorded.\n')
 (out/'README.txt').write_text('Optical errors are reported RMS. Charge uses raw V50 and the 0–6000 mV notebook peak estimates; widths are not validated peak-position uncertainties. Ratio bars combine optical RMS and estimated peak width as independent spreads, not complete uncertainties. Open markers flag V50 caveats. Missing/zero estimates are omitted, never represented as measured zero. Individual display ranges differ; events outside them are listed on plots. Results are preliminary. Work/ contains generated optical files and may be large. This run is isolated; the original dataset was not modified.\n')
 (out/'dataset.json').write_text(json.dumps({'dataset':dataset_label,'excluded':sorted(excluded)}))
 comparisons(results,out,excluded,args.paper_overlay)
 print(f'Results: {out}');print(f'Issues: {len(failures)} (see status.txt); metadata warnings: {len(warnings)} (see warnings.txt)');return 1 if failures else 0
if __name__=='__main__':sys.exit(main())
