(() => {
  const form=document.getElementById('drawForm');if(!form)return;
  const fields=[...form.querySelectorAll('input[name="slots"]')], choices=[...form.querySelectorAll('.country-choice')];
  const names=new Map(choices.map(b=>[b.dataset.code,b.dataset.name]));
  const summary=document.getElementById('drawSummary'), apply=document.getElementById('applyDraw'), preview=document.getElementById('pairPreview');
  let order=fields.map(f=>f.value).filter(Boolean),dirty=false;
  function render(){
    fields.forEach((f,i)=>f.value=order[i]||'');
    summary.textContent=`เลือกแล้ว ${order.length}/${fields.length} ทีม${dirty?' · ยังไม่บันทึก':''}`;
    if(apply)apply.disabled=order.length!==fields.length;
    choices.forEach(b=>{const i=order.indexOf(b.dataset.code);b.classList.toggle('selected',i>=0);b.setAttribute('aria-pressed',String(i>=0));b.querySelector('[data-used]').textContent=i>=0?String(i+1):'–'});
    preview.replaceChildren();
    for(let i=0;i<order.length;i+=2){const item=document.createElement('li');item.textContent=`${names.get(order[i])} พบ ${names.get(order[i+1])||'รอเลือกทีม'}`;preview.appendChild(item)}
  }
  choices.forEach(b=>b.addEventListener('click',()=>{
    if(!window.kkuCanEdit)return;
    const i=order.indexOf(b.dataset.code);
    if(i>=0)order.splice(i,1);else order.push(b.dataset.code);
    dirty=true;render();
  }));
  form.querySelector('[name="rounds"]').addEventListener('input',()=>{dirty=true;render()});
  document.getElementById('countrySearch').addEventListener('input',e=>{const q=e.target.value.trim().toLowerCase();choices.forEach(b=>b.hidden=!(b.dataset.name+' '+b.dataset.code).toLowerCase().includes(q))});
  form.addEventListener('submit',()=>{dirty=false});window.addEventListener('beforeunload',e=>{if(dirty){e.preventDefault();e.returnValue=''}});
  render();
})();
