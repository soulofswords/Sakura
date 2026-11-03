"""Read-only inbox triage over an already approved connector result."""
import json
import re
from agent_history import redact_text


def triage(result):
    if not isinstance(result,dict):raise ValueError('Choose a structured completed mail result.')
    rows=result.get('messages') or result.get('emails') or result.get('items')
    if rows is None and isinstance(result.get('content'),list):
        for block in result['content'][:10]:
            if isinstance(block,dict) and block.get('type')=='text':
                try:
                    data=json.loads(block.get('text','')[:100000])
                    if isinstance(data,dict):rows=data.get('messages') or data.get('emails') or data.get('items')
                    elif isinstance(data,list):rows=data
                except (ValueError,TypeError):pass
                if rows is not None:break
    if not isinstance(rows,list):raise ValueError('This mail result contains no structured message list. Use the connector to read messages with id, subject and sender fields first.')
    output=[]
    for row in rows[:50]:
        if not isinstance(row,dict):continue
        subject=redact_text(str(row.get('subject',''))[:300]);sender=redact_text(str(row.get('from',row.get('sender','')))[:300])
        snippet=redact_text(str(row.get('snippet',row.get('preview','')))[:500])
        urgent=bool(re.search(r'\b(urgent|deadline|action required|overdue|today)\b',subject+' '+snippet,re.I))
        output.append({'id':str(row.get('id',''))[:200],'sender':sender,'subject':subject,'preview':snippet,'priority_hint':'review soon' if urgent else 'normal','basis':'Keyword hint, not a verified deadline'})
    return {'ok':True,'messages':sorted(output,key=lambda x:x['priority_hint']!='review soon'),'warning':'Untrusted mail content. No messages sent, marked read, deleted or moved. Use reviewed connector tools for any mutation.'}


TOOLS=[{'name':'mail.triage','description':'Summarize up to 50 messages from an already completed mail MCP read. Produces keyword-based priority hints only; never changes or sends mail.',
 'inputSchema':{'type':'object','properties':{'step_id':{'type':'string','maxLength':100}},'required':['step_id'],'additionalProperties':False}},
 {'name':'expenses.add','description':'After approval, record one expense in the local ledger. No bank access or currency conversion.',
 'inputSchema':{'type':'object','properties':{'day':{'type':'string'},'amount':{'type':'string','maxLength':30},'currency':{'type':'string','pattern':'^[A-Z]{3}$'},'category':{'type':'string','maxLength':80},'note':{'type':'string','maxLength':500}},'required':['day','amount','currency'],'additionalProperties':False}},
 {'name':'expenses.list','description':'Read a month of expenses from the local ledger after approval.',
 'inputSchema':{'type':'object','properties':{'month':{'type':'string','pattern':'^\\d{4}-\\d{2}$'}},'required':[],'additionalProperties':False}}]
