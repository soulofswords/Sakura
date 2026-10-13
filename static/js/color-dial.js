export function installColorDial(input,host) {
    let hue=0,saturation=0,value=1,dragging=null;
    const canvas=document.createElement('canvas');canvas.width=canvas.height=240;canvas.className='model-color-dial';canvas.setAttribute('aria-label','Hue ring and saturation brightness square');
    const rgb=document.createElement('div');rgb.className='model-color-rgb';
    const fields=['R','G','B'].map(name=>{const label=document.createElement('label');label.textContent=name;const field=document.createElement('input');field.type='number';field.min=0;field.max=255;label.append(field);rgb.append(label);return field;});
    host.append(canvas,rgb);
    function fromHSV(h,s,v){const c=v*s,x=c*(1-Math.abs((h/60)%2-1)),m=v-c;const triple=h<60?[c,x,0]:h<120?[x,c,0]:h<180?[0,c,x]:h<240?[0,x,c]:h<300?[x,0,c]:[c,0,x];return triple.map(n=>Math.round((n+m)*255));}
    const hex=values=>'#'+values.map(n=>n.toString(16).padStart(2,'0')).join('');
    function draw(){
        const ctx=canvas.getContext('2d');ctx.clearRect(0,0,240,240);
        for(let angle=0;angle<360;angle++){ctx.beginPath();ctx.arc(120,120,104,(angle-91)*Math.PI/180,(angle-89)*Math.PI/180);ctx.strokeStyle=`hsl(${angle},100%,50%)`;ctx.lineWidth=20;ctx.stroke();}
        ctx.fillStyle=`hsl(${hue},100%,50%)`;ctx.fillRect(58,58,124,124);
        let gradient=ctx.createLinearGradient(58,0,182,0);gradient.addColorStop(0,'white');gradient.addColorStop(1,'transparent');ctx.fillStyle=gradient;ctx.fillRect(58,58,124,124);
        gradient=ctx.createLinearGradient(0,58,0,182);gradient.addColorStop(0,'transparent');gradient.addColorStop(1,'black');ctx.fillStyle=gradient;ctx.fillRect(58,58,124,124);
        for(const [x,y]of [[120+104*Math.cos((hue-90)*Math.PI/180),120+104*Math.sin((hue-90)*Math.PI/180)],[58+saturation*124,58+(1-value)*124]]){ctx.beginPath();ctx.arc(x,y,6,0,Math.PI*2);ctx.strokeStyle='#fff';ctx.lineWidth=2;ctx.stroke();ctx.strokeStyle='#111';ctx.lineWidth=1;ctx.stroke();}
        const channels=fromHSV(hue,saturation,value);input.value=hex(channels);channels.forEach((n,i)=>fields[i].value=n);
    }
    function sync(){const channels=input.value.slice(1).match(/../g).map(n=>parseInt(n,16)/255),max=Math.max(...channels),min=Math.min(...channels),difference=max-min;value=max;saturation=max?difference/max:0;if(difference){const i=channels.indexOf(max);hue=((i===0?(channels[1]-channels[2])/difference:i===1?2+(channels[2]-channels[0])/difference:4+(channels[0]-channels[1])/difference)*60+360)%360;}draw();}
    function move(event){if(!dragging)return;const rect=canvas.getBoundingClientRect(),x=(event.clientX-rect.left)*240/rect.width,y=(event.clientY-rect.top)*240/rect.height;
        if(dragging==='hue')hue=(Math.atan2(y-120,x-120)*180/Math.PI+450)%360;
        else{saturation=Math.max(0,Math.min(1,(x-58)/124));value=1-Math.max(0,Math.min(1,(y-58)/124));}draw();
    }
    canvas.onpointerdown=event=>{const rect=canvas.getBoundingClientRect(),x=(event.clientX-rect.left)*240/rect.width,y=(event.clientY-rect.top)*240/rect.height;const distance=Math.hypot(x-120,y-120);dragging=distance>=91&&distance<=116?'hue':x>=58&&x<=182&&y>=58&&y<=182?'square':null;if(dragging){canvas.setPointerCapture(event.pointerId);move(event);}};
    canvas.onpointermove=move;canvas.onpointerup=canvas.onpointercancel=()=>dragging=null;
    fields.forEach(field=>field.oninput=()=>{input.value=hex(fields.map(f=>Math.max(0,Math.min(255,Number(f.value)||0))));sync();});
    input.addEventListener('input',sync);sync();return {sync};
}
