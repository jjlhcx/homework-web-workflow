() => {
  const clean = value => (value || '').replace(/\s+/g, ' ').trim();
  const cards = [...document.querySelectorAll('.ulDiv > ul > li')];
  if (!cards.length) throw Error('UNSUPPORTED_LAYOUT: cannot certify an empty list');
  return cards.map(card => {
    const title = card.querySelector('.titTxt p a');
    const status = clean(card.querySelector('.titTxt strong')?.textContent);
    if (!title || !clean(title.getAttribute('title') || title.textContent) || !status)
      throw Error('INCOMPLETE_CARD: title/status missing');
    const labels = [...card.querySelectorAll('.titTxt .pt5')].map(e => clean(e.textContent));
    return {
      title: clean(title.getAttribute('title') || title.textContent), status,
      deadline: (labels.find(line => line.includes('截止时间')) || '').replace(/^截止时间\s*[:：]?\s*/, '')
    };
  });
}
