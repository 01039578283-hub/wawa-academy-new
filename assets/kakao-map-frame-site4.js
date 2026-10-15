/* Keep Kakao attribution and map controls; remove outbound actions inside this map frame. */
(()=>{'use strict';
 const root=document.querySelector('.root_daum_roughmap');if(!root)return;
 function clean(){
  root.querySelectorAll('.wrap_btn_roadview,.cont').forEach(n=>n.remove());
  root.querySelectorAll('a').forEach(a=>{
   a.removeAttribute('href');a.removeAttribute('target');a.removeAttribute('onclick');
   a.removeAttribute('title');a.tabIndex=-1;
   a.querySelectorAll('img[alt]').forEach(img=>{if(/이동|새창/.test(img.alt))img.alt='Kakao 지도';});
  });
  if(root.querySelector('.map')&&!document.documentElement.dataset.mapReady){
   document.documentElement.dataset.mapReady='true';
   parent.postMessage({type:'wawa-kakao-map-ready',id:root.id.replace('daumRoughmapContainer','')},location.origin);
  }
 }
 let pending=false;
 const observer=new MutationObserver(records=>{
  if(pending||!records.some(r=>[...r.addedNodes].some(n=>n.nodeType===1&&(n.matches('a,.cont,.wrap_btn_roadview')||n.querySelector('a,.cont,.wrap_btn_roadview')))))return;
  pending=true;requestAnimationFrame(()=>{pending=false;clean();});
 });observer.observe(root,{childList:true,subtree:true});clean();
 for(const type of ['click','auxclick'])document.addEventListener(type,e=>{if(e.target.closest('a')){e.preventDefault();e.stopImmediatePropagation();}},true);
 document.addEventListener('keydown',e=>{if((e.key==='Enter'||e.key===' ')&&e.target.closest('a')){e.preventDefault();e.stopImmediatePropagation();}},true);
 let width=document.documentElement.clientWidth;
 window.addEventListener('resize',()=>{
  const next=document.documentElement.clientWidth;
  if(next===width)return;width=next;
  if(window.wawaMap?.jsMap){const center=window.wawaMap.jsMap.getCenter();window.wawaMap.jsMap.relayout();window.wawaMap.jsMap.setCenter(center);}
 },{passive:true});
})();
