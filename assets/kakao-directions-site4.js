/* The map loads automatically near the viewport; existing page images are untouched. */
(()=>{'use strict';
 const frames=[...document.querySelectorAll('iframe[data-kakao-src]')];
 function load(frame){
  if(!frame.dataset.kakaoSrc||frame.dataset.kakaoLoaded)return;
  const url=new URL(frame.dataset.kakaoSrc,location.href);
  if(url.origin!==location.origin||!/^\/assets\/kakao-maps\/\d+\.html$/.test(url.pathname))return;
  const shell=frame.closest('.kd-map-shell');shell?.removeAttribute('data-map-ready');
  if(shell)shell.querySelector('.kd-map-status').textContent='지도 위치를 자동으로 불러옵니다.';
  // Vercel cleanUrls + trailingSlash serves the HTML map resource at this URL.
  frame.src=url.pathname.replace(/\.html$/,'/');frame.dataset.kakaoLoaded='true';
  shell?.setAttribute('data-map-started','true');
  const expected=frame.dataset.kakaoSrc;
  setTimeout(()=>{if(frame.dataset.kakaoSrc===expected&&!shell?.hasAttribute('data-map-ready')&&shell){shell.querySelector('.kd-map-status').textContent='카카오맵 연결이 지연되고 있습니다. 주소와 주변 교통 안내를 확인해 주세요.';}},10000);
 }
 window.addEventListener('message',event=>{
  if(event.origin!==location.origin||event.data?.type!=='wawa-kakao-map-ready')return;
  const frame=frames.find(f=>f.contentWindow===event.source&&f.dataset.kakaoSrc==='/assets/kakao-maps/'+event.data.id+'.html');
  frame?.closest('.kd-map-shell')?.setAttribute('data-map-ready','true');
 });
 if('IntersectionObserver' in window){
  const observer=new IntersectionObserver(entries=>{for(const entry of entries){if(entry.isIntersecting&&!entry.target.hidden){load(entry.target);observer.unobserve(entry.target);}}},{rootMargin:'450px 0px'});
  for(const frame of frames)if(frame.dataset.kakaoSrc)observer.observe(frame);
 }else{for(const frame of frames)load(frame);}
 for(const select of document.querySelectorAll('[data-kakao-hub-select]')){
  select.addEventListener('change',()=>{
   const section=select.closest('.kakao-directions'),option=select.selectedOptions[0];
   const shell=section.querySelector('.kd-map-shell'),frame=shell.querySelector('iframe');
   const address=section.querySelector('.kd-hub-address'),link=section.querySelector('.kd-hub-link');
   if(!option?.value){shell.hidden=true;address.hidden=true;link.hidden=true;frame.removeAttribute('src');delete frame.dataset.kakaoLoaded;return;}
   shell.hidden=false;frame.title=option.textContent+' 위치 지도';
   frame.dataset.kakaoSrc=option.value;delete frame.dataset.kakaoLoaded;load(frame);
   address.hidden=false;address.querySelector('dd').textContent=option.dataset.address||'';
   const target=new URL(option.dataset.branch,location.href);
   if(target.origin===location.origin&&target.pathname.startsWith('/%EC%A7%80%EC%A0%90%EC%95%88%EB%82%B4/')){link.href=target.pathname+'#kakao-directions';link.textContent=option.textContent+' 지점 정보와 주변 교통 안내';link.hidden=false;}
   section.querySelector('.kd-hub-status').textContent=option.textContent+'의 위치를 표시합니다.';
  });
 }
})();
