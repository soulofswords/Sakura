export function installBackupControls(){
 const host=document.getElementById('tab-general');if(!host)return;
 const box=document.createElement('fieldset');box.className='setting-group';box.innerHTML='<legend>Encrypted local backup</legend><p>Export characters and saved memories with AES-256-GCM password encryption. API keys, Google/Jio sessions and browser cookies are excluded. Restoration creates a new folder and never overwrites your current installation.</p><label>Backup password (at least 12 characters)<input type="password" autocomplete="new-password" minlength="12" maxlength="1024"></label><div class="studio-actions"><button type="button" data-backup="create">Create backup</button><button type="button" data-backup="restore">Restore to folder</button></div><p role="status">Keep the password safe. It cannot be recovered.</p>';
 host.append(box);const password=box.querySelector('input'),status=box.querySelector('[role=status]');
 for(const button of box.querySelectorAll('button'))button.onclick=async()=>{
  if(password.value.length<12){status.textContent='Use at least 12 characters.';return;}
  const api=window.pywebview?.api;if(!api?.encrypted_backup){status.textContent='Open the installed desktop app to choose backup files.';return;}
  const secret=password.value;password.value='';box.querySelectorAll('button').forEach(b=>b.disabled=true);status.textContent='Working locally. Large character libraries can take several minutes…';
  try{const result=await api.encrypted_backup(button.dataset.backup,secret);status.textContent=result.cancelled?'Cancelled.':(result.message||'Encrypted backup saved.')+' '+(result.path||'');}
  catch(error){status.textContent=error.message||'Backup failed. Check the password and free disk space.';}
  finally{box.querySelectorAll('button').forEach(b=>b.disabled=false);}
 };
}
