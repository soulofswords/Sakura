export function installChatAttachments({notice}) {
    const button=document.getElementById('attach-chat-btn'),input=document.getElementById('chat-file-input');
    const tray=document.getElementById('chat-attachment-tray');
    let items=[],busy=false;
    function render(){
        tray.replaceChildren();tray.hidden=!items.length&&!busy;
        for(const item of items){
            const chip=document.createElement('button');chip.type='button';chip.className='chat-file-chip';
            chip.textContent=item.name+' ×';chip.title='Remove attachment';
            chip.onclick=()=>{items=items.filter(i=>i.id!==item.id);render();void fetch('/api/chat/attachments/'+encodeURIComponent(item.id),{method:'DELETE'}).catch(()=>{});};
            tray.append(chip);
        }
        if(busy){const status=document.createElement('span');status.textContent='Reading file…';tray.append(status);}
        if(items.length){const hint=document.createElement('small');hint.textContent='Sent to your selected AI when you send a message. Long files may use excerpts.';tray.append(hint);}
        button.disabled=busy;
    }
    button.onclick=()=>input.click();
    input.onchange=async()=>{
        const files=Array.from(input.files||[]);input.value='';
        if(items.length+files.length>3){notice('Attach up to three files at a time.');return;}
        busy=true;render();
        try{
            for(const file of files){
                if(file.size>10*1024*1024)throw Error('Each attachment must be 10 MB or smaller.');
                const form=new FormData();form.append('file',file,file.name);
                const response=await fetch('/api/chat/attachments',{method:'POST',body:form});
                const result=await response.json();if(!response.ok)throw Error(result.error||'The file could not be read.');
                items.push(result);render();
                if(result.archaeology_save)window.dispatchEvent(new CustomEvent('sakura-save-context',{detail:result.archaeology_save}));
            }
        }catch(error){notice(error.message);}
        finally{busy=false;render();}
    };
    return {ids:()=>items.map(item=>item.id),busy:()=>busy,clear:()=>{items=[];render();}};
}
