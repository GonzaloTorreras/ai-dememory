'use strict';
const $ = (selector) => document.querySelector(selector);
const state = { settings: null, dirty: false, busy: false, scope: 'global' };
const pages = {
  memory: ['Memory', 'Useful knowledge, with its source and scope.'],
  providers: ['Providers & routing', 'Choose how learning and consolidation run.'],
  consolidation: ['Consolidation', 'Keep memory useful, on your schedule.'],
  activity: ['Activity', 'Understand what ran and what it consumed.'],
};

function element(tag, text, className) {
  const item = document.createElement(tag);
  if (text !== undefined) item.textContent = String(text);
  if (className) item.className = className;
  return item;
}
function notify(message, error = false) {
  const notice = $('#notice');
  notice.textContent = message;
  notice.className = error ? 'notice error' : 'notice';
  notice.hidden = !message;
}
function markDirty(value = true) {
  state.dirty = value;
  $('#dirty-notice').hidden = !value;
}
function showPage() {
  const name = location.hash.slice(1) in pages ? location.hash.slice(1) : 'memory';
  document.querySelectorAll('.page').forEach((page) => { page.hidden = page.id !== name; });
  document.querySelectorAll('nav a').forEach((link) => {
    if (link.hash === `#${name}`) link.setAttribute('aria-current', 'page');
    else link.removeAttribute('aria-current');
  });
  $('#page-title').textContent = pages[name][0];
  $('#page-description').textContent = pages[name][1];
  document.title = `ai DeMemory · ${pages[name][0]}`;
}
async function request(path, body) {
  const options = body === undefined ? {} : {
    method: 'POST', headers: { 'Content-Type': 'application/json',
      'X-DeMemory-Token': $('meta[name="dememory-token"]').content }, body: JSON.stringify(body),
  };
  const response = await fetch(path, { ...options, credentials: 'same-origin' });
  const data = await response.json();
  if (!response.ok || data.error) throw new Error(data.error || `Request failed (${response.status})`);
  return data;
}
async function perform(action) {
  if (state.busy) return;
  state.busy = true;
  const hadSettings = Boolean(state.settings);
  const controls = [...document.querySelectorAll('button, input, select, textarea')];
  const disabled = controls.map((control) => control.disabled);
  controls.forEach((control) => { control.disabled = true; });
  try { await action(); }
  catch (error) { notify(error.message || 'Unable to complete this action. Please try again.', true); }
  finally {
    state.busy = false;
    controls.forEach((control, index) => { control.disabled = (hadSettings && disabled[index]) || (!state.settings && control.id !== 'refresh'); });
  }
}
function emptyRow(target, columns, message) {
  const row = element('tr'), cell = element('td', message, 'empty');
  cell.colSpan = columns; row.append(cell); target.append(row);
}
function button(text, action) {
  const item = element('button', text); item.type = 'button';
  item.addEventListener('click', action); return item;
}
function timestamp(value) { return value ? new Date(value).toLocaleString() : 'Not yet'; }
function number(value) { return Number(value || 0).toLocaleString(); }
function renderMemories(memories) {
  const list = $('#memory-list'); list.replaceChildren();
  if (!memories.length) list.append(element('p', 'No memories in this scope yet. Save something useful below.', 'memory-empty'));
  for (const memory of memories) {
    const card = element('article', undefined, 'memory-card'), header = element('header');
    const status = memory.status || 'active';
    header.append(element('h2', memory.title), element('span', status, `badge ${status === 'provisional' ? 'provisional' : status === 'active' ? '' : 'inactive'}`));
    card.append(header, element('p', memory.content));
    const source = memory.source || {};
    const metadata = [memory.scope || 'global', source.provider || 'direct', source.evidence_kind || 'saved memory', timestamp(memory.created_at)];
    if (memory.key) metadata.push(`Key: ${memory.key}`);
    card.append(element('p', metadata.join(' · '), 'hint'));
    if (source.excerpt) { const details = element('details'); details.append(element('summary', 'Source excerpt'), element('p', source.excerpt)); card.append(details); }
    if (status === 'active' || status === 'provisional') {
      const actions = element('div', undefined, 'actions');
      actions.append(button(memory.supersedes ? 'Undo replacement' : 'Forget', () => perform(async () => {
        const result = await request('/api/forget', { memory_id: memory.memory_id, scope: memory.scope || state.scope });
        await refresh(); notify(result.restored_memory_id ? 'Previous memory restored.' : 'Memory marked inactive.');
      }))); card.append(actions);
    }
    list.append(card);
  }
}
function providerOptions(select, selected = '') {
  select.replaceChildren(new Option('Not configured', ''));
  Object.keys(state.settings.providers).forEach((id) => select.add(new Option(id, id)));
  select.value = selected;
}
function routeRow(name, title) {
  const route = state.settings.routes[name] || {}, row = element('div', undefined, 'route-row');
  row.dataset.route = name; row.append(element('h3', title));
  for (const [field, text, tag] of [['primary', 'Primary provider', 'select'], ['fallback', 'Fallback provider IDs', 'input'], ['max_output_tokens', 'Max output tokens', 'input']]) {
    const label = element('label', text), input = element(tag); input.dataset.field = field;
    if (field === 'primary') providerOptions(input, route.primary);
    else if (field === 'fallback') { input.value = (route.fallback || []).join(', '); input.placeholder = 'e.g. local, backup'; }
    else { input.type = 'number'; input.min = '16'; input.max = '16384'; input.step = '1'; input.value = route.max_output_tokens || 1024; input.required = true; }
    label.append(input); row.append(label);
  }
  return row;
}
function renderSettings() {
  const settings = state.settings, providers = $('#provider-rows'), overrides = $('#override-rows');
  providers.replaceChildren(); overrides.replaceChildren();
  for (const [id, profile] of Object.entries(settings.providers)) {
    const row = element('tr');
    [id, profile.kind === 'responses' ? 'Responses' : 'OpenAI compatible', profile.model, profile.api_key_env || 'Not required'].forEach((text) => row.append(element('td', text)));
    const cell = element('td'), actions = element('div', undefined, 'row-actions');
    actions.append(button('Edit', () => openProvider(id)), button('Remove', () => removeProvider(id)));
    cell.append(actions); row.append(cell); providers.append(row);
  }
  if (!providers.children.length) emptyRow(providers, 5, 'No providers yet. Add a local or hosted model to enable extraction.');
  $('#operation-routes').replaceChildren(routeRow('extract', 'Extract learning'), routeRow('consolidate', 'Consolidate memories'));
  for (const [id, route] of Object.entries(settings.routes).filter(([id]) => id.includes(':'))) {
    const row = element('tr'); row.append(element('td', id), element('td', [route.primary, ...route.fallback].join(' → ') + ` · ${route.max_output_tokens} tokens`));
    const cell = element('td'), actions = element('div', undefined, 'row-actions');
    actions.append(button('Edit', () => openOverride(id)), button('Remove', () => { collectSettings(); delete settings.routes[id]; markDirty(); renderSettings(); }));
    cell.append(actions); row.append(cell); overrides.append(row);
  }
  if (!overrides.children.length) emptyRow(overrides, 3, 'No overrides. Operations use their default route.');
  $('#daily-calls').value = settings.budgets.daily_calls;
  $('#daily-tokens').value = settings.budgets.daily_tokens;
  $('#daily-usd').value = settings.budgets.daily_usd;
  $('#schedule-enabled').checked = settings.schedule.enabled;
  $('#interval-hours').value = settings.schedule.interval_hours;
}
function parseFallback(value) { return value.split(',').map((id) => id.trim()).filter(Boolean); }
function collectSettings() {
  document.querySelectorAll('.route-row').forEach((row) => {
    const field = (name) => row.querySelector(`[data-field="${name}"]`).value;
    if (field('primary')) state.settings.routes[row.dataset.route] = { primary: field('primary'), fallback: parseFallback(field('fallback')), max_output_tokens: Number(field('max_output_tokens')) };
    else delete state.settings.routes[row.dataset.route];
  });
  state.settings.budgets = { daily_calls: Number($('#daily-calls').value), daily_tokens: Number($('#daily-tokens').value), daily_usd: Number($('#daily-usd').value) };
  state.settings.schedule = { enabled: $('#schedule-enabled').checked, interval_hours: Number($('#interval-hours').value) };
}
function openProvider(id = '') {
  collectSettings(); const form = $('#provider-form'); form.reset(); form.dataset.editId = id;
  $('#provider-error').hidden = true; $('#provider-title').textContent = id ? 'Edit provider' : 'Add provider';
  form.elements.id.value = id; form.elements.id.disabled = Boolean(id);
  if (id) Object.entries(state.settings.providers[id]).forEach(([field, value]) => { if (form.elements[field]) form.elements[field].value = value; });
  $('#provider-dialog').showModal();
}
function removeProvider(id) {
  collectSettings();
  const used = Object.entries(state.settings.routes).filter(([, route]) => [route.primary, ...route.fallback].includes(id)).map(([name]) => name);
  if (used.length) { notify(`Remove this provider from these routes first: ${used.join(', ')}.`, true); return; }
  delete state.settings.providers[id]; markDirty(); renderSettings();
}
function openOverride(id = '') {
  collectSettings(); const form = $('#override-form'); form.reset(); form.dataset.editId = id;
  $('#override-error').hidden = true; $('#override-title').textContent = id ? 'Edit override' : 'Add override';
  const route = state.settings.routes[id] || {};
  form.elements.id.value = id; form.elements.id.disabled = Boolean(id);
  providerOptions(form.elements.primary, route.primary);
  form.elements.fallback.value = (route.fallback || []).join(', ');
  form.elements.max_output_tokens.value = route.max_output_tokens || 1024;
  $('#override-dialog').showModal();
}
function dialogError(id, message) { $(id).textContent = message; $(id).hidden = false; }
function renderOperational(data) {
  const schedule = data.schedule || {}, facts = $('#schedule-status'); facts.replaceChildren();
  const result = schedule.last_result;
  const values = { Status: schedule.running ? 'Running' : schedule.enabled ? 'Scheduled' : 'Manual', 'Last run': timestamp(schedule.last_run_at), 'Next run': schedule.enabled ? timestamp(schedule.next_run_at) : 'Not scheduled', Result: result ? `${result.cleaned || 0} duplicates removed; ${result.proposals || 0} summaries proposed` : 'No completed run', 'Last error': schedule.last_error || 'None' };
  Object.entries(values).forEach(([label, value]) => facts.append(element('dt', label), element('dd', value)));
  const usage = data.usage || {}, grid = $('#usage'); grid.replaceChildren();
  [['Calls', number(usage.calls)], ['Tokens', number(usage.tokens)], ['Estimated USD', Number(usage.cost_usd || 0).toFixed(4)]].forEach(([label, value]) => { const item = element('div', undefined, 'usage-item'); item.append(element('span', label), element('strong', value)); grid.append(item); });
  const rows = $('#activity-rows'); rows.replaceChildren();
  for (const event of data.activity || []) {
    const row = element('tr'), tokens = Number(event.input_tokens || 0) + Number(event.output_tokens || 0);
    [timestamp(event.created_at), event.operation, `${event.provider} / ${event.model}`, [event.status, event.reason].filter(Boolean).join(' · '), `${number(tokens)}${event.estimated ? ' (est.)' : ''}`, Number(event.cost_usd || 0).toFixed(4)].forEach((value) => row.append(element('td', value)));
    rows.append(row);
  }
  if (!rows.children.length) emptyRow(rows, 6, 'No provider calls yet. Activity appears after extraction or model consolidation.');
}
async function refresh() {
  const query = new URLSearchParams({ scope: state.scope, inactive: String($('#inactive').checked) });
  const data = await request(`/api/state?${query}`);
  if (!state.dirty) { state.settings = data.settings; renderSettings(); }
  renderMemories(data.memories || []); renderOperational(data);
}

$('#provider-form').addEventListener('submit', (event) => {
  event.preventDefault(); const form = event.currentTarget, id = form.elements.id.value.trim();
  if (!form.dataset.editId && state.settings.providers[id]) { dialogError('#provider-error', 'This provider ID already exists.'); return; }
  const profile = {};
  for (const field of ['kind', 'base_url', 'api_key_env', 'model']) profile[field] = form.elements[field].value.trim();
  if (form.elements.reasoning_effort.value) profile.reasoning_effort = form.elements.reasoning_effort.value;
  for (const field of ['input_cost_per_million', 'output_cost_per_million']) if (form.elements[field].value !== '') profile[field] = Number(form.elements[field].value);
  state.settings.providers[id] = profile; markDirty(); renderSettings(); $('#provider-dialog').close(); notify('Provider applied. Save settings to use it.');
});
$('#override-form').addEventListener('submit', (event) => {
  event.preventDefault(); const form = event.currentTarget, id = form.elements.id.value.trim();
  if (!form.dataset.editId && state.settings.routes[id]) { dialogError('#override-error', 'This override already exists.'); return; }
  const route = { primary: form.elements.primary.value, fallback: parseFallback(form.elements.fallback.value), max_output_tokens: Number(form.elements.max_output_tokens.value) };
  const chain = [route.primary, ...route.fallback];
  if (chain.length > 8 || new Set(chain).size !== chain.length || chain.some((name) => !state.settings.providers[name])) { dialogError('#override-error', 'Use up to eight distinct configured provider IDs.'); return; }
  state.settings.routes[id] = route; markDirty(); renderSettings(); $('#override-dialog').close(); notify('Override applied. Save settings to use it.');
});
document.querySelectorAll('[data-close]').forEach((item) => item.addEventListener('click', () => document.getElementById(item.dataset.close).close()));
document.querySelectorAll('.save-settings').forEach((item) => item.addEventListener('click', () => {
  const invalid = [...document.querySelectorAll('#providers input, #consolidation input')].find((input) => !input.checkValidity());
  if (invalid) { location.hash = invalid.closest('.page').id; showPage(); invalid.reportValidity(); return; }
  collectSettings(); perform(async () => { await request('/api/settings', state.settings); markDirty(false); await refresh(); notify('Settings saved.'); });
}));
for (const id of ['providers', 'consolidation']) $( `#${id}`).addEventListener('input', () => markDirty());
$('#add-provider').addEventListener('click', () => openProvider());
$('#add-override').addEventListener('click', () => openOverride());
$('#refresh').addEventListener('click', () => perform(async () => { await refresh(); notify(state.dirty ? 'Activity and memory refreshed. Your unsaved settings are preserved.' : 'Up to date.'); }));
$('#scope-form').addEventListener('submit', (event) => { event.preventDefault(); state.scope = $('#scope').value.trim(); perform(refresh); });
$('#inactive').addEventListener('change', () => perform(refresh));
$('#remember-form').addEventListener('submit', (event) => {
  event.preventDefault(); const form = event.currentTarget;
  const payload = { title: form.elements.title.value.trim(), content: form.elements.content.value.trim(), scope: state.scope };
  if (form.elements.key.value.trim()) payload.key = form.elements.key.value.trim();
  perform(async () => { await request('/api/learn', payload); form.reset(); await refresh(); notify('Memory saved.'); });
});
$('#extract-form').addEventListener('submit', (event) => {
  event.preventDefault(); const form = event.currentTarget;
  const payload = { messages: [{ role: 'user', content: form.elements.content.value }], scope: state.scope };
  if (form.elements.route_key.value.trim()) payload.route_key = form.elements.route_key.value.trim();
  perform(async () => { notify('Extracting learnings with your configured provider…'); const result = await request('/api/extract', payload); await refresh(); notify(`${(result.learned || []).length} learnings saved; ${result.rejected || 0} unsupported candidates skipped.`); });
});
$('#run-consolidation').addEventListener('click', () => perform(async () => { notify('Running consolidation…'); const result = await request('/api/consolidate', { scope: state.scope }); await refresh(); notify(`Consolidation complete: ${result.cleaned || 0} duplicates removed; ${result.proposals || 0} summaries proposed.`); }));
window.addEventListener('hashchange', showPage);
window.addEventListener('beforeunload', (event) => { if (state.dirty) { event.preventDefault(); event.returnValue = ''; } });
showPage(); perform(refresh);
