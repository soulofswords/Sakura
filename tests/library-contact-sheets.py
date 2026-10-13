import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
root=Path('audit-results/full-library-2026-10-09')
parts=list(root.glob('part*/results.json'))
items=[]
final=root/'final-results.json'
for file in ([final] if final.exists() else parts or [root/'results.json']):
    folder=file.parent.relative_to(root)
    for r in json.loads(file.read_text(encoding='utf-8')):
        if r.get('preview'):
            if file != final:
                r['preview']=str(folder/'previews'/r['preview'])
            items.append(r)
items.sort(key=lambda item:item['index'])
font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',12)
out=root/'sheets'
out.mkdir(exist_ok=True)
for start in range(0,len(items),30):
    batch=items[start:start+30]
    target=out/f'{start//30:02d}.jpg'
    sheet=Image.new('RGB',(960,1320),'#20242a')
    draw=ImageDraw.Draw(sheet)
    for j,item in enumerate(batch):
        image=Image.open(root/item['preview']).convert('RGB')
        image.thumbnail((160,220))
        x=(j%6)*160;y=(j//6)*264
        sheet.paste(image,(x,y))
        draw.text((x+2,y+221),f"#{item['index']} {Path(item['path']).stem[:20]}",font=font,fill='white')
        draw.text((x+2,y+237),'/'.join(item['path'].split('/')[1:3])[:23],font=font,fill='white')
    sheet.save(target,quality=88)
print(f'{len(items)} previews; {len(list(out.glob("*.jpg")))} sheets')
