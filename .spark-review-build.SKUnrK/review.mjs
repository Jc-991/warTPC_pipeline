import fs from 'node:fs/promises';
import path from 'node:path';
import { Presentation, PresentationFile } from '@oai/artifact-tool';
const p=Presentation.create({slideSize:{width:1280,height:720}});
const a=JSON.parse(await fs.readFile('/tmp/wartpc-spark-deck-assets.json','utf8'));
const c=(prefix)=>Object.entries(a.combined).find(([k])=>k.startsWith(prefix+'_'))?.[1];
const r=(run,k)=>a.runs[run][k+'.png'];
function txt(s,t,x,y,w,h,size,color='#142D43',bold=false){
 const sh=s.shapes.add({geometry:'textbox',position:{left:x,top:y,width:w,height:h}});
 sh.text=t;
 sh.text.style={fontSize:size,color,bold,typeface:'Arial',insets:{left:0,right:0,top:0,bottom:0}};
}
const body=(s,t,x,y,w,h)=>txt(s,t,x,y,w,h,24);
function slide(title,sub){
 const s=p.slides.add();s.background.fill='#FFFFFF';
 txt(s,title,56,43,1170,60,42,'#142D43',true);
 if(sub)txt(s,sub,58,112,1160,54,22,'#486779');
 return s;
}
async function im(s,file,x,y,w,h,alt){
 const b=await fs.readFile(file);
 s.images.add({blob:b.buffer.slice(b.byteOffset,b.byteOffset+b.byteLength),contentType:'image/png',
 alt,fit:'contain',position:{left:x,top:y,width:w,height:h}});
}
const note=(s,t)=>s.speakerNotes.text=t;
function definitions(s,items){
 for(const [i,[head,copy]] of items.entries()){
  const y=190+i*120;txt(s,head,58,y,373,52,26,'#087E78',true);body(s,copy,445,y-1,747,78);
 }
}
{
 const s=p.slides.add();s.background.fill='#112B40';
 txt(s,'WARWICK TPC',80,98,1000,45,25,'#86D7CE',true);
 txt(s,'Spark detection\nand removal',80,214,1130,195,76,'#FFFFFF',true);
 txt(s,'Run 7 walkthrough and November 2026 production results',83,510,1100,70,29,'#D5E4EE');
}
{
 const s=slide('Run 7 optical output','voltage-run-22-11-26 / plots / optical_per_run / vr22-07');
 const rows=[
  ['2 text summaries','run_summary.txt is tab-separated. run_summary_readable.txt presents the same values one field per line.'],
  ['2 fit tables','projection_variations_before.csv and projection_variations_after.csv each record 30 X fits and 30 Y fits.'],
  ['20 plot files','Three spark diagnostics, the integrated ToT image, paired X/Y projections and signal histograms, and ten fit-variation histograms.']
 ];
 definitions(s,rows);
 note(s,'Source: local optical_per_run/vr22-07 folder in the 22 November optical export.');
}
{
 const s=slide('1D ToT distribution and spark threshold','Each histogram entry represents one occupied 5 ms window.');
 await im(s,r('vr22-07','tot-distribution-before-sparks'),56,166,753,494,'Run 7 grouped ToT histogram');
 txt(s,'Spark definition',831,209,380,46,27,'#087E78',true);
 body(s,'Sum hit ToT in each occupied window. Flag the window if its sum exceeds the mean plus 10 RMS.',831,263,380,135);
 txt(s,'5 flagged windows',831,422,380,47,33,'#087E78',true);
 body(s,'The red dashed line shows the threshold. The red bars count windows above it.',831,486,380,118);
 note(s,'Sources: vr22-07/080_tot-distribution-before-sparks.png and blackbox/spark_detection.py. RMS is the population standard deviation across occupied windows.');
}
{
 const s=slide('2D ToT versus arrival time','Run 7 before spark tagging. Colour shows the number of hits per display bin.');
 await im(s,r('vr22-07','tot-vs-time-before-sparks'),50,177,1175,440,'Run 7 unfiltered hit ToT versus time');
 body(s,'The horizontal axis starts at the first stored hit. The vertical axis is the ToT of each hit.',60,632,1160,56);
 note(s,'Source: vr22-07/090_tot-vs-time-before-sparks.png. The colour scale counts hits in display bins.');
}
{
 const s=slide('Run 7 hits removed by the cut','The cut removes every hit in a flagged window.');
 await im(s,r('vr22-07','tot-vs-time-spark-removal'),50,171,1175,435,'Run 7 ToT versus time with 231,465 removed hits marked');
 body(s,'Red circles mark 231,465 removed hits across five windows. At full-run scale they appear in two bands near 26 s and 97 s.',60,600,1165,58);
 txt(s,'Exposure removed: 25 ms out of 189.988 s.',60,666,1130,35,20,'#087E78',true);
 note(s,'Sources: vr22-07/100_tot-vs-time-spark-removal.png and run_summary_readable.txt.');
}
const comparisons=[
 ['Flagged spark windows','S17','C11','One count per flagged 5 ms window.'],
 ['Fraction of exposure removed','S19','C12','Flagged time within the run divided by original exposure.'],
 ['Mean X position','S05','C05','The bars show X positional RMS.'],
 ['Mean Y position','S09','C07','The bars show Y positional RMS.']
];
for(const [title,sid,cid,sub] of comparisons){
 const s=slide(title,sub);
 txt(s,'Streaming by run order',57,178,555,40,23,'#087E78',true);
 txt(s,'Voltage and pressure overlay',646,178,575,40,23,'#087E78',true);
 await im(s,c(sid),50,223,575,409,sid+' '+title);
 await im(s,c(cid),642,223,585,409,cid+' '+title);
 txt(s,'Only runs with saved values for this quantity appear.',60,655,1130,35,18,'#486779');
 note(s,[c(sid),c(cid)].join('\n'));
}
for(const [title,id,sub] of [
 ['Normalized optical signal','C01','Sₒⁿᵒʳᵐ versus V/P across the voltage and pressure scans.'],
 ['Normalized optical background','C14','Bₒⁿᵒʳᵐ combines the X and Y fits. The error bar is the fit RMS divided by usable exposure.'],
 ['Optical signal-to-background ratio','C13','Sₒ/Bₒ is dimensionless. Error bars assume independent signal and background spreads.'],
]){
 const s=slide(title,sub);await im(s,c(id),52,161,1170,530,id+' '+title);
 note(s,'Source: '+c(id)+'\nThe figure footnote identifies recovered fits and omitted runs.');
}
if(p.slides.items.length!==12)throw Error('Unexpected slide count');
await (await PresentationFile.exportPptx(p)).save(path.join(path.dirname(new URL(import.meta.url).pathname),'candidate.pptx'));
