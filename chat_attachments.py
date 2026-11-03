"""Bounded, temporary chat attachments. Files are read as data, never executed."""
import base64
import io
import re
import time
import uuid
import zipfile
from threading import RLock
from xml.etree import ElementTree

from PIL import Image,ImageOps

MAX_BYTES=10*1024*1024
MAX_TEXT=60000
TEXT_EXTENSIONS={'.txt','.md','.csv','.json','.log','.py','.js','.html','.xml','.yaml','.yml'}
IMAGE_EXTENSIONS={'.png','.jpg','.jpeg','.webp'}


def extract_attachment(filename,data,max_text=MAX_TEXT,allow_unknown_text=False):
    """Turn one attached file into text or an image. max_text=None keeps the whole text, which the
    agent's paged file read needs so it can report a true character count for the file.
    allow_unknown_text also reads names with no known extension; the chat uploader leaves it off so a
    random binary download is still refused by the same message it always showed."""
    if not data or len(data)>MAX_BYTES:raise ValueError('Choose a non-empty file of up to 10 MB.')
    name=re.split(r'[/\\]',filename or 'attachment')[-1]
    name=re.sub(r'[\x00-\x1f]','',name)[:180]
    extension='.'+name.rsplit('.',1)[-1].casefold()
    result={'name':name,'kind':'text','text':'','truncated':False}
    if extension in IMAGE_EXTENSIONS:
        try:
            with Image.open(io.BytesIO(data)) as source:
                if source.width*source.height>25_000_000:raise ValueError('The image is too large. Use an image under 25 megapixels.')
                source=ImageOps.exif_transpose(source).convert('RGBA');source.thumbnail((1536,1536))
                image=Image.new('RGB',source.size,'white');image.paste(source,mask=source.getchannel('A'))
                output=io.BytesIO();image.save(output,'JPEG',quality=80)
        except (OSError,Image.DecompressionBombError) as error:raise ValueError('The image could not be read.') from error
        result.update(kind='image',image=base64.b64encode(output.getvalue()).decode('ascii'))
        return result
    if extension=='.pdf':
        from pypdf import PdfReader
        try:
            reader=PdfReader(io.BytesIO(data))
            if reader.is_encrypted and not reader.decrypt(''):raise ValueError('Unlock the PDF before attaching it.')
            parts=[];length=0
            for page in reader.pages[:150]:
                part=page.extract_text() or '';parts.append(part);length+=len(part)
                if max_text is not None and length>max_text:break
            text='\n'.join(parts)
            result['truncated']=len(reader.pages)>len(parts)
        except ValueError:raise
        except Exception as error:raise ValueError('The PDF could not be read. Try an unlocked text-based PDF.') from error
    elif extension=='.docx':
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                if len(archive.infolist())>5000 or sum(i.file_size for i in archive.infolist())>40*1024*1024:raise ValueError('The document expands beyond the supported size.')
                xml=archive.read('word/document.xml')
                if len(xml)>8*1024*1024:raise ValueError('The document text is too large.')
                root=ElementTree.fromstring(xml)
                ns={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
                text='\n'.join(''.join(p.itertext()) for p in root.findall('.//w:p',ns))
        except (zipfile.BadZipFile,KeyError,ElementTree.ParseError) as error:raise ValueError('The DOCX file could not be read.') from error
    elif extension in TEXT_EXTENSIONS or allow_unknown_text:
        try:text=data.decode('utf-16') if data.startswith((b'\xff\xfe',b'\xfe\xff')) else data.decode('utf-8-sig')
        except UnicodeDecodeError:text=data.decode('cp1252',errors='replace')
        if '\x00' in text:raise ValueError('This appears to be a binary file. Attach a PDF, DOCX, text file or image.')
    else:raise ValueError('Supported: PDF, DOCX, text, Markdown, CSV, JSON, code, PNG, JPEG and WebP.')
    if not text.strip():raise ValueError('No readable text was found. For a scanned PDF, attach its page as an image.')
    result.update(text=text if max_text is None else text[:max_text],
                  truncated=result['truncated'] or (max_text is not None and len(text)>max_text))
    return result


class AttachmentStore:
    def __init__(self):self.items={};self.lock=RLock()
    def put(self,item):
        with self.lock:
            self.items={key:value for key,value in self.items.items() if time.monotonic()-value[0]<3600}
            while len(self.items)>=20:self.items.pop(next(iter(self.items)))
            token=uuid.uuid4().hex;self.items[token]=(time.monotonic(),item)
        return {'id':token,'name':item['name'],'kind':item['kind'],'characters':len(item.get('text','')),'truncated':item['truncated']}
    def get(self,tokens):
        if not isinstance(tokens,list) or len(tokens)>3 or any(not isinstance(t,str) for t in tokens):raise ValueError('Attach up to three files per message.')
        with self.lock:
            values=[self.items.get(token) for token in tokens]
        if any(not value or time.monotonic()-value[0]>=3600 for value in values):raise ValueError('An attachment expired. Please attach it again.')
        return [dict(value[1]) for value in values]
    def remove(self,token):
        with self.lock:self.items.pop(token,None)
    def clear(self):
        with self.lock:self.items.clear()


attachments=AttachmentStore()
