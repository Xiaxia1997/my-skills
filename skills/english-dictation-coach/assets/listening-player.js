/* Copy beside the generated HTML. Before this file, define window.LISTENING_PLAYER_CONFIG:
 * { audioSelector:'#practiceAudio', paragraphTimings:[[0,10]],
 *   sentenceTimings:[[[0,4],[4,10]]], sectionParagraphIndexes:[[0]] }
 */
(() => {
  try {
  const cfg = window.LISTENING_PLAYER_CONFIG;
  if (!cfg) throw new Error('Missing LISTENING_PLAYER_CONFIG');
  const audio = document.querySelector(cfg.audioSelector || '#practiceAudio');
  const paragraphs = [...document.querySelectorAll(cfg.paragraphSelector || 'section.text > p')];
  const sections = [...document.querySelectorAll(cfg.sectionSelector || 'section.text')];
  if (!audio || paragraphs.length !== cfg.paragraphTimings.length || paragraphs.length !== cfg.sentenceTimings.length) {
    throw new Error('Listening player config does not match the page paragraphs or audio element');
  }
  const groups = cfg.sectionParagraphIndexes || sections.map(section => [...section.children]
    .filter(node => node.matches('p')).map(node => paragraphs.indexOf(node)));
  const paragraphToSection = new Map();
  groups.forEach((items, sectionIndex) => items.forEach(paragraphIndex => paragraphToSection.set(paragraphIndex, sectionIndex)));
  const sectionTimes = groups.map(items => [cfg.paragraphTimings[items[0]][0], cfg.paragraphTimings[items.at(-1)][1]]);
  const sentenceRefs = groups.map(items => items.flatMap(paragraphIndex => cfg.sentenceTimings[paragraphIndex]
    .map(([start, end], sentenceIndex) => ({ paragraphIndex, sentenceIndex, start, end }))));

  const style = document.createElement('style');
  style.textContent = `.sentence{cursor:pointer;border-radius:3px}.sentence.playing{background:rgba(43,94,158,.14);box-shadow:0 0 0 2px rgba(43,94,158,.14)}
  .section-launch,.section-transcript{margin:-.2rem .35rem 1rem 0;padding:.38rem .65rem;border:1px solid #c8c3b5;border-radius:5px;background:transparent;color:#2b5e9e;font:600 .78rem sans-serif;cursor:pointer}.section-transcript.active{background:rgba(43,94,158,.08)}
  .audio-dock{position:fixed;z-index:200;left:50%;bottom:max(.7rem,env(safe-area-inset-bottom));transform:translateX(-50%);width:min(720px,calc(100% - 1.4rem));padding:.65rem .75rem;background:rgba(250,249,246,.97);border:1px solid #c8c3b5;border-radius:10px;box-shadow:0 8px 28px rgba(43,38,31,.2)}.audio-dock[hidden]{display:none}.dock-head,.dock-transport{display:flex;align-items:center;gap:.35rem;flex-wrap:wrap}.dock-context{font-size:.75rem;font-weight:600}.dock-close{margin-left:auto;border:0;background:transparent;font-size:1.1rem;cursor:pointer}.dock-timeline{position:relative;height:1.25rem;margin:.25rem 0}.dock-progress{position:absolute;top:.4rem;width:100%;accent-color:#2b5e9e}.dock-nodes{position:absolute;inset:0;pointer-events:none}.dock-node{position:absolute;top:.18rem;width:4px;height:10px;transform:translateX(-50%);border:0;border-radius:2px;background:#9b978b;pointer-events:auto;cursor:pointer}.dock-node.active{top:0;height:14px;background:#2b5e9e}.dock-transport button,.dock-rate{padding:.3rem .45rem;border:1px solid #c8c3b5;border-radius:4px;background:transparent;color:#2b5e9e;cursor:pointer}.dock-time{margin-left:auto;font:12px monospace}body.audio-dock-open{padding-bottom:8.5rem}section.text.transcript-mode .fix s,section.text.transcript-mode del{display:none}section.text.transcript-mode .fix em,section.text.transcript-mode ins{color:inherit;font-weight:inherit;margin-left:0}`;
  // Use one coordinate system: both markers and the native thumb travel from 7px to width - 7px.
  style.textContent += `.dock-timeline{height:28px;--thumb-size:14px}.dock-progress{appearance:none;-webkit-appearance:none;display:block;position:absolute;left:0;top:10px;height:18px;width:100%;margin:0;padding:0;border:0;background:transparent;cursor:pointer}.dock-progress::-webkit-slider-runnable-track{height:4px;border-radius:2px;background:linear-gradient(to right,#2b5e9e var(--progress,0%),#d6d3ca var(--progress,0%))}.dock-progress::-webkit-slider-thumb{appearance:none;-webkit-appearance:none;width:14px;height:14px;margin-top:-5px;border:0;border-radius:50%;background:#2b5e9e}.dock-progress::-moz-range-track{height:4px;border-radius:2px;background:#d6d3ca}.dock-progress::-moz-range-progress{height:4px;background:#2b5e9e}.dock-progress::-moz-range-thumb{width:14px;height:14px;border:0;border-radius:50%;background:#2b5e9e}.dock-nodes{inset:0 7px 0}.dock-node,.dock-node.active{top:19px;width:14px;height:14px;margin:0;padding:0;border:0;transform:translate(-50%,-50%);background:transparent}.dock-node::after{content:'';position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);margin:0;width:6px;height:6px;border-radius:50%;background:#9b978b}.dock-node.active::after{width:8px;height:8px;background:#2b5e9e}.dock-transport button:disabled{opacity:.45;cursor:default}`;
  document.head.append(style);

  const wrapped = paragraphs.map((paragraph, paragraphIndex) => {
    const nodes = [], walker = document.createTreeWalker(paragraph, NodeFilter.SHOW_TEXT, { acceptNode: node => node.parentElement.closest('s,del') ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT });
    let text = ''; while (walker.nextNode()) { const node = walker.currentNode; nodes.push({ node, start:text.length, end:text.length + node.nodeValue.length }); text += node.nodeValue.replace(/\s/g, ' '); }
    const parts = [...new Intl.Segmenter('en',{granularity:'sentence'}).segment(text)].map(part => { const a=part.segment.match(/^\s*/)[0].length,b=part.segment.match(/\s*$/)[0].length; return [part.index+a,part.index+part.segment.length-b]; }).filter(([a,b])=>b>a);
    if (parts.length !== cfg.sentenceTimings[paragraphIndex].length) throw new Error(`Sentence count mismatch in paragraph ${paragraphIndex + 1}`);
    const output = parts.map(()=>[]); nodes.forEach(item => { const fragment=document.createDocumentFragment(); let cursor=0; parts.forEach(([start,end],sentenceIndex)=>{const a=Math.max(item.start,start),b=Math.min(item.end,end);if(a>=b)return;const x=a-item.start,y=b-item.start;if(x>cursor)fragment.append(item.node.nodeValue.slice(cursor,x));const piece=document.createElement('span');piece.className='sentence';piece.dataset.p=paragraphIndex;piece.dataset.s=sentenceIndex;piece.textContent=item.node.nodeValue.slice(x,y);fragment.append(piece);output[sentenceIndex].push(piece);cursor=y;});if(cursor<item.node.nodeValue.length)fragment.append(item.node.nodeValue.slice(cursor));item.node.replaceWith(fragment); });
    return output;
  });

  let activeSection=null, activeSentence=null, stopAt=null, monitor=null, rendered=null;
  let mode='continuous', playRequest=0, scrubbing=false, seekGesture=null;
  const lessonStart=sectionTimes[0][0], lessonEnd=sectionTimes.at(-1)[1];
  const dock=document.createElement('div'); dock.className='audio-dock'; dock.hidden=true; dock.innerHTML=`<div class="dock-head"><span class="dock-context"></span><button class="dock-close" aria-label="关闭播放器">×</button></div><div class="dock-timeline"><input class="dock-progress" type="range" step=".001"><div class="dock-nodes"></div></div><div class="dock-transport"><button class="dock-play" aria-label="播放">▶ 播放</button><button class="dock-replay" disabled>↺ 重听本句</button><select class="dock-rate"><option value=".5">0.5×</option><option value=".75">0.75×</option><option value="1" selected>1×</option><option value="1.25">1.25×</option><option value="1.5">1.5×</option></select><span class="dock-time"></span></div>`; document.body.append(dock);
  const $=selector=>dock.querySelector(selector), launches=[];
  const time=s=>{const tenths=Math.round(Math.max(0,s)*10);return `${Math.floor(tenths/600)}:${String(Math.floor(tenths/10)%60).padStart(2,'0')}.${tenths%10}`;};
  const show=index=>{
    activeSection=index;dock.hidden=false;document.body.classList.add('audio-dock-open');
    if(rendered!==index){
      $('.dock-nodes').replaceChildren();const [a,b]=sectionTimes[index];
      $('.dock-progress').min=a;$('.dock-progress').max=b;
      sentenceRefs[index].forEach((ref,i)=>{
        const node=document.createElement('button');node.className='dock-node';node.type='button';
        node.style.left=`${(ref.start-a)/(b-a)*100}%`;
        node.title=`重听第 ${i+1} 句 · ${time(ref.start-a)}`;node.setAttribute('aria-label',node.title);
        node.onclick=()=>play(ref);$('.dock-nodes').append(node);
      });rendered=index;
    }
  };
  const update=()=>{
    if(activeSection===null)return;
    // Continuous playback follows the actual audio into subsequent sections without seeking back.
    if(mode==='continuous'&&!dock.hidden&&!scrubbing){
      const next=sectionTimes.findIndex(([a,b])=>audio.currentTime>=a&&audio.currentTime<b);
      if(next>=0&&next!==activeSection)show(next);
    }
    document.querySelectorAll('.sentence.playing,.dock-node.active').forEach(node=>node.classList.remove('playing','active'));
    launches.forEach((node,i)=>node.textContent=activeSection===i&&!audio.paused?'❚❚ 暂停本节':'▶ 播放本节');
    const [a,b]=sectionTimes[activeSection],elapsed=Math.max(0,Math.min(b-a,audio.currentTime-a));
    const current=sentenceRefs[activeSection].find(ref=>audio.currentTime>=ref.start&&audio.currentTime<ref.end);
    if(!audio.paused&&current&&mode!=='sentence')activeSentence=current;
    $('.dock-context').textContent=`第 ${activeSection+1} 节 · ${mode==='sentence'?'单句听读':mode==='section'?'本节播放':'连续播放'}`;
    $('.dock-progress').value=a+elapsed;
    $('.dock-progress').style.setProperty('--progress',`${elapsed/(b-a)*100}%`);
    $('.dock-time').textContent=`${time(elapsed)} / ${time(b-a)}`;
    const label=!audio.paused?'暂停':audio.currentTime>=lessonEnd-.01?'从头播放':'播放';
    const icon=!audio.paused?'❚❚':label==='从头播放'?'↺':'▶';
    $('.dock-play').textContent=`${icon} ${label}`;$('.dock-play').setAttribute('aria-label',label);
    $('.dock-replay').disabled=!activeSentence;
    if(!audio.paused&&current){
      wrapped[current.paragraphIndex][current.sentenceIndex].forEach(node=>node.classList.add('playing'));
      $('.dock-nodes').children[sentenceRefs[activeSection].indexOf(current)]?.classList.add('active');
    }
  };
  const playbackError=error=>{audio.pause();audio.controls=true;update();$('.dock-context').textContent='音频未能播放，请重试或使用页面顶部的音频控件。';$('.dock-context').setAttribute('role','status');console.error('Listening audio playback failed',error);};
  const startAudio=()=>{
    const request=++playRequest;
    try{const pending=audio.play();if(pending?.catch)pending.catch(error=>{if(request===playRequest&&error.name!=='AbortError')playbackError(error);});}
    catch(error){playbackError(error);}update();
  };
  const play=ref=>{show(paragraphToSection.get(ref.paragraphIndex));mode='sentence';activeSentence=ref;stopAt=ref.end;audio.currentTime=ref.start;startAudio();};
  const continueAudio=()=>{
    mode='continuous';stopAt=lessonEnd;
    if(audio.currentTime<lessonStart||audio.currentTime>=lessonEnd-.01)audio.currentTime=lessonStart;
    startAudio();
  };
  const playSection=index=>{
    if(activeSection===index&&!audio.paused){audio.pause();return;}
    show(index);mode='section';activeSentence=null;stopAt=sectionTimes[index][1];audio.currentTime=sectionTimes[index][0];startAudio();
  };
  sections.forEach((section,index)=>{const launch=document.createElement('button');launch.className='section-launch';launch.type='button';launch.textContent='▶ 播放本节';launch.onclick=()=>playSection(index);section.before(launch);launches.push(launch);const toggle=document.createElement('button');toggle.className='section-transcript';toggle.type='button';const setTranscript=showOriginal=>{section.classList.toggle('transcript-mode',showOriginal);toggle.classList.toggle('active',showOriginal);toggle.textContent=showOriginal?'返回批改':'查看原文';toggle.setAttribute('aria-pressed',String(showOriginal));toggle.setAttribute('aria-label',showOriginal?'返回本节批改':'查看本节原文');};setTranscript(false);toggle.onclick=()=>setTranscript(!section.classList.contains('transcript-mode'));section.before(toggle)});
  paragraphs.forEach((paragraph,p)=>paragraph.addEventListener('click',event=>{if(event.target.closest('.tip'))return;const piece=event.target.closest('.sentence');if(!piece)return;const s=+piece.dataset.s;play({paragraphIndex:p,sentenceIndex:s,start:cfg.sentenceTimings[p][s][0],end:cfg.sentenceTimings[p][s][1]})}));
  $('.dock-play').onclick=()=>audio.paused?continueAudio():audio.pause();
  $('.dock-replay').onclick=()=>{if(activeSentence)play(activeSentence);};
  $('.dock-close').onclick=()=>{++playRequest;audio.pause();dock.hidden=true;document.body.classList.remove('audio-dock-open');};
  const seekFromProgress=value=>{mode='continuous';stopAt=lessonEnd;audio.currentTime=+value;activeSentence=sentenceRefs[activeSection].find(ref=>audio.currentTime>=ref.start&&audio.currentTime<ref.end)||null;update();};
  $('.dock-progress').oninput=e=>seekFromProgress(e.currentTarget.value);
  $('.dock-progress').onpointerdown=e=>{scrubbing=true;seekGesture={id:e.pointerId,x:e.clientX,y:e.clientY,moved:false};e.currentTarget.setPointerCapture?.(e.pointerId);};
  $('.dock-progress').onpointermove=e=>{if(!seekGesture||seekGesture.id!==e.pointerId)return;if(Math.hypot(e.clientX-seekGesture.x,e.clientY-seekGesture.y)>6)seekGesture.moved=true;};
  const finishScrub=(e,cancelled=false)=>{if(!seekGesture||seekGesture.id!==e.pointerId)return;const {moved}=seekGesture;seekGesture=null;scrubbing=false;seekFromProgress(e.currentTarget.value);if(!cancelled&&!moved&&audio.paused&&audio.currentTime<lessonEnd-.01)startAudio();};
  $('.dock-progress').onpointerup=finishScrub;
  $('.dock-progress').onpointercancel=e=>finishScrub(e,true);
  $('.dock-rate').onchange=e=>audio.playbackRate=+e.target.value;
  window.addEventListener('keydown',e=>{const target=e.target instanceof Element?e.target:null;if((e.code!=='Space'&&e.key!==' ')||e.repeat||e.defaultPrevented||e.altKey||e.ctrlKey||e.metaKey||e.shiftKey||e.isComposing||target?.closest('input,textarea,select,[contenteditable="true"],[role="textbox"]'))return;e.preventDefault();if(dock.hidden)show(activeSection??0);audio.paused?continueAudio():audio.pause();},true);
  audio.addEventListener('timeupdate',update);audio.addEventListener('play',()=>{update();cancelAnimationFrame(monitor);const tick=()=>{if(!audio.paused&&stopAt!==null&&audio.currentTime>=stopAt){audio.pause();audio.currentTime=stopAt;update()}else if(!audio.paused)monitor=requestAnimationFrame(tick)};monitor=requestAnimationFrame(tick)});audio.addEventListener('pause',update);
  audio.addEventListener('error',()=>playbackError(audio.error));
  audio.addEventListener('ended',update);
  $('.dock-progress').setAttribute('aria-label','本节播放进度');
  $('.dock-rate').setAttribute('aria-label','播放速度');
  $('.dock-play').setAttribute('aria-keyshortcuts','Space');
  $('.dock-play').title='空格：播放/暂停';
  show(0);update();
  audio.controls=false;
  if(audio.error)playbackError(audio.error);
  } catch(error) {
    const audio=document.querySelector(window.LISTENING_PLAYER_CONFIG?.audioSelector||'#practiceAudio');
    if(audio){audio.controls=true;const note=document.createElement('div');note.setAttribute('role','status');note.textContent='逐句播放器未能加载，可使用上方音频控件播放完整录音。';audio.after(note);}
    document.querySelectorAll('.audio-dock,.section-launch,.section-transcript').forEach(node=>node.remove());
    document.body.classList.remove('audio-dock-open');
    console.error('Listening player initialization failed',error);
  }
})();
