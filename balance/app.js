/* PoE1 Gem Balance — standalone static GitHub Pages app.
   Dataset schema: balance/data/3.29.json. No external JS dependencies. */
(() => {
  'use strict';
  const $ = selector => document.querySelector(selector);
  const esc = input => String(input == null ? '' : input).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const fmt = (n, max=1) => Number(n).toLocaleString('ko-KR',{maximumFractionDigits:max});
  const state = { query:'', verdict:'all', kind:'all', metric:'all', direction:'buff' };
  const names = {buff:'상향',nerf:'하향',mixed:'복합',adjusted:'조정',new:'신규'};
  const metricLabels = {all:'주요 변경폭',damage:'기본 피해량',effectiveness:'추가 피해 효율',supportDamage:'보조 피해 배율',speed:'시전·공격 속도',cooldown:'재사용 대기시간',cost:'소모 비용·배율',crit:'치명타 확률',radius:'효과 반경',duration:'지속시간',projectiles:'투사체 수',count:'변경 항목 수',utility:'기타 효과',other:'기타'};
  const groupsOrder = ['damage','effectiveness','supportDamage','speed','cooldown','cost','crit','radius','duration','projectiles','utility','other'];
  let payload = null;
  let byId = new Map();
  let previousFocus = null;
  let modalHistoryOpened = false;

  const readState = () => {
    try {
      const saved = JSON.parse(sessionStorage.getItem('poe1.balance.filters.v1') || '{}');
      if (['all','buff','nerf','mixed','adjusted','new'].includes(saved.verdict)) state.verdict=saved.verdict;
      if (['all','active','support','transfigured','vaal'].includes(saved.kind)) state.kind=saved.kind;
      if (Object.hasOwn(metricLabels,saved.metric) && saved.metric !== 'utility' && saved.metric !== 'other') state.metric=saved.metric;
      if (['buff','nerf'].includes(saved.direction)) state.direction=saved.direction;
      if (typeof saved.query === 'string') state.query=saved.query.slice(0,120);
    } catch (_) { /* storage optional */ }
  };
  const saveState = () => { try {sessionStorage.setItem('poe1.balance.filters.v1',JSON.stringify(state));} catch (_) {} };

  function formatDelta(c,compact=false) {
    if (c.impactPct == null || !Number.isFinite(c.impactPct)) return '변경';
    // Display direct numerical change for costs / cooldown; use rate for cast time.
    if (c.key === 'castTime' || c.key === 'attackTime' || c.key === 'triggerInterval') {
      const p = c.impactPct;
      return (p>=0?'+':'')+fmt(p,1)+'%';
    }
    if (c.key === 'crit') {
      const pp = Number(c.after)-Number(c.before);
      return (pp>=0?'+':'')+fmt(pp,2)+'%p';
    }
    if (c.key === 'lessDamage') {
      const p = c.impactPct;
      return (p>=0?'+':'')+fmt(p,1)+'%';
    }
    const p = c.deltaPct;
    if (p == null) return '변경';
    return (p>=0?'+':'')+fmt(p,1)+'%';
  }
  function metricName(c) {
    if (c.key === 'castTime') return '기본 시전 속도';
    if (c.key === 'attackTime') return '기본 공격 속도';
    if (c.key === 'triggerInterval') return '발동 빈도';
    if (c.key === 'lessDamage') return '실효 피해 배율';
    return c.label || metricLabels[c.group] || '효과 변경';
  }
  function qualifies(c, metric) {
    if (c.type !== 'modified' || !Number.isFinite(c.impactPct)) return false;
    if (metric === 'all') return true;
    return c.group === metric;
  }
  function sortValue(g) {
    if (state.metric === 'count') return g.changes.length;
    const candidates = g.changes.filter(c=>qualifies(c,state.metric)).map(c=>Number(c.impactPct));
    if (!candidates.length) return null;
    return state.direction==='buff' ? Math.max(...candidates) : Math.min(...candidates);
  }
  function heroChange(g) {
    if (state.metric === 'count') return null;
    const candidates = g.changes.filter(c => qualifies(c,state.metric));
    if (!candidates.length) return null;
    const sorted = candidates.slice().sort((a,b) => state.direction==='buff' ? b.impactPct-a.impactPct : a.impactPct-b.impactPct);
    return sorted[0];
  }
  function isVariant(g, value) {
    if (value==='all') return true;
    if (value==='active' || value==='support') return g.kind===value;
    if (value==='transfigured') return g.variant==='transfigured';
    if (value==='vaal') return g.variant==='vaal' || /^Vaal/i.test(g.nameEn||'');
    return true;
  }
  function getFiltered() {
    const search=state.query.toLocaleLowerCase('ko').trim();
    const out=payload.gems.filter(g => {
      if (state.verdict!=='all' && g.verdict!==state.verdict) return false;
      if (!isVariant(g,state.kind)) return false;
      if (search && ![g.nameKo,g.nameEn,g.id].some(s=>String(s||'').toLocaleLowerCase('ko').includes(search))) return false;
      return true;
    });
    out.sort((a,b)=> {
      let av=sortValue(a),bv=sortValue(b);
      if (av===null && bv===null) return a.nameKo.localeCompare(b.nameKo,'ko');
      if (av===null) return 1;
      if (bv===null) return -1;
      if (av!==bv) return state.direction==='buff' ? bv-av : av-bv;
      return a.nameKo.localeCompare(b.nameKo,'ko');
    });
    return out;
  }
  function badge(g) { return `<span class="status ${esc(g.verdict)}">${esc(names[g.verdict]||'조정')}</span>`; }
  function gemIcon(g) {
    const color = ['r','g','b','w'].includes(g.color) ? g.color:'w';
    const support = g.kind==='support'?' is-support':'';
    const img = g.icon && !/^\s*(?:javascript:|data:)/i.test(g.icon) ? `<img alt="" loading="lazy" src="${esc(g.icon)}" onerror="this.remove()">` : '';
    return `<span class="gem-icon c-${color}${support}" aria-hidden="true"><span class="gem-facet"></span>${img}</span>`;
  }
  function previewCard(g) {
    const h=heroChange(g);
    const numeric=g.changes.filter(c=>c.type==='modified' && Number.isFinite(c.impactPct));
    const others=numeric.filter(c=>c!==h).sort((a,b)=>Math.abs(b.impactPct)-Math.abs(a.impactPct)).slice(0,2);
    const typ=g.kind==='support'?'보조젬':'스킬젬';
    const variant=g.variant==='transfigured'?' · 변형':(g.variant==='vaal'?' · 바알':'');
    const hero = g.gemState==='new'
      ? `<span class="metric-main"><span class="metric-change newcolor">신규 젬</span><span class="metric-name">새롭게 추가</span></span>`
      : state.metric==='count'
        ? `<span class="metric-main"><span class="metric-name">변경 항목</span><span class="metric-change neutral">${g.changes.length}건</span></span>`
        : h
          ? `<span class="metric-main"><span class="metric-name">${esc(metricName(h))}</span><span class="metric-change ${h.impact==='buff'?'positive':h.impact==='nerf'?'negative':'neutral'}">${esc(formatDelta(h))}</span></span>`
          : `<span class="metric-empty">${state.metric==='all'?'효과 추가·삭제 및 문구 변경':'선택한 항목의 수치 변경 없음'}</span>`;
    const extra=others.map(c=>`<span class="metric-secondary ${c.impact==='buff'?'positive':c.impact==='nerf'?'negative':''}">${esc(metricName(c))} <b>${esc(formatDelta(c,true))}</b></span>`).join('');
    const unseen = Math.max(0,g.changes.length - (h?1:0) - others.length);
    const tail= unseen>0 ? `+${unseen}개 변경` : `${typ}${variant}`;
    return `<button class="gem-card verdict-${esc(g.verdict)}" type="button" data-gem="${esc(g.id)}" aria-label="${esc(g.nameKo)} 변경 상세 열기">
      ${gemIcon(g)}<span class="gem-card-inner">
        <span class="gem-header"><span class="gem-name">${esc(g.nameKo)}</span>${badge(g)}<span class="gem-en">${esc(g.nameEn)}</span></span>
        <span class="gem-highlights">${hero}${extra}</span>
        <span class="gem-note">${esc(tail)}</span>
      </span><span class="card-arrow" aria-hidden="true">›</span>
    </button>`;
  }
  function renderSummary() {
    const counts={total:payload.gems.length,buff:0,nerf:0,mixed:0,adjusted:0,new:0};
    for(const g of payload.gems)counts[g.verdict]=(counts[g.verdict]||0)+1;
    const cards=[['total','변경 젬'],['buff','상향'],['nerf','하향'],['mixed','복합·조정'],['new','신규']];
    $('#summary-grid').innerHTML=cards.map(([key,label])=>{
      const count=key==='mixed'?(counts.mixed+counts.adjusted):counts[key];
      return `<div class="summary-item ${key}"><span class="summary-label">${label}</span><strong>${fmt(count,0)}</strong></div>`;
    }).join('');
    const segments=['buff','nerf','mixed','adjusted','new'];
    $('#distribution').innerHTML=segments.map(k=>`<span class="${k}" style="width:${counts.total?100*(counts[k]||0)/counts.total:0}%" title="${esc(names[k])}: ${counts[k]||0}"></span>`).join('');
    $('#patch-overline').textContent=`PATCH ${payload.patch} · GEM CHANGES`;
    $('#basis-label').textContent='Lv20 · 품질 20% 기준';
    $('#overall-note').textContent=`${payload.previousPatch} → ${payload.patch}`;
    const source=payload.source||{};
    const isPartial=['partial','pending','requires_review'].includes(source.status);
    $('#source-label').textContent=source.status==='requires_review'?'자동 추출 · 검토 필요':(isPartial?'검증용 데이터셋':'패치노트 변환 데이터');
    const notice=$('#source-notice');
    notice.hidden=!isPartial;
    notice.textContent=isPartial?(source.noticeKo||(source.status==='requires_review'?'자동 추출 결과입니다. 미매칭/미분류 변경을 검토한 뒤 공개하세요.':'현재 데이터는 일부 항목만 포함합니다.')) : '';
  }
  function renderFilters() {
    $('#search').value=state.query;
    $('#kind-select').value=state.kind;
    $('#metric-select').value=state.metric;
    const button=$('#sort-dir');
    button.dataset.dir=state.direction;
    $('#sort-dir-text').textContent=state.direction==='buff'?'상향순':'하향순';
    button.querySelector('.sort-icon').textContent=state.direction==='buff'?'↗':'↘';
    document.querySelectorAll('[data-verdict]').forEach(btn=>{
      const chosen=btn.dataset.verdict===state.verdict;
      btn.classList.toggle('is-selected',chosen);
      btn.setAttribute('aria-pressed',String(chosen));
    });
  }
  function renderList() {
    if (!payload) return;
    const items=getFiltered();
    $('#results-count').textContent=`${fmt(items.length,0)}개 젬`;
    const about=state.metric==='all'?'주요 변경폭':metricLabels[state.metric];
    const order=state.direction==='buff'?'상향 효과가 큰 순':'하향 효과가 큰 순';
    $('#list-description').textContent=`${about} 기준 · ${order} · 해당 항목 없는 젬은 뒤에 표시`;
    $('#gem-list').innerHTML=items.length?items.map(previewCard).join(''):
      `<div class="empty"><b>조건에 맞는 젬이 없습니다.</b>검색어나 필터를 바꿔보세요.</div>`;
    const partial=payload.source&&payload.source.status==='partial';
    $('#list-footnote').textContent=partial
      ? `현재 ${fmt(payload.gems.length,0)}개 젬만 담긴 선별 미리보기입니다. 전체 3.29 데이터는 HTML 분석기로 생성할 수 있습니다. 정렬에서 변화율은 동일 항목 안에서 비교하세요.`
      : '수치 변화율은 Lv20 기준입니다. 다른 스탯 간 변화율이 곧 전체 젬 성능의 우열을 의미하지는 않습니다.';
  }
  function refresh() {renderFilters();renderList();saveState();}

  function getChangeGroup(c) {return groupsOrder.includes(c.group)?c.group:'other';}
  function compareBars(c) {
    if (!Number.isFinite(c.before) || !Number.isFinite(c.after) || c.before<0 || c.after<0) return '';
    const maximum=Math.max(c.before,c.after);
    if (!maximum) return '';
    const a=Math.max(3,100*c.before/maximum),b=Math.max(3,100*c.after/maximum);
    return `<div class="compare-bars" aria-hidden="true"><div class="track"><span class="fill" style="width:${a}%"></span></div><div class="track after"><span class="fill" style="width:${b}%"></span></div></div>`;
  }
  function numChangeRow(c) {
    const p = c.impact==='buff'?'positive':(c.impact==='nerf'?'negative':'neutral');
    const comment = ['castTime','attackTime','triggerInterval'].includes(c.key)
      ? '※ 변화율은 속도(초당 사용 횟수)로 환산하여 표시'
      : c.key==='lessDamage'
        ? '※ less Damage의 실효 피해 배율로 환산'
        : c.key==='crit'?'※ 치명타 확률 변화는 퍼센트포인트(%p)로 표시':'';
    return `<article class="change-row"><div class="change-heading"><span class="change-name">${esc(c.label)}</span><span class="change-impact ${p}">${esc(formatDelta(c))}${c.impact==='buff'?' · 상향':c.impact==='nerf'?' · 하향':''}</span></div><div class="change-values"><span class="change-old">${esc(c.beforeText||fmt(c.before,2))}</span><span class="change-arr">→</span><span class="change-new">${esc(c.afterText||fmt(c.after,2))}</span></div>${compareBars(c)}${comment?`<div class="change-comment">${comment}</div>`:''}</article>`;
  }
  function qualitativeRow(c) {
    const kind=c.type==='added'?'추가':c.type==='removed'?'제거':'변경';
    const text=c.type==='added'?c.afterText:c.type==='removed'?c.beforeText:
      (c.beforeText&&c.afterText?`${c.beforeText} → ${c.afterText}`:(c.afterText||c.beforeText||'효과 변경'));
    return `<article class="qualitative ${esc(c.type)}"><span class="sign">${c.type==='added'?'+':c.type==='removed'?'−':'↔'}</span><div><div class="kind">${kind}</div><div class="desc">${esc(text)}</div></div></article>`;
  }
  function renderModalContent(g) {
    const countBuff=g.changes.filter(c=>c.impact==='buff').length;
    const countNerf=g.changes.filter(c=>c.impact==='nerf').length;
    const details=[`${g.changes.length}개 변경 항목`];
    if(countBuff)details.push(`상향 ${countBuff}`);
    if(countNerf)details.push(`하향 ${countNerf}`);
    const typeText=(g.kind==='support'?'보조젬':'스킬젬') + (g.variant==='transfigured'?' · 변형':g.variant==='vaal'?' · 바알':'');
    $('#modal-id').textContent=`${payload.previousPatch} → ${payload.patch} / ${typeText}`;
    const numeric=g.changes.filter(c=>c.type==='modified'&&Number.isFinite(c.before)&&Number.isFinite(c.after));
    const qualitative=g.changes.filter(c=>!numeric.includes(c));
    const sections=groupsOrder.map(key=>{
      const row=numeric.filter(c=>getChangeGroup(c)===key);
      if(!row.length)return '';
      return `<section class="modal-section"><h3 class="modal-section-title">${esc(metricLabels[key]||'효과 변경')} <span>(${row.length})</span></h3>${row.map(numChangeRow).join('')}</section>`;
    }).join('');
    $('#modal-body').innerHTML=`
      <div class="modal-header">${gemIcon(g)}<div class="modal-header-main"><h2 id="modal-title">${esc(g.nameKo)}</h2><div class="english">${esc(g.nameEn)}</div><div class="modal-header-tags">${badge(g)}<span class="gem-variant">${esc(typeText)}</span></div></div></div>
      <div class="modal-lead">${g.gemState==='new'?'이번 패치에서 <strong>새로 추가된 젬</strong>입니다.':`<strong>${esc(details.join(' · '))}</strong> · 변경된 항목만 표시합니다.`}<br>${esc(payload.previousPatch)}에서 ${esc(payload.patch)}로 변경된 Lv20 기준 수치입니다.</div>
      ${sections}
      ${qualitative.length?`<section class="modal-section"><h3 class="modal-section-title">효과·설명 변경 (${qualitative.length})</h3>${qualitative.map(qualitativeRow).join('')}</section>`:''}
      ${!g.changes.length?`<div class="empty">추가 상세정보는 공식 원문에서 확인하세요.</div>`:''}`;
    $('#modal-basis').textContent='Lv20 · 품질 20%';
    const source=(payload.source||{}).url;
    $('#modal-source').href=/^https:\/\//i.test(source)?source:'https://www.pathofexile.com';
  }
  function matchModalFromUrl() {
    const m=location.hash.match(/^#gem=(.+)$/);
    if (!m) return null;
    try {return byId.get(decodeURIComponent(m[1])) || null;} catch (_) {return null;}
  }
  function setModalVisible(flag) {
    $('#modal').classList.toggle('is-open',flag);
    $('#modal').setAttribute('aria-hidden',String(!flag));
    document.body.classList.toggle('modal-active',flag);
    if (flag) {
      $('.modal-sheet').focus({preventScroll:true});
    } else if (previousFocus && previousFocus.isConnected) {
      previousFocus.focus({preventScroll:true});
      previousFocus=null;
    }
  }
  function openModal(g,historyEntry=true) {
    if(!g) return;
    previousFocus=document.activeElement;
    renderModalContent(g);
    setModalVisible(true);
    $('#modal-body').scrollTop=0;
    if(historyEntry){
      modalHistoryOpened=true;
      history.pushState({poeBalanceModal:true,gem:g.id},'',`#gem=${encodeURIComponent(g.id)}`);
    }
  }
  function closeModal() {
    if (!$('#modal').classList.contains('is-open'))return;
    setModalVisible(false);
    if (modalHistoryOpened && history.state && history.state.poeBalanceModal) {
      modalHistoryOpened=false;
      history.back();
    } else if (location.hash.startsWith('#gem=')) {
      history.replaceState(null,'',location.pathname+location.search);
    }
  }
  function syncModalWithHistory() {
    const gem=matchModalFromUrl();
    if (gem) {
      if (!$('#modal').classList.contains('is-open'))openModal(gem,false);
      else renderModalContent(gem);
    } else {modalHistoryOpened=false;setModalVisible(false);}
  }
  function installEvents() {
    $('#search').addEventListener('input',e=>{state.query=e.target.value;refresh();});
    document.querySelectorAll('[data-verdict]').forEach(btn=>btn.addEventListener('click',()=>{state.verdict=btn.dataset.verdict;refresh();}));
    $('#kind-select').addEventListener('change',e=>{state.kind=e.target.value;refresh();});
    $('#metric-select').addEventListener('change',e=>{state.metric=e.target.value;refresh();});
    $('#sort-dir').addEventListener('click',()=>{state.direction=state.direction==='buff'?'nerf':'buff';refresh();});
    $('#reset-filters').addEventListener('click',()=>{
      Object.assign(state,{query:'',verdict:'all',kind:'all',metric:'all',direction:'buff'});refresh();
    });
    $('#gem-list').addEventListener('click',e=>{
      const button=e.target.closest('[data-gem]');
      if(button)openModal(byId.get(button.dataset.gem));
    });
    $('#modal-close').addEventListener('click',closeModal);
    $('#modal').addEventListener('click',e=>{if(e.target.dataset.close==='true')closeModal();});
    document.addEventListener('keydown',e=>{
      if(e.key==='Escape' && $('#modal').classList.contains('is-open'))closeModal();
      if(e.key==='/' && !['INPUT','TEXTAREA','SELECT'].includes(document.activeElement.tagName) && !$('#modal').classList.contains('is-open')){
        e.preventDefault();$('#search').focus();
      }
      if(e.key==='Tab' && $('#modal').classList.contains('is-open')){
        // The modal has a close button and external source link; keep focus inside.
        const targets=Array.from($('#modal').querySelectorAll('a[href],button:not([disabled])'));
        if(!targets.length)return;
        const first=targets[0],last=targets[targets.length-1];
        if(e.shiftKey && (document.activeElement===first || document.activeElement===$('.modal-sheet'))){e.preventDefault();last.focus();}
        else if(!e.shiftKey && document.activeElement===last){e.preventDefault();first.focus();}
      }
    });
    window.addEventListener('popstate',syncModalWithHistory);
    window.addEventListener('hashchange',syncModalWithHistory);
  }
  async function init() {
    readState();
    installEvents();
    const params=new URLSearchParams(location.search);
    const requested=params.get('patch');
    // Only explicit, safe built-in patch names are accepted (never arbitrary paths).
    // New patch JSON automatically becomes the homepage dataset. Keep 3.29
    // selectable with ?patch=3.29; never fetch the .template.json directly.
    const candidates=requested==='3.29'?['3.29.json']:
      requested==='3.30'?['3.30.json']:['3.30.json','3.29.json'];
    try {
      let lastError=null;
      for (const name of candidates) {
        try {
          const response=await fetch(`./data/${name}?v=1`,{cache:'no-store'});
          if(!response.ok)throw Error(`${name}: HTTP ${response.status}`);
          payload=await response.json();
          break;
        } catch (e) {lastError=e;}
      }
      if (!payload)throw lastError||Error('Cannot load patch JSON');
      if(!payload||!Array.isArray(payload.gems))throw Error('Invalid balance data: gems[] missing');
      byId=new Map(payload.gems.map(g=>[g.id,g]));
      renderSummary();refresh();syncModalWithHistory();
    } catch (e) {
      console.error('Failed to load balance data',e);
      $('#gem-list').innerHTML=`<div class="empty"><b>데이터를 불러올 수 없습니다.</b>GitHub Pages 또는 로컬 HTTP 서버에서 열었는지 확인하세요.<br><small>${esc(e.message)}</small></div>`;
      $('#overall-note').textContent='로드 오류';
    }
  }
  init();
})();
