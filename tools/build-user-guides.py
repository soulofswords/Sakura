from pathlib import Path
import re,html,shutil,datetime
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,PageBreak,KeepTogether,Table,TableStyle,Image
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.graphics.shapes import Drawing,Rect,Circle,String,Line
from reportlab.graphics import renderSVG
import reportlab
from pypdf import PdfReader
ROOT=Path.cwd();OUT=ROOT/'output/pdf';PARENT=Path('F:/AI/assistant')
OUT.mkdir(parents=True,exist_ok=True)
fonts=Path(reportlab.__file__).parent/'fonts'
pdfmetrics.registerFont(TTFont('Guide',str(fonts/'Vera.ttf')))
pdfmetrics.registerFont(TTFont('GuideBold',str(fonts/'VeraBd.ttf')))
pdfmetrics.registerFontFamily('Guide',normal='Guide',bold='GuideBold',italic='Guide',boldItalic='GuideBold')
W,H=A4
DATE='28 October 2026 / Version 1.0.1'
def clean(s):
 return s.replace('\u2014','-').replace('\u2013','-').replace('\u2011','-').replace('\u2019',"'").replace('\u201c','"').replace('\u201d','"')
def parse(p):
 text=clean(p.read_text(encoding='utf-8-sig'));chapters=[];current=None
 for line in text.splitlines():
  line=line.strip()
  if line.startswith('## '):
   current={'title':line[3:],'steps':[],'notes':[]};chapters.append(current)
  elif current and line:
   if re.match(r'^\d+\. ',line):current['steps'].append(re.sub(r'^\d+\. ','',line))
   elif line.startswith('Check: '):current['check']=line[7:]
   elif line.startswith('Note: '):current['notes'].append(line[6:])
   else:current['goal']=line
 return chapters
ESC=html.escape
CSS='''*{box-sizing:border-box}body{margin:0;background:#f1f4f8;color:#192438;font:16px/1.65 "Segoe UI",Arial,sans-serif}header{background:#111b2d;color:white;padding:48px max(24px,calc((100vw - 1120px)/2))}header p{color:#ccd5e4;max-width:780px}.tag{color:#fff;background:var(--accent);font-size:12px;letter-spacing:2px;padding:7px 12px;border-radius:30px;display:inline-block}h1{font-size:44px;line-height:1.1;margin:20px 0 12px}h2{font-size:27px;line-height:1.25;color:#13243b}a{color:var(--accent)}.layout{max-width:1168px;margin:28px auto;display:grid;grid-template-columns:250px 1fr;gap:24px;padding:0 24px}nav{align-self:start;position:sticky;top:18px;background:white;border-radius:14px;padding:20px}nav a{display:block;font-size:14px;text-decoration:none;padding:8px 0;border-bottom:1px solid #e8ecf1}main{min-width:0}article,.intro{background:white;border:1px solid #dce3ec;border-radius:16px;padding:28px;margin-bottom:24px;scroll-margin-top:20px}.goal{color:#526076;font-size:17px}.check{padding:16px 18px;background:#e9f7f2;border-left:4px solid #208c6e;border-radius:5px}.note{padding:13px 16px;background:#f4f6fa;border-radius:7px;font-size:14px;color:#46546a}li{padding:5px 0 9px 6px}button,.download{font:inherit;background:var(--accent);color:white;border:0;border-radius:8px;padding:10px 18px;text-decoration:none;cursor:pointer;display:inline-block;margin:8px 10px 0 0}.download.secondary{background:#34435d}footer{text-align:center;padding:24px;color:#63718a;font-size:13px}@media(max-width:800px){.layout{display:block;padding:0 12px}nav{position:static;margin-bottom:24px}h1{font-size:34px}article{padding:20px}}@media print{body{background:white;font-size:11pt}header{padding:20px;color:#182439;background:white}header p{color:#526076}.layout{display:block;max-width:none;padding:0}nav,button,.download{display:none}article{break-before:page;border:0;padding:0;border-radius:0}article li{break-inside:avoid}.intro{border:0;padding:0}.check,.note{break-inside:avoid}footer{display:none}}'''
QUICK={
 'companion':['Open Sakura Companion.exe, choose Cloud API or Local LLM, then Models to load a character.','Choose a local or cloud AI in Settings > AI, test it and save.','Send one typed question, then test voice.','Add screen viewing, camera, phone or Agent tools after basic chat works.'],
 'vtuber':['Open Sakura VTuber.exe, then click Models (person icon) to import/load an avatar.','Choose the camera and basic MediaPipe face source.','Start tracking and calibrate your neutral face.','Enable hands if wanted, then test your recording/output. No chat LLM is needed.']}
PRE={
 'companion':'You need a character model and either a cloud API key/internet connection or a downloaded local AI model. A microphone, webcam, phone and external accounts are optional.',
 'vtuber':'You need a rigged character and a webcam or paired Sakura Mobile. Chat AI/API keys are not required. OBS, NVIDIA SDK files, Leap Motion and internet Collab services are optional.'}
META={
 'companion':('Sakura Companion','#b83571','AI conversation, local/cloud models and approved Agent work'),
 'vtuber':('Sakura VTuber','#087f82','Face, head, arms, fingers and streaming output')}

def layout_map(kind):
 d=Drawing(500,210)
 d.add(Rect(0,0,500,210,rx=8,fillColor=colors.HexColor('#10151b'),strokeColor=colors.HexColor('#45515e')))
 d.add(Rect(0,188,500,22,fillColor=colors.HexColor('#20252c'),strokeColor=None))
 d.add(String(12,196,'Sakura / '+kind.upper(),fontName='GuideBold',fontSize=9,fillColor=colors.white))
 labels=(['Models','Camera & tracking','Voice & speech','Model Settings','Streaming & output','Sakura Mobile','Memory & privacy','Settings'] if kind=='companion' else ['Models','Camera & tracking','Expressions & hotkeys','Background','Streaming & voice','Sakura Mobile','Settings','Collab'])
 for i,label in enumerate(labels):
  y=172-i*20
  d.add(Circle(15,y,7,fillColor=colors.HexColor('#d9effb'),strokeColor=None))
  d.add(String(30,y-2.5,label,fontName='Guide',fontSize=7.5,fillColor=colors.HexColor('#e8edf4')))
 d.add(Circle(243,135,15,fillColor=colors.HexColor('#a7b6c5'),strokeColor=None))
 d.add(Rect(223,65,40,48,rx=10,fillColor=colors.HexColor('#a7b6c5'),strokeColor=None))
 d.add(Line(225,100,207,74,strokeColor=colors.HexColor('#a7b6c5'),strokeWidth=6))
 d.add(Line(261,100,279,74,strokeColor=colors.HexColor('#a7b6c5'),strokeWidth=6))
 d.add(String(198,46,'Your character stage',fontName='Guide',fontSize=8,fillColor=colors.HexColor('#d5e0ec')))
 d.add(Rect(353,12,137,168,rx=7,fillColor=colors.HexColor('#252c35'),strokeColor=colors.HexColor('#4c5c70')))
 d.add(String(365,161,'Models',fontName='GuideBold',fontSize=11,fillColor=colors.white))
 for i,label in enumerate(['Search your characters...','PMX','VRM','Live2D','Import a character']):
  y=132-i*23
  d.add(Rect(364,y,115,17,rx=3,fillColor=colors.HexColor('#374351'),strokeColor=None))
  d.add(String(370,y+5,label,fontName='Guide',fontSize=7,fillColor=colors.white))
 if kind=='companion':
  d.add(Rect(144,12,111,28,rx=4,fillColor=colors.HexColor('#252c35'),strokeColor=colors.HexColor('#4c5c70')))
  d.add(String(151,28,'Chat with Sakura',fontName='GuideBold',fontSize=7,fillColor=colors.white))
  d.add(String(151,18,'Message / microphone',fontName='Guide',fontSize=6.5,fillColor=colors.HexColor('#ccd9e5')))
 else:d.add(String(146,22,'Start tracking   Stop   Calibrate   Hands',fontName='Guide',fontSize=7,fillColor=colors.HexColor('#ccd9e5')))
 return d
def html_guide(kind,chapters):
 title,accent,subtitle=META[kind];base='Sakura_'+('Companion' if kind=='companion' else 'VTuber')+'_Guide'
 nav=''.join(f'<a href="#step-{i}">{ESC(c["title"])}</a>' for i,c in enumerate(chapters,1))
 blocks=[]
 for i,c in enumerate(chapters,1):
  notes=''.join(f'<p class="note">{ESC(x)}</p>' for x in c['notes'])
  diagram=renderSVG.drawToString(layout_map(kind)) if 'Find your way' in c['title'] else ''
  screenshot=next((ROOT/'docs/user-guides/images'/f'{kind}-{suffix}.png' for suffix,words in [('models','Find your way'),('settings','Installed version'),('scenery','PMX backgrounds')] if words.lower() in c['title'].lower()),None)
  if screenshot and screenshot.is_file():diagram+=f'<img style="width:100%;height:auto" src="images/{screenshot.name}" alt="Sakura {kind} interface"><p class="note">Actual UI components shown with demonstration data and no personal avatar.</p>'
  blocks.append(f'<article id="step-{i}"><h2>{ESC(c["title"])}</h2><p class="goal">{ESC(c["goal"])}</p>{diagram}<ol>'+''.join('<li>'+ESC(x)+'</li>' for x in c['steps'])+f'</ol><p class="check"><strong>How to tell it worked</strong><br>{ESC(c["check"])}</p>{notes}</article>')
 return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{title} - Step-by-step guide</title><style>:root{{--accent:{accent}}}{CSS}</style></head><body><header><span class="tag">SAKURA / USER GUIDE</span><h1>{title}</h1><p>{subtitle}. A separate, practical guide for this edition. Updated {DATE}; button names are checked against this app snapshot.</p><a class="download" href="{base}.pdf">Open printable PDF</a><button onclick="window.print()">Print this guide</button><a class="download secondary" href="Sakura_User_Guide.html">Choose a different guide</a></header><div class="layout"><nav aria-label="Guide chapters"><strong>In this guide</strong>{nav}</nav><main><section class="intro"><h2>First successful session</h2><ol>{''.join('<li>'+ESC(x)+'</li>' for x in QUICK[kind])}</ol><p>{ESC(PRE[kind])}</p><p class="note">If using an installer, install the matching edition first and keep its application folder together. Use the current APK for phone features. Features and labels can vary between builds; do not use a screenshot from an older guide as proof of setup.</p></section>{''.join(blocks)}</main></div><footer>Windows guide | {DATE} | Use Ctrl+F to find a feature. This file works offline; linked services and downloads require internet.</footer></body></html>'''
def styles(accent):
 return {
 'eyebrow':ParagraphStyle('eye',fontName='GuideBold',fontSize=9,leading=13,textColor=accent,spaceAfter=12),
 'cover':ParagraphStyle('cover',fontName='GuideBold',fontSize=34,leading=39,textColor=colors.HexColor('#152338'),spaceAfter=14),
 'title':ParagraphStyle('title',fontName='GuideBold',fontSize=23,leading=28,textColor=colors.HexColor('#152338'),spaceAfter=12),
 'goal':ParagraphStyle('goal',fontName='Guide',fontSize=11,leading=16,textColor=colors.HexColor('#526076'),spaceAfter=16),
 'body':ParagraphStyle('body',fontName='Guide',fontSize=10.8,leading=15.8,textColor=colors.HexColor('#233146'),spaceAfter=9),
 'step':ParagraphStyle('step',fontName='Guide',fontSize=10.7,leading=15.8,textColor=colors.HexColor('#233146'),spaceAfter=9,leftIndent=22,firstLineIndent=-19),
 'label':ParagraphStyle('label',fontName='GuideBold',fontSize=9,leading=12,textColor=accent,spaceAfter=5),
 'note':ParagraphStyle('note',fontName='Guide',fontSize=9.6,leading=14,textColor=colors.HexColor('#4b5a70'),spaceAfter=8),
 'toc':ParagraphStyle('toc',fontName='Guide',fontSize=10,leading=15,textColor=colors.HexColor('#233146'),spaceAfter=5)}
def para(text,style):return Paragraph(ESC(text),style)
def chrome(canvas,doc,title,accent):
 canvas.saveState();canvas.setStrokeColor(accent);canvas.setLineWidth(2);canvas.line(43,H-33,W-43,H-33)
 canvas.setFont('GuideBold',8);canvas.setFillColor(colors.HexColor('#526076'));canvas.drawString(43,H-25,title.upper())
 canvas.setStrokeColor(colors.HexColor('#dce3ec'));canvas.setLineWidth(.5);canvas.line(43,38,W-43,38)
 canvas.setFont('Guide',7.5);canvas.drawString(43,24,'USER GUIDE  |  '+DATE);canvas.drawRightString(W-43,24,str(doc.page));canvas.restoreState()
class GuideDoc(SimpleDocTemplate):
    def afterFlowable(self,flowable):
        if isinstance(flowable,Paragraph) and flowable.style.name=='title':
            self.chapter_number=getattr(self,'chapter_number',0)+1
            key='chapter-'+str(self.chapter_number)
            self.canv.bookmarkPage(key)
            self.canv.addOutlineEntry(flowable.getPlainText(),key,level=0,closed=False)

def pdf_guide(kind,chapters,path):
 title,color,subtitle=META[kind];accent=colors.HexColor(color);st=styles(accent)
 story=[para('STEP-BY-STEP / WINDOWS',st['eyebrow']),para(title,st['cover']),para(subtitle,st['goal']),para('Start here',st['label'])]
 for i,line in enumerate(QUICK[kind],1):story.append(para(f'{i}. {line}',st['step']))
 story +=[Spacer(1,9),para('Before you start',st['label']),para(PRE[kind],st['body']),para('Using an installer? Install the matching edition first and keep its application folder together. Phone features use the separate, current Sakura Mobile APK.',st['note']),PageBreak(),para('Find a task',st['title'])]
 for i,c in enumerate(chapters,1):story.append(Paragraph(f'<link href="#chapter-{i}">{ESC(c["title"])}</link>',st['toc']))
 story +=[Spacer(1,12),para('This guide follows the app snapshot checked on '+DATE+'. External services, account permissions and optional hardware still need their own setup. No zero-latency or fixed-FPS promise is made.',st['note'])]
 for c in chapters:
  story += [PageBreak(),para('FOLLOW THESE STEPS',st['eyebrow']),para(c['title'],st['title']),para(c['goal'],st['goal'])]
  if 'Find your way' in c['title']:story += [layout_map(kind),Spacer(1,12)]
  for i,line in enumerate(c['steps'],1):story.append(para(f'{i}. {line}',st['step']))
  story +=[Spacer(1,9),para('HOW TO TELL IT WORKED',st['label']),para(c['check'],st['body']),Spacer(1,6),para('Useful notes and limits',st['label'])]
  for line in c['notes']:story.append(para(line,st['note']))
 for suffix,label in [('models','Models and navigation'),('settings','Theme, version and graphics'),('scenery','PMX backgrounds and props')]:
  screenshot=ROOT/'docs/user-guides/images'/f'{kind}-{suffix}.png'
  if screenshot.is_file():story +=[PageBreak(),para(label,st['title']),para('Actual Sakura 1.0.1 UI components with demonstration data; no personal character or account is shown.',st['note']),Image(str(screenshot),width=509,height=335),Spacer(1,15),para('Use the matching chapters above for detailed instructions. Scenery is enabled explicitly and stays separate from the tracked character.',st['body'])]
 doc=GuideDoc(str(path),pagesize=A4,leftMargin=43,rightMargin=43,topMargin=53,bottomMargin=52,title=title+' - Step-by-step user guide',author='Sakura',pageCompression=1)
 doc.build(story,onFirstPage=lambda c,d:chrome(c,d,title,accent),onLaterPages=lambda c,d:chrome(c,d,title,accent))
 pages=PdfReader(path).pages
 text='\n'.join(p.extract_text() for p in pages)
 for c in chapters:assert c['title'][:8] in text,(kind,c['title'])
 print(path.name,len(pages),'pages; chapter boundaries verified')
archive=PARENT/'Guide Archive'/'2026-10-24'
archive.mkdir(parents=True,exist_ok=True)
for ext in ['html','pdf']:
 p=PARENT/('Sakura_User_Guide.'+ext)
 if p.exists() and not (archive/p.name).exists():shutil.copy2(p,archive/p.name)
for kind in META:
 chapters=parse(ROOT/f'docs/user-guides/{kind}.md');assert len(chapters)==(17 if kind=='companion' else 15)
 base='Sakura_'+('Companion' if kind=='companion' else 'VTuber')+'_Guide'
 pdf_guide(kind,chapters,OUT/(base+'.pdf'))
 content=html_guide(kind,chapters)
 (ROOT/'docs/user-guides'/(base+'.html')).write_text(content.replace('href="'+base+'.pdf"','href="../../output/pdf/'+base+'.pdf"'),encoding='utf-8')
 (PARENT/(base+'.html')).write_text(content,encoding='utf-8')
 shutil.copy2(OUT/(base+'.pdf'),PARENT/(base+'.pdf'))
hub=f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Sakura - Choose your guide</title><style>:root{{--accent:#b83571}}{CSS}</style></head><body><header><span class="tag">SAKURA / GUIDES</span><h1>Choose your edition</h1><p>Two separate step-by-step guides, updated {DATE}. The older combined guide has been replaced.</p></header><div class="layout" style="display:block;max-width:900px"><article><h2>Sakura Companion</h2><p>Conversation, voice, local/cloud AI, model downloads, Game Mode, Google, Agent approvals and phone setup.</p><a class="download" href="Sakura_Companion_Guide.html">Read Companion guide</a><a class="download secondary" href="Sakura_Companion_Guide.pdf">Companion PDF</a></article><article><h2>Sakura VTuber</h2><p>Webcam/mobile tracking, hands, NVIDIA setup, expressions, materials, streaming output, Collab and Chat Reader.</p><a class="download" href="Sakura_VTuber_Guide.html">Read VTuber guide</a><a class="download secondary" href="Sakura_VTuber_Guide.pdf">VTuber PDF</a></article></div></body></html>'''
(PARENT/'Sakura_User_Guide.html').write_text(hub,encoding='utf-8')
(ROOT/'docs/user-guides/Sakura_User_Guide.html').write_text(hub.replace('href="Sakura_Companion_Guide.pdf"','href="../../output/pdf/Sakura_Companion_Guide.pdf"').replace('href="Sakura_VTuber_Guide.pdf"','href="../../output/pdf/Sakura_VTuber_Guide.pdf"'),encoding='utf-8')
st=styles(colors.HexColor('#b83571'));story=[para('SAKURA / GUIDES',st['eyebrow']),para('Choose your edition',st['cover']),para('The previous combined guide is now two separate step-by-step guides. Updated '+DATE+'.',st['goal'])]
for name,desc in [('Companion','AI conversation, voices, local/cloud models, Agent tasks, Google and Game Mode.'),('VTuber','Face/hand tracking, phone camera, optional NVIDIA inputs, expressions and streaming.')]:
 story +=[Spacer(1,18),para('Sakura '+name,st['title']),para(desc,st['body']),para('Open the matching file in this same folder:',st['note']),Paragraph(f'<b>Sakura_{name}_Guide.pdf</b>',st['body']),Paragraph(f'<link href="Sakura_{name}_Guide.html" color="#b83571">Open the offline HTML guide</link>',st['body'])]
story +=[Spacer(1,20),para('For the clickable guide chooser, open Sakura_User_Guide.html. The previous combined files are preserved under Guide Archive / 2026-10-24.',st['note'])]
p=OUT/'Sakura_User_Guide.pdf';doc=SimpleDocTemplate(str(p),pagesize=A4,leftMargin=43,rightMargin=43,topMargin=53,bottomMargin=52,title='Sakura - Choose your guide');doc.build(story,onFirstPage=lambda c,d:chrome(c,d,'Sakura guides',colors.HexColor('#b83571')));shutil.copy2(p,PARENT/p.name)
print('Original guide replaced with chooser; previous guide archived; source Markdown and offline HTML saved.')
