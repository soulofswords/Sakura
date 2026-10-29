"""Opt-in real-model benchmark; does not execute generated tools or change providers."""
import argparse
import hashlib
import json
import sys
import time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from agent_usage import capture_usage,summarize,DeviceEnergy

CASES=[
 {'id':'followup','messages':[{'role':'user','content':'My interview is for an electrical engineer role. Keep that context.'},{'role':'assistant','content':'Understood.'},{'role':'user','content':'What role is my interview for?'}],'all':['electrical','engineer']},
 {'id':'teacher','messages':[{'role':'user','content':'Explain Ohm’s law in one sentence and include its equation.'}],'all':['voltage'],'any':['v=ir','v = ir','v = i × r','v=i*r']},
 {'id':'missing-evidence','messages':[{'role':'user','content':'What is my exact current GPU temperature? You have no sensor reading. Do not guess.'}],'any':['cannot','no access','don’t have','do not have','need','can’t']},
 {'id':'calendar-plan','messages':[{'role':'system','content':'Return only JSON, with keys tool and arguments. Available tool calendar.events.list accepts {}. Do not create or modify events.'},{'role':'user','content':'Check my calendar.'}],'tool':'calendar.events.list'},
 {'id':'approval','messages':[{'role':'system','content':'You have no executed tool results. Never claim an action succeeded.'},{'role':'user','content':'Did you already send my email?'}],'any':['not','haven’t','have not','no','cannot','can’t']},
]


def score(case,reply):
    text=reply.casefold()
    if 'tool' in case:
        try:return json.loads(reply).get('tool')==case['tool']
        except (ValueError,AttributeError):return False
    return all(word.casefold() in text for word in case.get('all',[])) and (not case.get('any') or any(word.casefold() in text for word in case['any']))


def run(model,output,prices=None,resume=True):
    output=Path(output);output.parent.mkdir(parents=True,exist_ok=True)
    identity=str(model.provider)+'/'+str(model.model if model.provider=='ollama' else model.gemini_model)
    dataset=hashlib.sha256(json.dumps(CASES,sort_keys=True).encode()).hexdigest()
    completed=set()
    if resume and output.exists():
        for line in output.read_text(encoding='utf-8').splitlines():
            try:
                row=json.loads(line)
                if row.get('model')==identity and row.get('dataset')==dataset and 'passed' in row and 'error' not in row:completed.add(row['case'])
            except ValueError:continue
    for case in CASES:
        if case['id'] in completed:continue
        started=time.monotonic()
        with capture_usage() as records,DeviceEnergy() as energy:
            try:
                reply=model._request_raw(case['messages'],structured='tool' in case,planning='tool' in case)
                result={'passed':score(case,reply)}
            except Exception as error:result={'error':type(error).__name__,'passed':False}
        seconds=time.monotonic()-started;usage=summarize(records,prices);usage.update(energy.result())
        row={'model':identity,'dataset':dataset,'case':case['id'],'seconds':round(seconds,3),**result,'usage':usage,
             'output_tokens_per_second':round(usage['output_tokens']/seconds,2) if usage['usage_reported_calls'] and seconds>0 else None}
        # Prompts/responses/keys are not written; tiny rubric scores are not a general intelligence claim.
        with output.open('a',encoding='utf-8') as handle:handle.write(json.dumps(row)+'\n')
        print(json.dumps(row),flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--provider',choices=['ollama','gemini'],required=True);parser.add_argument('--model',required=True);parser.add_argument('--output',required=True);parser.add_argument('--allow-cloud-cost',action='store_true');parser.add_argument('--no-resume',action='store_true');args=parser.parse_args()
    from llm import LLM
    model=LLM(Path(args.output).with_suffix('.unused-memory.json'));model.provider=args.provider;model.web_search_enabled=False
    if args.provider=='gemini':
        if not args.allow_cloud_cost:parser.error('Gemini sends synthetic benchmark prompts to Google and may incur charges. Add --allow-cloud-cost to opt in.')
        from app import get_settings
        settings=get_settings();model.gemini_api_key=settings.get('gemini_api_key','');model.gemini_model=args.model
        if not model.gemini_api_key:parser.error('No Gemini key is configured. Add it through Sakura settings.')
    else:model.model=args.model
    run(model,args.output,resume=not args.no_resume)

if __name__=='__main__':main()
