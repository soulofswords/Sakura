"""Bounded SKILL.md metadata importer. Imported text is guidance, never code."""
import hashlib
import json
import re

FIELD_MAPPING={'name':'name','title':'name','description':'description',
               'allowed-tools':'required_tools','tools':'required_tools','required_tools':'required_tools',
               'dependencies':'dependencies','requires-skills':'dependencies'}
TOOL_MAPPING={'Read':'files.read','Write':'files.text.create','Edit':'files.text.edit',
              'Bash':'shell.run','Shell':'shell.run','WebSearch':'web.search','WebFetch':'web.fetch',
              'read_file':'files.read','write_file':'files.text.create','web_search':'web.search'}


def parse_skill(text,source):
    if not isinstance(text,str) or not 10<=len(text)<=24000:raise ValueError('Import a SKILL.md of 10–24,000 characters.')
    if not isinstance(source,str) or len(source)>250 or '\n' in source:raise ValueError('Invalid skill source label.')
    text=text.lstrip('\ufeff').replace('\r\n','\n');metadata={};body=text
    if text.startswith('---\n'):
        end=text.find('\n---\n',4)
        if end<0:raise ValueError('Close skill frontmatter with --- on its own line.')
        for line in text[4:end].splitlines():
            if not line.strip() or line.lstrip().startswith('#'):continue
            if ':' not in line or line[:1].isspace():raise ValueError('Use simple one-line SKILL.md frontmatter; nested YAML is not supported.')
            key,value=line.split(':',1);canonical=FIELD_MAPPING.get(key.strip())
            if canonical is None:continue
            if canonical in metadata:raise ValueError('Duplicate skill metadata field: '+canonical)
            value=value.strip()
            if canonical in ('required_tools','dependencies'):
                if value.startswith('['):
                    try:value=json.loads(value.replace("'",'"'))
                    except ValueError:raise ValueError('Use a JSON list or comma-separated tool/skill names.') from None
                else:value=[v for v in re.split(r'[,\s]+',value) if v]
                if not isinstance(value,list) or len(value)>30 or any(not isinstance(v,str) or not re.fullmatch(r'[A-Za-z0-9_.:-]{1,120}',v) for v in value):raise ValueError('Invalid tool or dependency list.')
            else:value=value.strip('"\'')
            metadata[canonical]=value
        body=text[end+5:].strip()
    name=metadata.get('name')
    if not isinstance(name,str) or not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,59}',name):raise ValueError('Skill frontmatter needs a lowercase hyphenated name (up to 60 characters).')
    if not 10<=len(body)<=4000:raise ValueError('The skill procedure must contain 10–4,000 characters.')
    if re.search(r'(?i)(?:sk-[a-z0-9]{16,}|Bearer\s+\S+|(?:api[_ -]?key|password|access[_ -]?token)\s*[:=]\s*\S+)',body):raise ValueError('Remove credentials from the imported skill.')
    description=metadata.get('description','')
    if not isinstance(description,str) or len(description)>600:raise ValueError('Skill description allows up to 600 characters.')
    return {'name':name,'description':description,'instructions':body,
            'required_tools':[TOOL_MAPPING.get(t,t) for t in metadata.get('required_tools',[])],
            'dependencies':metadata.get('dependencies',[]),'source':'imported SKILL.md',
            'provenance':{'label':source,'sha256':hashlib.sha256(text.encode()).hexdigest()},
            'script_execution':False}
