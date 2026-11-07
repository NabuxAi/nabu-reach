'use strict';
const $ = id => document.getElementById(id);
const esc = value => String(value == null ? '' : value).replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
async function api(route, opts={}) {
  if(typeof window.reachDemoApi==="function") return window.reachDemoApi(route,opts);
  const response=await fetch(route,opts);
  const data=await response.json();
  if(!response.ok) throw Error(data.error||`HTTP ${response.status}`);
  return data;
}
function toast(message){const x=$('toast');x.textContent=message;x.classList.add('show');clearTimeout(toast.t);toast.t=setTimeout(()=>x.classList.remove('show'),4500);}
function switchTab(tab){
  document.querySelectorAll('[data-panel]').forEach(e=>e.classList.toggle('active',e.dataset.panel===tab));
  document.querySelectorAll('[data-tab]').forEach(e=>e.classList.toggle('active',e.dataset.tab===tab));
  $('currentTab').textContent=tab[0].toUpperCase()+tab.slice(1);location.hash=tab;
  refresh();
  if(tab==="campaigns" && typeof window.reachDemoApi==="function") {
    setTimeout(()=>$("previewBtn").click(),250); // simulated opt-in previews only
  }
}
async function refresh(){
  try{
    const [s,accounts,contacts,drafts]=await Promise.all([api('/api/summary'),api('/api/accounts'),api('/api/contacts'),api('/api/campaigns')]);
    $('metricAccounts').textContent=s.accounts;$('metricConsented').textContent=s.opted_in;$('metricOptouts').textContent=s.opted_out;$('metricDrafts').textContent=s.drafts;
    $('contactsCount').textContent=`(${s.contacts})`;
    $('accountsList').innerHTML=accounts.length?accounts.map(a=>`<div class="list-row"><div><b>${esc(a.label)}</b><small>${esc(a.provider.replaceAll('_',' '))}</small></div><span class="pill ${a.status==='mock_ready'?'green':'warn'}">${a.status==='mock_ready'?'Mock ready':'Setup needed'}</span></div>`).join(''):'<div class="list-empty">No accounts yet. Add a mock account to begin.</div>';
    $('campaignAccount').innerHTML=accounts.length?accounts.map(a=>`<option value="${Number(a.id)}">${esc(a.label)} (${esc(a.provider)})</option>`).join(''):'<option value="">Add an account first</option>';
    $('contactsList').innerHTML=contacts.length?contacts.map(c=>`<div class="list-row"><div><b>${esc(c.name||c.phone)}</b><small>${esc(c.phone)} · ${esc(c.consent_source)}</small></div><span class="pill ${c.consent_status==='opt_in'?'green':'warn'}">${c.consent_status==='opt_in'?'Opted in':'Opted out'}</span></div>`).join(''):'<div class="list-empty">Your consent ledger is empty. Import a CSV to begin.</div>';
    $('draftList').innerHTML=drafts.length?drafts.map(c=>`<div class="list-row"><div><b>${esc(c.name)}</b><small>${esc(c.account_label)}</small></div><span class="pill">Draft</span></div>`).join(''):'<div class="list-empty">No saved drafts.</div>';
  }catch(e){toast(e.message);}
}
const jsonPost=(url,body)=>api(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
document.querySelectorAll('[data-tab]').forEach(e=>e.addEventListener('click',()=>switchTab(e.dataset.tab)));
document.querySelectorAll('[data-go]').forEach(e=>e.addEventListener('click',()=>switchTab(e.dataset.go)));
$('accountForm').addEventListener('submit',async e=>{e.preventDefault();try{await jsonPost('/api/accounts',{label:$('accountLabel').value,provider:$('accountProvider').value});toast('Account placeholder saved.');$('accountLabel').value='';refresh();}catch(err){toast(err.message)}});
$('optoutForm').addEventListener('submit',async e=>{e.preventDefault();try{await jsonPost('/api/contacts/opt-out',{phone:$('optoutPhone').value});toast('Contact opted out.');$('optoutPhone').value='';refresh();}catch(err){toast(err.message)}});
$('csvFile').addEventListener('change',async e=>{const file=e.target.files[0];if(!file)return;try{const result=await api('/api/contacts/import',{method:'POST',headers:{'Content-Type':'text/csv'},body:await file.arrayBuffer()});$('importResult').hidden=false;$('importResult').textContent=`Imported: ${result.imported} · Skipped: ${result.skipped}`+(result.errors.length?'\n'+result.errors.map(e=>`Row ${e.row}: ${e.reason}`).join('\n'):'');refresh();}catch(err){toast(err.message)}finally{e.target.value=''}});
$('previewBtn').addEventListener('click',async()=>{try{const p=await jsonPost('/api/campaigns/preview',{message:$('campaignMessage').value});const intro=`<p class="muted">${p.eligible} eligible · ${p.within_draft_limit} within preview cap · No messages sent.</p>`;$('previewResults').innerHTML=intro+(p.examples.length?p.examples.map(x=>`<div class="preview-message"><small>${esc(x.phone)}</small>${esc(x.message)}</div>`).join(''):'<p class="muted">No opted-in contacts available.</p>');}catch(err){toast(err.message)}});
$('campaignForm').addEventListener('submit',async e=>{e.preventDefault();try{const accountId=Number($('campaignAccount').value);if(!accountId)throw Error('Add an account first.');await jsonPost('/api/campaigns',{name:$('campaignName').value,account_id:accountId,message:$('campaignMessage').value});toast('Campaign saved as draft. No messages sent.');$('campaignName').value='';refresh();}catch(err){toast(err.message)}});
// Generate a local example download without transmitting any contact data.
const example='phone,name,consent,consent_source,consent_at\n+15550100101,Example Person,yes,demo_signup_form,2026-01-01T12:00:00Z\n';
const sampleURL=URL.createObjectURL(new Blob([example],{type:'text/csv'}));$('sampleInfo').href=sampleURL;
window.addEventListener('hashchange',()=>{const tab=location.hash.slice(1);if(['overview','contacts','accounts','campaigns'].includes(tab))switchTab(tab)});
const initial=location.hash.slice(1);switchTab(['overview','contacts','accounts','campaigns'].includes(initial)?initial:'overview');
