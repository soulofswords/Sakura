"""Explicit avatar changes resolve installed artwork, never invented costumes."""
import re
from pathlib import Path

REQUEST=re.compile(r'^\s*(?:(?:please|sakura)[, ]+|(?:can|could|would) you\s+|let[’\']?s\s+)*(?:change|switch|swap)(?:\s+(?:your|the|my))?\s+(?:costume|outfit|avatar|model)(?:\s+(?:to|into))?\s+(?P<name>.+?)\s*[.!?]*$',re.I)
SHORT_REQUEST=re.compile(r"^\s*(?:(?:yes|yea|yeah|okay|ok|please|sakura)[, .!]*\s*|let[’']?s\s+)*(?:change|switch|swap)(?:\s+(?:your|the|my))?(?:\s+(?:costume|outfit|avatar|model))?(?:\s+(?:to|into))?\s*(?P<name>.*?)\s*[.!?]*$",re.I)
LIBRARY_REQUEST=re.compile(r'\b(?:show|list|browse|what|which)\b.*\b(?:models|outfits|costumes|avatars|model library)\b',re.I)


def inventory(root):
    root=Path(root).resolve();entries=[]
    for count,file in enumerate(root.rglob('*')):
        if count>=20000:break
        if not file.is_file() or file.suffix.casefold() not in ('.pmx','.vrm') and not file.name.casefold().endswith('.model3.json'):continue
        relative=file.relative_to(root)
        if any(part in {'Stages','Tools & Props'} or part.startswith('.') for part in relative.parts):continue
        if not file.resolve().is_relative_to(root):continue
        entries.append((relative.as_posix(),file.name.removesuffix('.model3.json') if file.name.endswith('.model3.json') else file.stem))
    return entries


def request(text, root):
    listing=LIBRARY_REQUEST.search(str(text))
    match=REQUEST.fullmatch(str(text))
    if not match:
        short=SHORT_REQUEST.fullmatch(str(text))
        if short and (short['name'].strip(' .!?').casefold() in {'it','that','again','one',''} or re.search(r'\b(?:elegant|traditional|casual|formal|dress|costume|outfit|avatar|model)\b',short['name'],re.I)):
            match=short
    if listing:
        entries=inventory(root)
        cloud=bool(re.search(r'\bcloud\b',str(text),re.I))
        return {'reply':('Opening the cloud model library. Sign in if needed; these models must be downloaded before I can wear them.' if cloud else 'Installed characters include: '+(', '.join(name for _,name in entries[:20]) or 'none yet')+'. Choose an actual model in Models; cloud imports are listed separately.'),'avatar_picker':True,'avatar_query':'','avatar_cloud':cloud}
    if not match:return None
    query=match['name'].strip(' .!?')[:120]
    if query.casefold() in {'it','that','again','one',''}:
        return {'reply':'Choose the character or outfit in Models. I have not changed it yet.','avatar_picker':True,'avatar_query':''}
    cloud=bool(re.search(r'\bcloud\b',query,re.I))
    if cloud:
        return {'reply':'Opening cloud imports to search the published models. Sign in if needed, then choose and download one; I have not changed outfits yet.','avatar_picker':True,'avatar_query':re.sub(r'\b(?:from|the|cloud|library)\b','',query,flags=re.I).strip(),'avatar_cloud':True}
    terms=[word for word in re.findall(r'\w+',query.casefold()) if word not in {'a','an','the','woman','girl','man','boy','model','outfit','costume','chinese'}]
    words=set(terms)
    if not words:return {'reply':'Which installed character or outfit should I use?','avatar_picker':query}
    candidates=[]
    for relative,name in inventory(root):
        tokens=set(re.findall(r'\w+',relative.casefold()))
        if words<=tokens:candidates.append((relative,name))
    if len(candidates)==1:
        if candidates[0][0].endswith('.model3.json'):
            return {'reply':'Choose '+candidates[0][1]+' in the Live2D selector. I have not changed it yet.','avatar_picker':True,'avatar_query':candidates[0][1]}
        return {'reply':'Loading '+candidates[0][1]+'.','avatar_model':candidates[0][0]}
    return {'reply':('I found several matching outfits. Choose one in Models.' if candidates else 'I could not identify one installed outfit from that description. Choose it in Models, or import it first.'),'avatar_picker':' '.join(terms)}
