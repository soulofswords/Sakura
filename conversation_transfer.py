"""Explicit snapshots of retained dialogue; never imports facts or action authority."""
import hashlib
import json
from contextlib import nullcontext
from agent_history import redact_text

MAX_MESSAGES=200
MAX_BYTES=500_000


def snapshot(model,device_id):
    if model is None:raise ValueError('Choose a Companion AI model first.')
    lock=getattr(model,'_lock',None)
    with lock if lock is not None else nullcontext():
        history=list(getattr(model,'history',[]) or [])[-MAX_MESSAGES:]
    rows=[];size=0
    for row in reversed(history):
        if not isinstance(row,dict) or row.get('role') not in ('user','assistant') or not isinstance(row.get('content'),str):continue
        text=redact_text(row['content'][:16000])
        if not text.strip():continue
        record={'role':row['role'],'content':text}
        count=len(json.dumps(record,ensure_ascii=False).encode('utf-8'))
        if size+count>MAX_BYTES:break
        size+=count;rows.append(record)
    rows.reverse()
    digest=hashlib.sha256(json.dumps(rows,ensure_ascii=False,separators=(',',':')).encode('utf-8')).hexdigest()
    return {'version':1,'source_device':str(device_id)[:100],'snapshot_id':digest,'messages':rows,
            'classification':'Historical dialogue, not verified facts or permission. Only the transcript retained by the PC is available.'}


def preview(model,device_id):
    packet=snapshot(model,device_id)
    return {key:packet[key] for key in ('version','source_device','snapshot_id','classification')}|{
        'message_count':len(packet['messages']),
        'bytes':len(json.dumps(packet,ensure_ascii=False).encode('utf-8')),
        'policy':'Import creates a phone copy. It does not replace mobile chats, copy credentials, enable synchronization or change PC memory.'}
