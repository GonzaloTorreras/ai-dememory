'use strict';
const $ = (selector) => document.querySelector(selector);
const state = { settings: null, credentials: {}, modules: [], dirty: false, busy: false, scope: 'global', sources: [] };
const providerPresets = {
  codex: { kind: 'codex', base_url: '', auth: 'chatgpt', api_key_env: '' },
  openai: { kind: 'responses', base_url: 'https://api.openai.com/v1', auth: 'session', api_key_env: 'OPENAI_API_KEY' },
  anthropic: { kind: 'anthropic', base_url: 'https://api.anthropic.com/v1', auth: 'session', api_key_env: 'ANTHROPIC_API_KEY' },
  local: { kind: 'openai_compatible', base_url: 'http://localhost:11434/v1', auth: 'none', api_key_env: '' },
  custom: { kind: 'openai_compatible', base_url: '', auth: 'environment', api_key_env: '' },
};
function profileAuth(profile) { return profile.auth || (profile.api_key_env ? 'environment' : 'none'); }
const pages = {
  memory: ['Memory', 'Useful knowledge, with its source and scope.'],
  providers: ['Providers & routing', 'Choose how learning and consolidation run.'],
  sources: ['Local conversation sources', 'Your conversations, organized by workspace.'],
  modules: ['Modules', 'Keep only the capabilities you need.'],
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
  if (!response.ok || data.error) throw new Error(data.message || data.error || `Request failed (${response.status})`);
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
    updateSourceSelection();
    if ($('#provider-dialog').open) { updateProviderFields(); $('#provider-form').elements.id.disabled = Boolean($('#provider-form').dataset.editId); }
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
    const auth = profileAuth(profile), credential = state.credentials[id];
    const label = auth === 'chatgpt' ? 'Codex subscription (check sign-in)' : auth === 'session' ? (credential?.configured ? 'Session key set (not verified)' : 'Session key needed') : auth === 'environment' ? `${profile.api_key_env} (${credential?.configured ? 'set' : 'missing'})` : 'No authentication';
    [id, { codex: 'Codex subscription', responses: 'OpenAI Responses', anthropic: 'Anthropic Messages', openai_compatible: 'OpenAI compatible' }[profile.kind] || profile.kind, profile.model, label].forEach((text) => row.append(element('td', text)));
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
  $('#schedule-scope').value = settings.schedule.scope;
}
function parseFallback(value) { return value.split(',').map((id) => id.trim()).filter(Boolean); }
function collectSettings() {
  document.querySelectorAll('.route-row').forEach((row) => {
    const field = (name) => row.querySelector(`[data-field="${name}"]`).value;
    if (field('primary')) state.settings.routes[row.dataset.route] = { primary: field('primary'), fallback: parseFallback(field('fallback')), max_output_tokens: Number(field('max_output_tokens')) };
    else delete state.settings.routes[row.dataset.route];
  });
  state.settings.budgets = { daily_calls: Number($('#daily-calls').value), daily_tokens: Number($('#daily-tokens').value), daily_usd: Number($('#daily-usd').value) };
  state.settings.schedule = { enabled: $('#schedule-enabled').checked, interval_hours: Number($('#interval-hours').value), scope: $('#schedule-scope').value.trim() };
}
function openProvider(id = '') {
  collectSettings(); const form = $('#provider-form'); form.reset(); form.dataset.editId = id; form.dataset.suggestedId = '';
  $('#provider-error').hidden = true; $('#provider-title').textContent = id ? 'Edit provider' : 'Add provider';
  form.elements.id.value = id; form.elements.id.disabled = Boolean(id);
  $('#provider-models').replaceChildren(); $('#provider-advanced').open = false;
  $('#models-status').textContent = 'Load the provider model list, or enter an exact model ID manually.';
  if (id) {
    const profile = state.settings.providers[id];
    Object.entries(profile).forEach(([field, value]) => { if (form.elements[field]) form.elements[field].value = value; });
    form.elements.auth.value = profileAuth(profile);
    form.elements.preset.value = Object.keys(providerPresets).find((name) => providerPresets[name].kind === profile.kind && providerPresets[name].base_url === profile.base_url) || 'custom';
  } else applyProviderPreset();
  updateProviderFields();
  $('#provider-dialog').showModal();
}
function applyProviderPreset() {
  const form = $('#provider-form'), preset = providerPresets[form.elements.preset.value];
  Object.entries(preset).forEach(([field, value]) => { form.elements[field].value = value; });
  form.elements.api_key.value = ''; form.elements.model.value = ''; form.elements.reasoning_effort.value = '';
  form.elements.input_cost_per_million.value = ''; form.elements.output_cost_per_million.value = '';
  $('#provider-models').replaceChildren(); $('#models-status').textContent = 'Load available models for this provider after choosing authentication.';
  if (!form.dataset.editId && (!form.elements.id.value || form.elements.id.value === form.dataset.suggestedId)) {
    form.dataset.suggestedId = form.elements.preset.value.replace('plugin:', '') + '-learning';
    form.elements.id.value = form.dataset.suggestedId;
  }
  updateProviderFields();
}
function updateProviderFields() {
  const form = $('#provider-form'), auth = form.elements.auth.value, anthropic = form.elements.kind.value === 'anthropic', codex = form.elements.kind.value === 'codex';
  $('#codex-login').hidden = !codex; $('#provider-auth-field').hidden = codex;
  $('#custom-endpoint-fields').hidden = form.elements.preset.value !== 'custom' && form.elements.preset.value !== 'local';
  $('#preset-endpoint-help').hidden = !$('#custom-endpoint-fields').hidden;
  form.elements.base_url.required = !codex;
  $('#provider-prices').hidden = codex;
  for (const id of ['codex-device', 'codex-browser', 'codex-check', 'codex-cancel']) $('#' + id).hidden = !moduleEnabled('codex-subscription');
  $('#enable-codex').hidden = moduleEnabled('codex-subscription');
  $('#load-models').disabled = codex && !moduleEnabled('codex-subscription');
  $('#session-key-field').hidden = $('#session-key-help').hidden = auth !== 'session';
  $('#environment-key-field').hidden = $('#environment-key-help').hidden = auth !== 'environment';
  form.elements.api_key.disabled = auth !== 'session';
  if (auth !== 'session') form.elements.api_key.value = '';
  form.elements.api_key_env.disabled = auth !== 'environment'; form.elements.api_key_env.required = auth === 'environment';
  form.elements.reasoning_effort.disabled = anthropic; $('#reasoning-help').hidden = !anthropic;
  if (anthropic) form.elements.reasoning_effort.value = '';
  const id = form.dataset.editId, credential = state.credentials[id];
  $('#credential-status').textContent = auth === 'session' && credential?.mode === 'session' && credential.configured ? 'A session key is set. Leave blank to keep it, or paste a replacement. Endpoint changes require a new key.' : '';
  $('#clear-provider-key').hidden = !(auth === 'session' && credential?.mode === 'session' && credential.configured);
}
function providerDraft() {
  const form = $('#provider-form'), profile = {};
  for (const field of ['kind', 'base_url', 'api_key_env', 'model', 'auth']) profile[field] = form.elements[field].value.trim();
  if (profile.auth !== 'environment') profile.api_key_env = '';
  if (form.elements.reasoning_effort.value) profile.reasoning_effort = form.elements.reasoning_effort.value;
  if (profile.kind !== 'codex') for (const field of ['input_cost_per_million', 'output_cost_per_million']) if (form.elements[field].value !== '') profile[field] = Number(form.elements[field].value);
  return profile;
}
function moduleEnabled(id) { return state.modules.some((item) => item.module_id === id && item.enabled); }
function renderModules(data) {
  state.modules = data.modules || [];
  const list = $('#module-list'); list.replaceChildren();
  for (const item of state.modules) {
    if (item.module_id === 'harness') continue;
    const card = element('article', undefined, 'memory-card');
    const enabled = item.enabled || (item.module_id.startsWith('harness-') && moduleEnabled('harness'));
    card.append(element('h2', item.module_id), element('p', item.summary), element('p', enabled ? 'Enabled' : 'Disabled', 'hint'));
    if (item.module_id !== 'workbench') card.append(button(enabled ? 'Disable' : 'Enable', () => {
      if (!item.enabled && !item.builtin && !confirm('Enable this installed Python plugin? It can access files and the network as your user.')) return;
      perform(async () => { await request('/api/modules', { id: item.module_id, enabled: !enabled }); await refresh(); notify('Module state saved.'); });
    }));
    list.append(card);
  }
  const enabled = moduleEnabled('sources');
  $('#enable-sources').hidden = enabled; $('#source-controls').hidden = !enabled;
  if (!enabled) { state.sources = []; $('#source-files').replaceChildren(); }
  const form = $('#provider-form'), selected = form.elements.preset.value, selectedKind = form.elements.kind.value;
  document.querySelectorAll('#provider-form option[data-plugin]').forEach((option) => option.remove());
  for (const key of Object.keys(providerPresets)) if (key.startsWith('plugin:')) delete providerPresets[key];
  for (const extension of data.provider_extensions || []) {
    const {kind, label, base_url, auth} = extension;
    providerPresets[kind] = {kind, base_url, auth, api_key_env: ''};
    const preset = new Option(label + ' (plugin)', kind); preset.dataset.plugin = 'true'; form.elements.preset.add(preset);
    const protocol = new Option(label, kind); protocol.dataset.plugin = 'true'; form.elements.kind.add(protocol);
  }
  form.elements.preset.value = selected || 'codex';
  form.elements.kind.value = selectedKind;
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
  const values = { Status: schedule.running ? 'Running' : schedule.enabled ? 'Scheduled' : 'Manual', 'Scheduled scope': schedule.scope || 'global', 'Last run': timestamp(schedule.last_run_at), 'Last run scope': schedule.last_run_scope || 'No run yet', 'Next run': schedule.enabled ? timestamp(schedule.next_run_at) : 'Not scheduled', Result: result ? `${result.cleaned || 0} duplicates removed; ${result.proposals || 0} summaries proposed` : 'No completed run', 'Last error': schedule.last_error || 'None' };
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
  state.credentials = data.credentials || {};
  renderModules(data);
  const scopes = [...new Set([...(data.scopes || ['global']), state.scope])];
  $('#scope-selector').replaceChildren(...scopes.map(name => new Option(name, name)));
  $('#scope-selector').value = state.scope;
  $('#scope-options').replaceChildren(...scopes.map(name => new Option(name, name)));
  $('#run-consolidation').textContent = `Run now in ${state.scope}`;
  renderSourceSchedules(data.source_schedules || []);
  state.codexRoot = data.codex_sessions_root;
  if (!state.dirty) { state.settings = data.settings; renderSettings(); }
  renderMemories(data.memories || []); renderOperational(data);
}

$('#provider-form').addEventListener('submit', (event) => {
  event.preventDefault(); const form = event.currentTarget, id = form.elements.id.value.trim();
  if (!form.dataset.editId && state.settings.providers[id]) { dialogError('#provider-error', 'This provider ID already exists.'); return; }
  const profile = providerDraft();
  let key = form.elements.api_key.value;
  const previous = state.settings.providers[id];
  const keepsKey = state.credentials[id]?.mode === 'session' && state.credentials[id].configured && previous?.kind === profile.kind && previous?.base_url === profile.base_url && profileAuth(previous) === profile.auth;
  if (profile.auth === 'session' && !key && !keepsKey) { dialogError('#provider-error', 'Enter an API key for this session, or choose an environment variable.'); return; }
  state.settings.providers[id] = profile; markDirty();
  form.elements.api_key.value = '';
  perform(async () => {
    let saved = false;
    try {
      await request('/api/settings', state.settings); saved = true;
      if (profile.auth === 'session' && key) await request('/api/credentials', { provider: id, api_key: key, expected: { kind: profile.kind, base_url: profile.base_url, auth: profile.auth } });
      markDirty(false); await refresh(); $('#provider-dialog').close(); notify('Provider and settings saved. No model call was made.');
    } catch (error) {
      if (saved) {
        form.dataset.editId = id; markDirty(false); delete state.credentials[id];
        $('#provider-title').textContent = 'Edit provider';
      } else if (previous) state.settings.providers[id] = previous;
      else delete state.settings.providers[id];
      renderSettings();
      dialogError('#provider-error', `${saved ? 'Provider settings saved. Finish credential setup or refresh: ' : ''}${error.message}`);
    } finally { key = ''; }
  }).then(() => { form.elements.id.disabled = Boolean(form.dataset.editId); updateProviderFields(); });
});
$('#provider-form').elements.preset.addEventListener('change', applyProviderPreset);
$('#provider-form').elements.auth.addEventListener('change', updateProviderFields);
$('#provider-form').elements.kind.addEventListener('change', updateProviderFields);
for (const name of ['auth', 'kind', 'base_url', 'api_key', 'api_key_env']) {
  $('#provider-form').elements[name].addEventListener('input', () => {
    $('#provider-models').replaceChildren();
    $('#models-status').textContent = 'Provider connection changed. Load models again, or enter an exact model ID.';
  });
}
$('#load-models').addEventListener('click', () => {
  const form = $('#provider-form'), profile = providerDraft();
  profile.model ||= 'catalog-request';
  let key = form.elements.api_key.value;
  perform(async () => {
    try {
      const result = await request('/api/provider-models', {profile, provider:form.dataset.editId || '', api_key:key});
      $('#provider-models').replaceChildren(...result.models.map((id) => new Option(id, id)));
      $('#models-status').textContent = `${result.models.length} models returned by this provider. Choose a text-generation model your account supports, or enter an ID manually.`;
    } catch (error) { $('#models-status').textContent = `Could not list models: ${error.message}. You can still enter an exact model ID manually.`; }
    finally { key = ''; }
  });
});
function enableBuiltin(id) {
  perform(async () => { await request('/api/modules', {id, enabled:true}); await refresh(); notify('Optional module enabled.'); }).then(updateProviderFields);
}
$('#enable-codex').addEventListener('click', () => enableBuiltin('codex-subscription'));
$('#enable-sources').addEventListener('click', () => enableBuiltin('sources'));
function renderLogin(result) {
  $('#codex-auth-status').textContent = result.authenticated ? 'Signed in with ChatGPT. You can now load Codex models.' : result.message || result.error || (result.pending ? 'Waiting for you to complete official sign-in.' : 'Not signed in.');
  const link = $('#codex-auth-link'), raw = result.verification_url || result.auth_url || '';
  link.hidden = true; link.removeAttribute('href');
  if (raw) {
    const url = new URL(raw);
    if (url.protocol === 'https:' && ['auth.openai.com', 'auth0.openai.com', 'chatgpt.com'].includes(url.hostname)) { link.href = url.href; link.hidden = false; }
  }
  $('#codex-user-code').textContent = result.user_code ? `Device code: ${result.user_code}` : '';
}
for (const method of ['device','browser']) $('#codex-' + method).addEventListener('click', () => perform(async () => {
  renderLogin({message: 'Starting official Codex sign-in…'});
  try { renderLogin({...await request('/api/codex/login', {method}), pending:true}); }
  catch (error) { renderLogin({message: error.message}); }
}));
$('#codex-check').addEventListener('click', () => perform(async () => {
  try { renderLogin(await request('/api/codex/status', {})); } catch (error) { renderLogin({message: error.message}); }
}));
$('#codex-cancel').addEventListener('click', () => perform(async () => { await request('/api/codex/cancel', {}); renderLogin({}); }));
$('#provider-dialog').addEventListener('close', () => { $('#provider-form').elements.api_key.value = ''; });
$('#clear-provider-key').addEventListener('click', () => perform(async () => {
  await request('/api/credentials', { provider: $('#provider-form').dataset.editId, api_key: '' });
  await refresh(); updateProviderFields(); notify('Session key cleared.');
}));
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
function changeScope(value) {
  if (!/^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$/.test(value)) { notify('Use a short scope name, such as global or project:your-project.', true); return; }
  state.scope = value; $('#scope').value = value;
  state.sources.forEach(item => { item.preview = null; item.result = ''; item.open = false; }); renderSources(); perform(refresh);
}
$('#scope-form').addEventListener('submit', (event) => { event.preventDefault(); changeScope($('#scope').value.trim()); });
$('#scope-selector').addEventListener('change', event => changeScope(event.target.value));
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
$('#source-form').addEventListener('submit', (event) => {
  event.preventDefault(); const form = event.currentTarget, root = form.elements.root.value.trim(), format = form.elements.format.value;
  perform(async () => {
    const result = await request('/api/sources/list', {root, format});
    state.sources = result.files.map(file => ({...file, root, format, selected:false, preview:null}));
    renderSources();
    for (const notice of result.notices || []) $('#source-files').append(element('p', notice, 'hint'));
    notify(`${result.files.length} conversations found${result.truncated ? ' (bounded scan; select a narrower folder for more)' : ''}. No content sent to a model.`);
  });
});
function updateSourceSelection() {
  const selected = state.sources.filter(item => item.selected);
  const ready = selected.length > 0 && selected.every(item => item.preview?.messages.length && item.preview.destinations.length);
  $('#extract-source').disabled = state.busy || !ready;
  $('#preview-selected').disabled = state.busy || !selected.length;
  $('#source-selection').textContent = `${selected.length} selected · destination ${state.scope}. Preview each selected conversation before extracting. Each conversation uses its own bounded model call.`;
}
async function previewItem(item) {
  item.preview = await request('/api/sources/preview', {root:item.root,format:item.format,file:item.path,session_id:item.session_id,scope:state.scope});
  item.open = true; renderSources();
}
function renderSources() {
  const list = $('#source-files'); list.replaceChildren();
  const query = $('#source-search').value.toLowerCase();
  for (const item of state.sources) {
    const modified = item.last_message_at ?? item.modified_at;
    const title = item.title || `Conversation · ${new Date(modified*1000).toLocaleDateString()}`;
    if (![title,item.workspace || '',item.path].join(' ').toLowerCase().includes(query)) continue;
    const card = element('article', undefined, 'source-card');
    const check = element('input'); check.type = 'checkbox'; check.checked = item.selected; check.setAttribute('aria-label', `Select ${title}`);
    check.onchange = () => { if (check.checked && state.sources.filter(row => row.selected).length >= 10) { check.checked = false; notify('Select up to ten conversations per batch.',true); return; } item.selected = check.checked; updateSourceSelection(); };
    const details = element('details'); details.open = Boolean(item.open);
    const summary = element('summary'); summary.append(element('strong',title),element('span',`${new Date(modified*1000).toLocaleString()} · ${item.workspace || item.format}`, 'hint'));
    details.append(summary);
    details.ontoggle = () => { item.open = details.open; if(details.open && !item.preview && !state.busy) perform(()=>previewItem(item)); };
    details.append(element('p',item.path,'source-path'),button(item.preview ? 'Refresh preview' : 'Preview user messages',()=>perform(()=>previewItem(item))));
    if (item.preview) {
      const p = item.preview;
      details.append(element('p',`${p.messages.length} user messages → ${p.scope} · ${p.destinations.join(' → ') || 'No extraction route configured'}`, 'hint'));
      details.append(element('pre',p.messages.map((message,i)=>`${i+1}. ${message.content}`).join('\n\n') || 'No eligible human messages.', 'conversation-preview'));
      if (p.truncated || p.notice) details.append(element('p',[p.truncated?'Latest bounded window; older messages are not included.':'',p.notice || ''].join(' '),'hint'));
      const diagnostics = element('details'); diagnostics.append(element('summary','Reader details'),element('p',Object.entries(p.counts || {}).map(([k,v])=>`${k.replaceAll('_',' ')}: ${v}`).join(' · '),'hint')); details.append(diagnostics);
    }
    if (item.result) details.append(element('p',item.result,'notice'));
    card.append(check,details); list.append(card);
  }
  if (!list.children.length) list.append(element('p','No matching conversations. Choose a folder or change the filter.','hint'));
  updateSourceSelection();
}
$('#source-search').addEventListener('input', renderSources);
$('#codex-default-root').addEventListener('click',()=>{const form=$('#source-form');form.elements.root.value=state.codexRoot || '';form.elements.format.value='codex';state.sources=[];renderSources();updateSourceMode();});
for(const field of ['root','format']) $('#source-form').elements[field].addEventListener('change',()=>{state.sources=[];renderSources();});
$('#preview-selected').addEventListener('click',()=>perform(async()=>{for (const item of state.sources.filter(item=>item.selected)) await previewItem(item);}));
$('#extract-source').addEventListener('click', () => perform(async () => {
  await request('/api/sources/validate',{tokens:state.sources.filter(item=>item.selected).map(item=>item.preview?.preview_token)});
  for (const item of state.sources.filter(item=>item.selected)) {
    if (!item.preview) throw new Error('Preview all selected conversations first.');
    try { const result = await request('/api/sources/extract',{preview_token:item.preview.preview_token,confirmed:true}); item.result = `${(result.learned || []).length} learnings saved to ${item.preview.scope}`; item.selected = false; }
    catch (error) { item.result = error.message; renderSources(); throw error; }
  }
  renderSources(); await refresh(); notify('Selected conversations processed. Results are shown inline.');
}));
$('#source-schedule-form').addEventListener('submit', event=>{
  event.preventDefault(); const form = event.currentTarget, source = $('#source-form');
  perform(async()=>{await request('/api/source-schedules/save',{root:source.elements.root.value.trim(),format:source.elements.format.value,mode:form.elements.mode.value,scope:state.scope,interval_hours:Number(form.elements.interval_hours.value),enabled:form.elements.enabled.checked,confirmed:form.elements.enabled.checked}); await refresh(); notify('Source schedule saved. No extraction was started.');});
});
function updateSourceMode() {
  const select = $('#source-schedule-form').elements.mode, codex = $('#source-form').elements.format.value === 'codex';
  select.querySelector('[value="history"]').disabled = !codex;
  if (!codex) select.value = 'recent';
  $('#source-mode-help').textContent = select.value === 'history'
    ? 'Reads native Codex human events in order, saves progress across restarts, and revisits files for new messages. Mirrored messages and internal sessions are excluded. Older response-only exports require manual preview. Discovery is bounded to 5,000 entries / four directory levels; choose a smaller dated folder if a limit is reported.'
    : 'Recent activity reads the latest bounded window in the 100 most recent conversations, not the entire history.';
}
$('#source-form').elements.format.addEventListener('change', updateSourceMode);
$('#source-schedule-form').elements.mode.addEventListener('change', updateSourceMode);
updateSourceMode();
function renderSourceSchedules(rules) {
  const list=$('#source-schedules'); list.replaceChildren();
  for (const rule of rules) {
    const card=element('article',undefined,'memory-card');
    card.append(element('h3',`${rule.format} → ${rule.scope}`),element('p',rule.root,'source-path'),element('p',`${rule.enabled?'Enabled':'Paused'} · every ${rule.interval_hours}h · ${rule.last_result}${rule.enabled?' · next '+new Date(rule.next_run*1000).toLocaleString():''}`,'hint'));
    if (rule.mode === 'history') {
      const p = rule.progress || {};
      card.append(element('p',`History and new messages · ${p.messages || 0} user messages in ${p.windows || 0} windows · ${p.tracked_conversations || 0} conversations tracked · ${p.passes || 0} discovery passes completed`));
      card.append(element('p',p.waiting_for_newline ? 'Waiting for a complete final line; other conversations can still advance.' : p.bytes_remaining ? `${p.bytes_remaining.toLocaleString()} bytes remain in the current conversation.` : 'Progress saved. Next run continues discovery and checks for new messages.','hint'));
      if (p.scan_limited) card.append(element('p','Discovery limit reached. This is not the whole archive; choose a smaller dated folder.','hint'));
      if (p.source_warning) card.append(element('p',p.source_warning,'hint'));
      const d = p.last_discards;
      if (d) card.append(element('p',`Last window skipped: ${d.malformed} malformed records, ${d.sensitive} sensitive messages, ${d.oversize} oversized messages; ${d.ignored} non-user/internal records ignored.`,'hint'));
    } else card.append(element('p','Recent activity · latest bounded windows only','hint'));
    if (rule.source_warning) card.append(element('p',rule.source_warning,'hint'));
    card.append(button('Run now',()=>{if(confirm('Send one changed conversation window to this harness extraction route? Provider charges may apply.')) perform(async()=>{await request('/api/source-schedules/run',{id:rule.id,confirmed:true}); await refresh();});}));
    if(rule.enabled) card.append(button('Pause',()=>perform(async()=>{await request('/api/source-schedules/change',{id:rule.id,action:'pause'}); await refresh();})));
    else card.append(button('Resume',()=>{if(confirm('Enable automatic extraction from this folder into this scope using the configured route and fallbacks?')) perform(async()=>{await request('/api/source-schedules/change',{id:rule.id,action:'resume',confirmed:true}); await refresh();});}));
    card.append(button('Remove schedule',()=>perform(async()=>{await request('/api/source-schedules/change',{id:rule.id,action:'delete'}); await refresh();}))); list.append(card);
  }
}
$('#run-consolidation').addEventListener('click', () => perform(async () => { notify(`Running consolidation in ${state.scope}…`); const result = await request('/api/consolidate', { scope: state.scope }); await refresh(); notify(`Consolidation in ${result.scope} complete: ${result.cleaned || 0} duplicates removed; ${result.proposals || 0} summaries proposed.`); }));
window.addEventListener('hashchange', showPage);
window.addEventListener('beforeunload', (event) => { if (state.dirty) { event.preventDefault(); event.returnValue = ''; } });
showPage(); perform(refresh);
