(() => {
  const text = e => (e?.innerText ?? e?.textContent ?? '').trim();
  function htmlText(html) {
    const d = document.createElement('div'); d.innerHTML = html || '';
    d.querySelectorAll('script,style').forEach(e => e.remove());
    d.querySelectorAll('br').forEach(e => e.replaceWith('\n'));
    d.querySelectorAll('p,div,li').forEach(e => e.append('\n'));
    return (d.textContent || '').replace(/\r\n/g, '\n').replace(/\n{3,}/g, '\n\n').trim();
  }
  const editors = () => Object.values(window.UE?.instants || {});
  const reviewPage = () => /\/work\/(view|review)(?:\/|$)/i.test(location.pathname);
  function roots() {
    const result = new Map();
    for (const field of document.querySelectorAll('input[name^=answertype]')) {
      const id = field.name.slice(10), root = field.closest('.questionLi,.TiMu');
      if (root && /^\d+$/.test(id)) result.set(id, root);
    }
    if (!result.size) {
      const leaves = [...document.querySelectorAll('.questionLi,.TiMu')]
        .filter(root => !root.querySelector('.questionLi,.TiMu'));
      for (const [i, root] of leaves.entries()) {
        const id = root.id?.match(/\d+$/)?.[0] || root.getAttribute('data') || `view-${i + 1}`;
        result.set(id, root);
      }
    }
    return result;
  }
  function optionNodes(root) {
    return [...root.querySelectorAll('li[qid],.answerBg li')].filter(li => li.querySelector('[data],input[type=radio],input[type=checkbox]'));
  }
  function optionId(li) {
    return li.querySelector('span[data]')?.getAttribute('data') ??
      li.querySelector('input[type=radio],input[type=checkbox]')?.value ?? null;
  }
  function selected(li) {
    if (li.hasAttribute('aria-checked')) return li.getAttribute('aria-checked') === 'true';
    const input = li.querySelector('input[type=radio],input[type=checkbox]');
    if (input) return input.checked;
    return !!li.querySelector('.check_answer');
  }
  function parseChoice(value, ids) {
    if (!value) return [];
    if (ids.includes(value)) return [value];
    if (value.includes(',')) return value.split(',').filter(Boolean);
    if (/^[A-Z]+$/.test(value) && ids.every(id => /^[A-Z]$/.test(id))) return [...value];
    return [value];
  }
  function fields(root) {
    return [...root.querySelectorAll('textarea,input:not([type=hidden])')].filter(e => /^answer/.test(e.id || ''));
  }
  function questionImages(head, optionRows) {
    const images = [...(head?.querySelectorAll('img') || [])]
      .map(node => ({node, part:'stem', option:null}));
    optionRows.forEach((row, index) => {
      for (const node of row.querySelectorAll('img')) {
        if (!head?.contains(node)) images.push({node, part:'option', option:index+1});
      }
    });
    return images;
  }
  function findImages(root) {
    const head = root.querySelector('.mark_name,.Zy_TItle,.stem');
    const controls = optionNodes(root);
    const rows = reviewPage() && !controls.length ? [...root.querySelectorAll('.mark_letter li')] : controls;
    return questionImages(head, rows);
  }
  function readQuestion(id, root) {
    const head = root.querySelector('.mark_name,.Zy_TItle,.stem');
    const review = reviewPage();
    const typeLabel = text(head?.querySelector('.colorShallow'));
    const inferred = /多选题/.test(typeLabel) ? '1' : /单选题/.test(typeLabel) ? '0' :
      /填空题/.test(typeLabel) ? '2' : /简答题|论述题/.test(typeLabel) ? '4' : null;
    const type = root.querySelector('input[name^=answertype]')?.value ?? (review ? inferred : null);
    const stem = text(head) || text(root).slice(0, 2000);
    const controls = optionNodes(root);
    // Display letters on a review page must never become writable control identifiers.
    const displayedOptions = review && !controls.length ? [...root.querySelectorAll('.mark_letter li')] : [];
    const options = displayedOptions.length ? displayedOptions.map(li => {
      const value = text(li), match = value.match(/^([A-Z])\s*[.．、:：]\s*/);
      return {id: match?.[1] || null, text: match ? value.slice(match[0].length).trim() : value,
        label: match?.[1] || ''};
    }) : controls.map(li => {
      const copy = li.cloneNode(true); copy.querySelectorAll('.num_option,.num_option_dx,input').forEach(e => e.remove());
      return {id: optionId(li), text: text(copy), label: text(li.querySelector('.num_option,.num_option_dx'))};
    });
    // Blank positions come from the page, not the asynchronous editor registration order.
    const fs = fields(root), keys = fs.map(e => e.id);
    const es = fs.map(f => editors().find(e => e.textarea === f || e.key === f.id));
    // Plain controls contain literal text; interpreting <todo> as markup would hide an existing answer.
    const values = fs.map((f, i) => es[i] ? htmlText(es[i].body?.innerHTML) : f.value.trim());
    const formValues = fs.map((f, i) => es[i] ? htmlText(f.value) : f.value.trim());
    let kind = 'unsupported', answer = '', formAnswer = '';
    if (options.length && options.every(o => o.id)) {
      kind = 'choice';
      const ids = options.map(o => o.id);
      formAnswer = parseChoice(document.getElementById('answer' + id)?.value || '', ids);
      answer = optionNodes(root).filter(selected).map(optionId);
      if (review) {
        answer = parseChoice(text(root.querySelector('.stuAnswerContent')).replace(/\s+/g, ''), ids);
        formAnswer = null;
      }
    } else if (review && type === '2') {
      kind = 'blanks';
      answer = [...root.querySelectorAll('.stuAnswerContent')]
        .map(e => htmlText(e.innerHTML).replace(/^\s*[(（]\d+[)）]\s*/, ''));
      formAnswer = null;
    } else if (review && type === '4') {
      kind = 'text'; answer = text(root.querySelector('.stuAnswerContent')); formAnswer = null;
    } else if (type === '2' || keys.length > 1) {
      kind = keys.length ? 'blanks' : 'unsupported'; answer = values; formAnswer = formValues;
    } else if (keys.length === 1) {
      kind = 'text'; answer = values[0]; formAnswer = formValues[0];
    }
    const hasAssets = es.some(e => e?.body?.querySelector('img,audio,video,iframe,object,a[href]'));
    const manualAudio = !!root.querySelector('audio,iframe[src*="audioplay"]');
    const correctValues = review ? [...root.querySelectorAll('.rightAnswerContent')]
      .map(e => htmlText(e.innerHTML).replace(/^\s*[(（]\d+[)）]\s*/, '')) : [];
    const correct = kind === 'choice' ? parseChoice(correctValues.join('').replace(/\s+/g, ''), options.map(o => o.id)) :
      kind === 'blanks' ? correctValues : correctValues.join('\n');
    return {
      id, kind, type_code: type || null, stem, options, multiple: type === '1', answer,
      form_answer: formAnswer, editor_keys: keys, has_assets: hasAssets,
      ...(review ? {correct_answer: correct, explanation: text(root.querySelector('.qtAnalysis'))} : {}),
      manual_only: manualAudio || /朗读|听录音|听力|听写|\bdictation\b|\blistening\b|\blisten to\b|(?:上传|提交).{0,30}(?:录音|语音)/i.test(stem),
      images: questionImages(head, displayedOptions.length ? displayedOptions : controls)
        .map(({node, part, option}) => ({url: node.src, alt: node.alt, part, option})),
      needs_vision: /[\ue000-\uf8ff]/.test(stem),
      resources: [...root.querySelectorAll('audio,video,iframe:not([id^=ueditor_])')].map(e => ({tag: e.tagName, url: e.getAttribute('src')}))
    };
  }
  function assignmentIdentity() {
    const url = new URL(location.href);
    const value = (id, query) => document.getElementById(id)?.value || url.searchParams.get(query || id) || '';
    return {course_id: value('courseId'), work_id: value('workId')};
  }
  function imageTargets(request) {
    ensureIdentity(assignmentIdentity(), request);
    const limit = request.limit;
    if (!Number.isInteger(limit) || limit < 1 || limit > 4) throw Error('IMAGE_LIMIT');
    const groups = [];
    let number = 0;
    for (const [id, root] of roots()) {
      number += 1;
      const images = findImages(root);
      if (images.length) groups.push({id, number, images:images.slice(0,8), truncated:images.length>8});
      if (groups.length === limit) break;
    }
    return groups;
  }
  function read() {
    const url = new URL(location.href);
    const qs = [...roots()].map(([id, root]) => readQuestion(id, root));
    const editable = !/\/work\/(view|review)/i.test(url.pathname) &&
      typeof window.saveWork === 'function' && !!document.querySelector('input[name^=answertype]');
    return {...assignmentIdentity(), title: document.title,
      editable, questions: qs, page_text: text(document.body), path: location.pathname};
  }
  function ensureIdentity(snapshot, request) {
    if (!request || String(snapshot.course_id) !== String(request.course_id) ||
        String(snapshot.work_id) !== String(request.work_id)) throw Error('IDENTITY_MISMATCH');
  }
  function fill(request) {
    const snapshot = read();
    ensureIdentity(snapshot, request);
    const changes = request.changes;
    if (!snapshot.editable) throw Error('READ_ONLY');
    // Validate the entire batch before its first write, including changes made by the user since the last read.
    for (const change of changes) {
      const q = snapshot.questions.find(q => q.id === change.id);
      if (!q || JSON.stringify(q.answer) !== JSON.stringify(change.before)) throw Error('PAGE_CHANGED: ' + change.id);
      if (q.has_assets) throw Error('ASSETS_PRESENT: ' + change.id);
      if (q.manual_only) throw Error('MANUAL_TASK: ' + change.id);
      if (q.kind !== change.kind) throw Error('QUESTION_CHANGED: ' + change.id);
      if (q.kind !== 'choice') {
        for (const key of q.editor_keys) {
          const e = editors().find(e => e.key === key), f = document.getElementById(key);
          if (!f || (e && (!e.isReady || !e.body))) throw Error('EDITOR_NOT_READY: ' + key);
        }
      }
    }
    for (const change of changes) {
      const root = roots().get(change.id);
      const q = snapshot.questions.find(q => q.id === change.id);
      if (q.kind === 'choice') {
        for (const li of optionNodes(root)) {
          if (change.value.includes(optionId(li)) && !selected(li)) li.click();
        }
      } else {
        const values = q.kind === 'text' ? [change.value] : change.value;
        q.editor_keys.forEach((key, i) => {
          const field = document.getElementById(key), e = editors().find(e => e.key === key);
          if (e) {
            const node = document.createElement('p'); node.style.whiteSpace = 'pre-wrap'; node.textContent = values[i];
            e.setContent(node.outerHTML); if (e.sync) e.sync();
          } else field.value = values[i];
          field.dispatchEvent(new Event('input', {bubbles: true}));
          field.dispatchEvent(new Event('change', {bubbles: true}));
        });
        if (typeof window.syncAnswer === 'function') window.syncAnswer(change.id, q.type_code);
      }
    }
    return {changed: changes.length};
  }
  function save(request) {
    const snapshot = read();
    ensureIdentity(snapshot, request);
    if (!snapshot.editable) throw Error('READ_ONLY');
    if (snapshot.questions.some(q => q.manual_only)) throw Error('MANUAL_TASK');
    if (snapshot.questions.some(q => q.kind === 'unsupported')) throw Error('UNSUPPORTED_QUESTION');
    if (window.saveLock) throw Error('SAVE_BUSY');
    window.__cxDraftSave = {status: 'pending'};
    window.saveWork({
      success: () => { window.__cxDraftSave = {status: 'saved'}; },
      failure: data => { window.__cxDraftSave = {status: 'failed', message: data?.msg || '保存失败'}; }
    });
    return {status: 'pending'};
  }
  return {read, fill, save, imageTargets};
})()
