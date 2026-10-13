"""Bounded single-image vision context for local multimodal runtimes."""
import base64
from io import BytesIO
from PIL import Image, ImageDraw

def combine_screen_avatar(screen,avatar):
    views=[]
    for encoded in (screen,avatar):
        with Image.open(BytesIO(base64.b64decode(encoded,validate=True))) as image:
            view=image.convert('RGB');view.thumbnail((800,800));views.append(view)
    width=sum(v.width for v in views)+24
    result=Image.new('RGB',(width,max(v.height for v in views)+32),'#202830')
    draw=ImageDraw.Draw(result);x=0
    for label,view in zip(('SCREEN','YOUR AVATAR'),views):
        draw.text((x+8,8),label,fill='white');result.paste(view,(x,32));x+=view.width+24
    output=BytesIO();result.save(output,format='JPEG',quality=85)
    return base64.b64encode(output.getvalue()).decode('ascii')
