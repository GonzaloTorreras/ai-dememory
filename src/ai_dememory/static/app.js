'use strict';
const $ = (selector) => document.querySelector(selector);
const state = { settings: null, credentials: {}, modules: [], dirty: false, busy: false, scope: 'global', scopeLabels: {}, sources: [], recallRevision: 0, scopes: [], providerExtensions: [], memories: [], judgmentRevision: 0, judgmentMemory: null };
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
  if (value) {
    state.jevEvaluationKey = null;
    $('#jev-evaluation-confirm').checked = false;
    $('#run-jev-evaluation').disabled = true;
  }
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
function scopeLabel(scope = 'global') {
  if (Object.hasOwn(state.scopeLabels, scope)) return state.scopeLabels[scope];
  if (scope === 'global') return 'Global · shared';
  const name = scope.replace(/^project:/, '');
  return /^[a-f0-9]{32}$/.test(name) ? 'Unnamed project' : name;
}
function importanceOptions(selected = 'normal') {
  const select = element('select');
  for (const value of ['low', 'normal', 'high']) select.add(new Option(value[0].toUpperCase() + value.slice(1), value));
  select.value = ['low', 'normal', 'high'].includes(selected) ? selected : 'normal';
  return select;
}
function memoryKindOptions(selected = 'unspecified') {
  const select = element('select');
  for (const [value, label] of [['unspecified', 'Unspecified'], ['durable', 'Durable lesson'], ['episode', 'Episode or status']]) select.add(new Option(label, value));
  select.value = ['unspecified', 'durable', 'episode'].includes(selected) ? selected : 'unspecified';
  return select;
}
function localDateTime(value) {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  const part = (number) => String(number).padStart(2, '0');
  return `${date.getFullYear()}-${part(date.getMonth() + 1)}-${part(date.getDate())}T${part(date.getHours())}:${part(date.getMinutes())}`;
}
function isoDateTime(value) {
  if (!value) return null;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date.toISOString();
}
function confidenceLabel(memory) {
  const confidence = memory.confidence && typeof memory.confidence === 'object' ? memory.confidence : {};
  const label = confidence.label || confidence.assessment_label || memory.confidence_label;
  if (typeof label === 'string' && label.trim()) return label.trim().slice(0, 120);
  const status = confidence.status || memory.confidence_status;
  return confidenceStatusLabel(status);
}
function confidenceStatusLabel(status) {
  if (status === 'advisory') return 'Advisory assessment';
  if (status === 'not_used') return 'Advisory assessment (not used for ranking)';
  if (status === 'stale') return 'Assessment stale';
  return 'Not assessed';
}
function matchingReason(memory) {
  const details = memory.details && typeof memory.details === 'object' ? memory.details : memory;
  const matchingTerms = Array.isArray(details.matching_terms) ? details.matching_terms : [];
  if (!matchingTerms.length) return '';
  const terms = matchingTerms.slice(0, 6).map((term) => String(term).slice(0, 80)).filter(Boolean);
  return terms.length ? `Matched on: ${terms.join(', ')}` : '';
}
function priorityOriginLabel(origin) {
  if (origin === 'user') return 'set by you';
  if (origin === 'host') return 'host suggestion';
  return 'default';
}
function recallReason(details) {
  const reasons = [matchingReason({ details })].filter(Boolean);
  const importance = ['low', 'normal', 'high'].includes(details.importance) ? details.importance : 'normal';
  const origin = details.importance_origin || details.origin || 'default';
  if (origin === 'host') reasons.push(`Priority suggestion: ${importance[0].toUpperCase() + importance.slice(1)} (not weighted)`);
  else {
    const weight = Number.isFinite(details.importance_weight) ? ` · weight ${details.importance_weight}` : '';
    reasons.push(`Priority: ${importance[0].toUpperCase() + importance.slice(1)} · ${priorityOriginLabel(origin)}${weight}`);
  }
  reasons.push(`Confidence: ${confidenceStatusLabel(details.confidence_status)}`);
  if (details.match_fields?.includes('source_excerpt')) reasons.push('Original evidence wording matched');
  if (details.jev?.language) reasons.push(`Language: ${details.jev.language.verdict} (advisory)`);
  if (details.jev?.usefulness) reasons.push(`Usefulness: ${judgmentNumber(details.jev.usefulness.probability)} (not weighted)`);
  return reasons.join(' · ');
}
function clearRecallResults() {
  state.recallRevision += 1;
  const list = $('#recall-results'); list.replaceChildren(); list.hidden = true;
}
function renderRecallResults(hits, scope) {
  const list = $('#recall-results'); list.replaceChildren(); list.hidden = false;
  if (!hits.length) { list.append(element('p', `No useful matches in ${scopeLabel(scope)}.`, 'memory-empty')); return; }
  for (const hit of hits) {
    const card = element('article', undefined, 'memory-card recall-result');
    card.append(element('h3', hit.title || 'Untitled memory'), element('p', hit.snippet || 'No preview available.'));
    const details = hit.details && typeof hit.details === 'object' ? hit.details : {};
    card.append(element('p', recallReason(details), 'hint'));
    list.append(card);
  }
}
function renderMemories(memories) {
  const list = $('#memory-list'); list.replaceChildren();
  if (!memories.length) list.append(element('p', 'No memories in this scope yet. Save something useful below.', 'memory-empty'));
  for (const memory of memories) {
    const card = element('article', undefined, 'memory-card'), header = element('header');
    const status = memory.status || 'active';
    header.append(element('h2', memory.title), element('span', status, `badge ${status === 'provisional' ? 'provisional' : status === 'active' ? '' : 'inactive'}`));
    card.append(header, element('p', memory.content));
    const source = memory.source || {};
    const metadata = [scopeLabel(memory.scope), source.provider || 'direct', source.evidence_kind || 'saved memory', timestamp(memory.created_at)];
    if (memory.key) metadata.push(`Key: ${memory.key}`);
    if (memory.memory_kind && memory.memory_kind !== 'unspecified') metadata.push(memory.memory_kind === 'episode' ? 'Episode' : 'Durable lesson');
    if (memory.expires_at) metadata.push(`Expires: ${timestamp(memory.expires_at)}`);
    card.append(element('p', metadata.join(' · '), 'hint'));
    const reason = matchingReason(memory);
    if (reason) card.append(element('p', reason, 'hint'));
    const quality = element('div', undefined, 'memory-quality');
    const priority = importanceOptions(memory.importance || 'normal');
    const priorityLabel = element('label', 'Priority'); priorityLabel.append(priority);
    const kind = memoryKindOptions(memory.memory_kind);
    const kindLabel = element('label', 'Memory kind'); kindLabel.append(kind);
    const originalExpiryLocal = localDateTime(memory.expires_at);
    const expiry = element('input'); expiry.type = 'datetime-local'; expiry.value = originalExpiryLocal;
    const expiryLabel = element('label', 'Expires at'); expiryLabel.append(expiry);
    const origin = memory.importance_origin || 'default';
    const priorityNote = origin === 'host' ? `Host suggestion: ${priority.value[0].toUpperCase() + priority.value.slice(1)}. Save priority to apply it as your setting.` : `Priority is ${priorityOriginLabel(origin)} and is not truth.`;
    quality.append(priorityLabel, kindLabel, expiryLabel, element('p', `Confidence: ${confidenceLabel(memory)}. ${priorityNote} Expiry hides a memory from normal recall; it does not delete it.`, 'hint quality-note'));
    const savePriority = async (reset = false) => {
      if (reset) priority.value = 'normal';
      const payload = { memory_id: memory.memory_id, scope: memory.scope || state.scope, importance: priority.value };
      if (!reset) {
        payload.memory_kind = kind.value;
        payload.expires_at = expiry.value === originalExpiryLocal ? memory.expires_at || null : isoDateTime(expiry.value);
      }
      await request('/api/memory/quality', payload);
      await refresh(); notify(reset ? 'Priority reset to Normal.' : 'Priority saved.');
    };
    const qualityActions = element('div', undefined, 'actions');
    qualityActions.append(button('Save changes', () => perform(() => savePriority())), button('Reset priority', () => perform(() => savePriority(true))));
    if (moduleEnabled('jev')) {
      const evaluate = button('Evaluate evidence preview', () => openJudgment(memory));
      if (!source.excerpt) { evaluate.disabled = true; evaluate.title = 'No source excerpt for an evidence-support check.'; }
      qualityActions.append(evaluate);
      const skills = state.settings?.module_settings?.jev;
      if (skills?.language || skills?.usefulness) qualityActions.append(button('Assess language / usefulness', () => openJudgment(memory, true)));
    }
    quality.append(qualityActions); card.append(quality);
    const details = element('details');
    details.append(element('summary', 'Source & technical details'));
    if (source.excerpt) details.append(element('p', source.excerpt));
    details.append(element('p', `Scope ID: ${memory.scope || 'global'}`, 'hint'));
    if (source.session) details.append(element('p', `Conversation ID: ${source.session}`, 'hint'));
    if (source.turn) details.append(element('p', `Turn ID: ${source.turn}`, 'hint'));
    card.append(details);
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
function providerCapabilities(profile) {
  if (!profile.kind?.startsWith('plugin:')) return ['generate'];
  return state.providerExtensions.find((extension) => extension.kind === profile.kind)?.capabilities || [];
}
function providerOptions(select, selected = '', capability = 'generate') {
  select.replaceChildren(new Option('Not configured', ''));
  const profiles = Object.entries(state.settings.providers);
  profiles.filter(([, profile]) => providerCapabilities(profile).includes(capability)).forEach(([id]) => select.add(new Option(id, id)));
  const selectedProfile = state.settings.providers[selected];
  if (selected && selectedProfile && !providerCapabilities(selectedProfile).includes(capability)) {
    const unavailable = new Option(`${selected} (unavailable/disabled)`, selected); unavailable.disabled = true; select.add(unavailable);
  }
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
    actions.append(button('Edit', () => openOverride(id)), button('Remove', () => { if (!collectOrNotify()) return; delete settings.routes[id]; markDirty(); renderSettings(); }));
    cell.append(actions); row.append(cell); overrides.append(row);
  }
  if (!overrides.children.length) emptyRow(overrides, 3, 'No overrides. Operations use their default route.');
  $('#daily-calls').value = settings.budgets.daily_calls;
  $('#daily-tokens').value = settings.budgets.daily_tokens;
  $('#daily-usd').value = settings.budgets.daily_usd;
  $('#importance-weight').value = Number.isFinite(settings.ranking?.importance_weight) ? settings.ranking.importance_weight : 0.15;
  $('#confidence-weight').value = 0;
  $('#episode-recall-days').value = settings.lifecycle?.episode_recall_days ?? 0;
  $('#project-summaries').checked = Boolean(settings.consolidation?.project_summaries);
  $('#schedule-enabled').checked = settings.schedule.enabled;
  $('#interval-hours').value = settings.schedule.interval_hours;
  $('#schedule-scope').value = settings.schedule.scope;
  $('#schedule-mode').value = settings.schedule.target_mode || 'fixed';
  $('#schedule-include-global').checked = Boolean(settings.schedule.include_global);
  renderJudgmentSettings(settings);
  updateScheduleTargetControls();
}
function renderJudgmentSettings(settings) {
  const config = settings.judgment || {}, selectedScopes = new Set(config.scopes || []), operations = new Set(config.operations || ['support']);
  providerOptions($('#judgment-primary'), config.primary || '', 'judge');
  $('#judgment-fallback').value = (config.fallback || []).join(', ');
  const scopes = $('#judgment-scopes'); scopes.replaceChildren(element('legend', 'Scopes allowed to request a judgment'));
  for (const scope of state.scopes) {
    const label = element('label', undefined, 'check'), input = element('input');
    input.type = 'checkbox'; input.value = scope; input.checked = selectedScopes.has(scope);
    label.append(input, document.createTextNode(scopeLabel(scope))); scopes.append(label);
  }
  $('#judgment-operations').querySelectorAll('input').forEach((input) => { input.checked = operations.has(input.value); });
  const skills = settings.module_settings?.jev || {};
  for (const name of ['language', 'usefulness', 'recall-tags', 'after-save']) $('#jev-' + name).checked = Boolean(skills[name.replaceAll('-', '_')]);
  $('#jev-languages').value = Object.entries(skills.languages || {es:'Spanish', en:'English'}).map(([code, name]) => `${code}=${name}`).join('\n');
  $('#jev-purpose').value = skills.purpose || '';
  const automatic = $('#jev-auto-scopes'); automatic.replaceChildren(element('legend', 'Explicit scopes for automatic external processing'));
  for (const scope of state.scopes) {
    const label = element('label', undefined, 'check'), input = element('input');
    input.type = 'checkbox'; input.value = scope; input.checked = (skills.automatic_scopes || []).includes(scope);
    label.append(input, document.createTextNode(scopeLabel(scope))); automatic.append(label);
  }
  $('#module-extra-json').value = JSON.stringify(Object.fromEntries(Object.entries(settings.module_settings || {}).filter(([id]) => id !== 'jev')), null, 2);
  $('#source-excerpt-recall').checked = settings.retrieval?.source_excerpt !== false;
}
function renderScheduleProjectTargets(scopes, schedule) {
  const list = $('#schedule-project-list'), selected = new Set(schedule.scopes || []);
  list.replaceChildren();
  const projects = scopes.filter((scope) => scope.startsWith('project:'));
  for (const scope of projects) {
    const label = element('label', undefined, 'check');
    const input = element('input'); input.type = 'checkbox'; input.value = scope; input.checked = selected.has(scope);
    label.append(input, document.createTextNode(scopeLabel(scope))); list.append(label);
  }
  if (!projects.length) list.append(element('p', 'No project scopes are known yet. Use a project scope above first.', 'hint'));
  updateScheduleTargetControls();
}
function updateScheduleTargetControls() {
  const mode = $('#schedule-mode').value, fixed = mode === 'fixed';
  $('#schedule-fixed-target').hidden = !fixed;
  $('#schedule-project-targets').hidden = fixed;
  $('#schedule-project-list').hidden = mode !== 'selected_projects';
}
function parseFallback(value) { return value.split(',').map((id) => id.trim()).filter(Boolean); }
function collectSettings() {
  const extra = JSON.parse($('#module-extra-json').value || '{}');
  if (!extra || typeof extra !== 'object' || Array.isArray(extra)) throw new Error('Other module settings must be a JSON object.');
  const languages = {};
  for (const line of $('#jev-languages').value.split('\n').map((value) => value.trim()).filter(Boolean)) {
    const separator = line.indexOf('='), code = line.slice(0, separator).trim(), name = line.slice(separator + 1).trim();
    if (separator < 1 || !name || Object.hasOwn(languages, code)) throw new Error('Use one unique language code=name per line.');
    languages[code] = name;
  }
  document.querySelectorAll('.route-row').forEach((row) => {
    const field = (name) => row.querySelector(`[data-field="${name}"]`).value;
    if (field('primary')) state.settings.routes[row.dataset.route] = { primary: field('primary'), fallback: parseFallback(field('fallback')), max_output_tokens: Number(field('max_output_tokens')) };
    else delete state.settings.routes[row.dataset.route];
  });
  state.settings.budgets = { daily_calls: Number($('#daily-calls').value), daily_tokens: Number($('#daily-tokens').value), daily_usd: Number($('#daily-usd').value) };
  state.settings.ranking = { ...(state.settings.ranking || {}), importance_weight: Number($('#importance-weight').value), confidence_weight: 0 };
  state.settings.lifecycle = { ...(state.settings.lifecycle || {}), episode_recall_days: Number($('#episode-recall-days').value) };
  state.settings.consolidation = { ...(state.settings.consolidation || {}), project_summaries: $('#project-summaries').checked };
  state.settings.judgment = { primary: $('#judgment-primary').value, fallback: parseFallback($('#judgment-fallback').value), scopes: [...document.querySelectorAll('#judgment-scopes input:checked')].map((input) => input.value), operations: [...document.querySelectorAll('#judgment-operations input:checked')].map((input) => input.value) };
  state.settings.retrieval = { source_excerpt: $('#source-excerpt-recall').checked };
  state.settings.module_settings = {...extra, jev:{language:$('#jev-language').checked, usefulness:$('#jev-usefulness').checked,
    recall_tags:$('#jev-recall-tags').checked, after_save:$('#jev-after-save').checked, languages, purpose:$('#jev-purpose').value,
    automatic_scopes:[...document.querySelectorAll('#jev-auto-scopes input:checked')].map((input) => input.value)}};
  const schedule = { enabled: $('#schedule-enabled').checked, interval_hours: Number($('#interval-hours').value), scope: $('#schedule-scope').value.trim() };
  const targetMode = $('#schedule-mode').value;
  if (targetMode !== 'fixed') {
    schedule.target_mode = targetMode;
    schedule.scopes = targetMode === 'selected_projects' ? [...document.querySelectorAll('#schedule-project-list input:checked')].map((input) => input.value) : [];
    schedule.include_global = $('#schedule-include-global').checked;
  }
  state.settings.schedule = schedule;
}
function collectOrNotify() {
  try { collectSettings(); return true; }
  catch (error) { notify(error.message, true); return false; }
}
function openProvider(id = '') {
  if (!collectOrNotify()) return;
  const form = $('#provider-form'); form.reset(); form.dataset.editId = id; form.dataset.suggestedId = '';
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
  if (preset.kind === 'plugin:jev') {
    form.elements.model.value = 'jev-1.13.0'; form.elements.auth.value = 'environment'; form.elements.api_key_env.value = 'TYPESAFE_API_KEY';
  }
  $('#provider-models').replaceChildren(); $('#models-status').textContent = 'Load available models for this provider after choosing authentication.';
  if (!form.dataset.editId && (!form.elements.id.value || form.elements.id.value === form.dataset.suggestedId)) {
    form.dataset.suggestedId = form.elements.preset.value.replace('plugin:', '') + '-learning';
    form.elements.id.value = form.dataset.suggestedId;
  }
  updateProviderFields();
}
function updateProviderFields() {
  const form = $('#provider-form'), jev = form.elements.kind.value === 'plugin:jev', anthropic = form.elements.kind.value === 'anthropic', codex = form.elements.kind.value === 'codex';
  if (jev) { form.elements.base_url.value = providerPresets['plugin:jev']?.base_url || 'https://api.typesafe.ai/v1'; form.elements.model.value = 'jev-1.13.0'; if (form.elements.auth.value === 'none') form.elements.auth.value = 'environment'; }
  const auth = form.elements.auth.value;
  $('#codex-login').hidden = !codex; $('#provider-auth-field').hidden = codex;
  $('#custom-endpoint-fields').hidden = jev || (form.elements.preset.value !== 'custom' && form.elements.preset.value !== 'local');
  $('#preset-endpoint-help').hidden = jev || !$('#custom-endpoint-fields').hidden; $('#jev-provider-help').hidden = !jev;
  form.elements.base_url.required = !codex && !jev;
  $('#provider-prices').hidden = codex;
  for (const id of ['codex-device', 'codex-browser', 'codex-check', 'codex-cancel']) $('#' + id).hidden = !moduleEnabled('codex-subscription');
  $('#enable-codex').hidden = moduleEnabled('codex-subscription');
  $('#load-models').disabled = codex && !moduleEnabled('codex-subscription');
  $('#session-key-field').hidden = $('#session-key-help').hidden = auth !== 'session';
  $('#environment-key-field').hidden = $('#environment-key-help').hidden = auth !== 'environment';
  form.elements.api_key.disabled = auth !== 'session';
  if (auth !== 'session') form.elements.api_key.value = '';
  form.elements.auth.querySelector('option[value="none"]').hidden = jev;
  form.elements.api_key_env.disabled = auth !== 'environment'; form.elements.api_key_env.required = auth === 'environment';
  form.elements.model.disabled = jev;
  form.elements.reasoning_effort.disabled = anthropic || jev; form.elements.reasoning_effort.closest('label').hidden = jev; $('#reasoning-help').hidden = !anthropic || jev;
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
  state.providerExtensions = data.provider_extensions || [];
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
  for (const extension of state.providerExtensions) {
    const {kind, label, base_url, auth} = extension;
    providerPresets[kind] = {kind, base_url, auth, api_key_env: ''};
    const preset = new Option(label + ' (plugin)', kind); preset.dataset.plugin = 'true'; form.elements.preset.add(preset);
    const protocol = new Option(label, kind); protocol.dataset.plugin = 'true'; form.elements.kind.add(protocol);
  }
  form.elements.preset.value = selected || 'codex';
  form.elements.kind.value = selectedKind;
}
function removeProvider(id) {
  if (!collectOrNotify()) return;
  const used = Object.entries(state.settings.routes).filter(([, route]) => [route.primary, ...route.fallback].includes(id)).map(([name]) => name);
  const judgment = state.settings.judgment || {}, judgmentUsed = [judgment.primary, ...(judgment.fallback || [])].includes(id);
  if (used.length || judgmentUsed) { notify(`Remove this provider from ${[used.length ? `these routes: ${used.join(', ')}` : '', judgmentUsed ? 'Jev judgment settings' : ''].filter(Boolean).join(' and ')} first.`, true); return; }
  delete state.settings.providers[id]; markDirty(); renderSettings();
}
function openOverride(id = '') {
  if (!collectOrNotify()) return;
  const form = $('#override-form'); form.reset(); form.dataset.editId = id;
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
  const scheduledTarget = schedule.target_mode === 'selected_projects' ? 'Selected projects' : schedule.target_mode === 'all_project_scopes' ? 'All project scopes' : scopeLabel(schedule.scope);
  $('#task-status').textContent = data.scheduled_task?.installed_receipt ? 'Windows task installation recorded. Live health is not polled here; use the status command below. Pausing this schedule stops future consolidation.' : 'No Windows task installation recorded for this vault. Automatic consolidation currently needs the workbench or an external one-shot runner.';
  const values = { Status: schedule.running ? 'Running' : schedule.busy ? 'Busy in another process' : schedule.enabled ? 'Scheduled' : 'Manual', 'Scheduled scope': scheduledTarget, 'Last run': timestamp(schedule.last_run_at), 'Last run scope': schedule.last_run_scope ? scopeLabel(schedule.last_run_scope) : 'No run yet', 'Next run': schedule.enabled ? timestamp(schedule.next_run_at) : 'Not scheduled', Result: result ? `${result.cleaned || 0} duplicates removed; ${result.proposals || 0} summaries proposed` : 'No completed run', 'Last error': schedule.last_error || 'None' };
  if (Number.isInteger(schedule.target_count)) values.Targets = `${schedule.target_count} total · ${schedule.processed_count || 0} visited this run · ${schedule.remaining_count || 0} not visited this run`;
  Object.entries(values).forEach(([label, value]) => facts.append(element('dt', label), element('dd', value)));
  renderScheduleScopeResults(schedule.scope_results);
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
function resultSummary(result) {
  if (!result || typeof result !== 'object') return 'No result recorded.';
  if (result.error) return `Error: ${String(result.error).slice(0, 180)}`;
  const parts = [];
  if (Number.isFinite(result.cleaned)) parts.push(`${result.cleaned} duplicates removed`);
  if (Number.isFinite(result.proposals)) parts.push(`${result.proposals} proposals`);
  if (result.no_op) parts.push('No changes needed');
  return parts.join(' · ') || 'Completed.';
}
function renderScheduleScopeResults(scopeResults) {
  const list = $('#schedule-scope-results'); list.replaceChildren();
  const entries = Array.isArray(scopeResults) ? scopeResults.map((item) => [item.scope, item]) : Object.entries(scopeResults || {});
  list.hidden = !entries.length;
  for (const [scope, result] of entries.slice(0, 100)) {
    const card = element('article', undefined, 'schedule-result');
    card.append(element('strong', scopeLabel(scope)), element('p', resultSummary(result), 'hint'));
    list.append(card);
  }
}
function renderProposals(proposals) {
  const list = $('#proposal-list'); list.replaceChildren();
  if (!proposals.length) { list.append(element('p', 'No proposals for this scope.', 'hint')); return; }
  for (const proposal of proposals) {
    const card = element('article', undefined, 'memory-card');
    card.append(element('h3', proposal.title || 'Untitled proposal'), element('p', proposal.content || ''));
    card.append(element('p', `Scope: ${scopeLabel(proposal.scope || state.scope)} · ${proposal.status || 'pending'}`, 'hint'));
    if (proposal.status === 'pending') {
      const actions = element('div', undefined, 'actions');
      for (const [label, accept] of [['Accept', true], ['Reject', false]]) actions.append(button(label, () => perform(async () => {
        await request('/api/proposals/decide', { proposal_id: proposal.proposal_id, scope: proposal.scope || state.scope, accept });
        await refresh(); notify(accept ? 'Proposal accepted.' : 'Proposal rejected.');
      })));
      card.append(actions);
    }
    list.append(card);
  }
}
function judgmentNumber(value) { return Number.isFinite(value) ? value.toFixed(3) : 'not supplied'; }
function judgmentAssessment(label, assessment) {
  if (!assessment || typeof assessment !== 'object') return '';
  const probability = label === 'Evidence support' ? assessment.probabilities?.supports : assessment.probabilities?.[assessment.verdict];
  const probabilityLabel = label === 'Evidence support' ? 'support probability' : 'label probability';
  return `${label}: ${assessment.verdict || 'unknown'} · ${probabilityLabel} ${judgmentNumber(probability)} · evaluator certainty ${judgmentNumber(assessment.certainty)}`;
}
function renderJudgmentResult(response) {
  const target = $('#judgment-result'); target.replaceChildren();
  const metadata = [`Status: ${response.status || 'unassessed'}`, `Advisory/shadow-only: ${response.shadow_only === true || response.advisory_only === true ? 'yes' : 'no'}`, `Canonical writes: ${response.writes_canonical_memory === true ? 'yes' : 'no'}`, `Source authenticity: ${response.source_authenticity || 'unverified'}`];
  if (response.model) metadata.push(`Model: ${response.model}`);
  if (response.rubric) metadata.push(`Rubric: ${response.rubric}`);
  if (response.cache && typeof response.cache.hit === 'boolean') metadata.push(`Cached: ${response.cache.hit ? 'yes' : 'no'}`);
  target.append(element('span', metadata.join(' · ')));
  if (response.status !== 'assessed') {
    target.append(document.createTextNode(` · ${response.reason === 'preview_stale' ? 'Preview is stale; refresh and review it again.' : response.reason || 'Not assessed.'}`));
    return;
  }
  const support = judgmentAssessment('Evidence support', response.result?.support);
  const comparison = judgmentAssessment('Comparison', response.result?.comparison);
  if (support) target.append(element('span', support, 'judgment-line'));
  if (comparison) target.append(element('span', comparison, 'judgment-line'));
  const language = judgmentAssessment('Language', response.result?.language);
  if (language) target.append(element('span', language, 'judgment-line'));
  if (response.result?.usefulness) target.append(element('span', `Usefulness probability: ${judgmentNumber(response.result.usefulness.probability)}. Retention value, not truth or authority.`, 'judgment-line'));
  target.append(element('span', 'Typed probability and evaluator certainty describe this assessment, not whether a memory is true.', 'judgment-line'));
}
function clearJudgment() {
  state.judgmentRevision += 1; state.judgmentMemory = null;
  const dialog = $('#judgment-dialog');
  if (dialog.open) dialog.close();
  $('#judgment-preview').replaceChildren(); $('#judgment-result').replaceChildren(); $('#judgment-confirm').checked = false;
  $('#run-judgment').disabled = true;
}
function updateJudgmentRun() {
  const allowed = Boolean(state.judgmentMemory && (state.judgmentMode === 'skills' || state.judgmentMemory.source?.excerpt)) && $('#judgment-confirm').checked;
  $('#run-judgment').disabled = !allowed;
}
function renderJudgmentPreview(memory, comparison) {
  const preview = $('#judgment-preview'); preview.replaceChildren();
  preview.append(element('h3', memory.title), element('p', memory.content));
  if (state.judgmentMode === 'skills') {
    const config = state.settings.module_settings?.jev || {};
    preview.append(element('p', `Scope ID: ${memory.scope}. Purpose: ${config.purpose || '(generic scoped archive)'}.`, 'hint'),
      element('p', `Skills: ${[config.language ? 'language' : '', config.usefulness ? 'usefulness' : ''].filter(Boolean).join(', ') || 'none enabled'}. Languages: ${Object.entries(config.languages || {es:'Spanish',en:'English'}).map(([id, label]) => `${id}=${label}`).join(', ')}.`, 'hint'));
    const chain = [state.settings.judgment.primary, ...(state.settings.judgment.fallback || [])].filter(Boolean);
    preview.append(element('p', `Provider order: ${chain.map((id) => `${id} (${state.settings.providers[id]?.model || 'unavailable'})`).join(' → ') || 'not configured'}.`, 'hint'));
  } else preview.append(element('p', 'Source excerpt', 'hint'), element('pre', memory.source.excerpt));
  if (comparison) preview.append(element('h3', 'Comparison candidate'), element('p', comparison.title), element('p', comparison.content));
}
function openJudgment(memory, skills = false) {
  if (!skills && !memory.source?.excerpt) return;
  if (state.dirty) { notify('Save settings before previewing an external assessment.', true); return; }
  state.judgmentMode = skills ? 'skills' : 'support'; state.judgmentConfigKey = state.jevConfigKey;
  $('#judgment-title').textContent = skills ? 'Assess language and usefulness' : 'Evaluate evidence preview';
  state.judgmentRevision += 1; state.judgmentMemory = memory;
  const comparison = $('#judgment-comparison'); comparison.replaceChildren(new Option('No comparison', ''));
  for (const candidate of state.memories.filter((item) => item.memory_id !== memory.memory_id && item.scope === memory.scope)) comparison.add(new Option(candidate.title, candidate.memory_id));
  const compareEnabled = !skills && Boolean(state.settings?.judgment?.operations?.includes('compare'));
  comparison.disabled = !compareEnabled;
  comparison.closest('label').hidden = skills;
  $('#judgment-disclosure').textContent = skills
    ? 'Send only this displayed title/content, scope ID, archive purpose and the displayed skill instructions to the saved provider. No source excerpt or transcript is sent. Results are advisory; canonical memory and ranking stay unchanged.'
    : 'Your local service sends this displayed claim and source excerpt to the configured external judgment provider. An optional comparison sends the two displayed claims separately, never as supporting evidence. It does not write canonical memory.';
  if (!compareEnabled) comparison.title = 'Enable Same-scope comparison in Jev settings before using this option.';
  renderJudgmentPreview(memory);
  $('#judgment-confirm').checked = false; $('#judgment-result').replaceChildren(); updateJudgmentRun();
  $('#judgment-dialog').showModal();
}
async function refresh() {
  const query = new URLSearchParams({ scope: state.scope, inactive: String($('#inactive').checked) });
  const data = await request(`/api/state?${query}`);
  clearRecallResults(); clearJudgment();
  state.credentials = data.credentials || {};
  state.jevConfigKey = data.jev_skill_config_key || '';
  $('#jev-auto-status').textContent = `Automatic assessment: ${data.jev_skills?.status || 'off'}${data.jev_skills?.reason ? ' · ' + data.jev_skills.reason : ''}. No canonical memory changes.`;
  state.scopeLabels = data.scope_labels || {};
  renderModules(data);
  const scheduledScope = state.dirty ? $('#schedule-scope').value : data.settings.schedule.scope;
  const scopes = [...new Set(['global', ...(data.scopes || []), ...(data.settings.schedule.scopes || []), state.scope, scheduledScope])].filter(Boolean);
  state.scopes = scopes;
  scopes.sort((a, b) => a === 'global' ? -1 : b === 'global' ? 1 : scopeLabel(a).localeCompare(scopeLabel(b)));
  $('#scope-selector').replaceChildren(...scopes.map(id => new Option(scopeLabel(id), id)));
  $('#scope-selector').value = state.scope;
  $('#schedule-scope').replaceChildren(...scopes.map(id => new Option(scopeLabel(id), id)));
  $('#schedule-scope').value = scheduledScope;
  $('#scope-id').textContent = state.scope;
  $('#run-consolidation').textContent = `Run now in ${scopeLabel(state.scope)}`;
  renderSourceSchedules(data.source_schedules || []);
  state.codexRoot = data.codex_sessions_root;
  if (!state.dirty) { state.settings = data.settings; renderScheduleProjectTargets(scopes, data.settings.schedule); renderSettings(); }
  state.memories = data.memories || [];
  renderMemories(state.memories); renderOperational(data); renderProposals(data.proposals || []);
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
$('#judgment-confirm').addEventListener('change', updateJudgmentRun);
$('#judgment-comparison').addEventListener('change', () => {
  const memory = state.judgmentMemory, comparison = state.memories.find((item) => item.memory_id === $('#judgment-comparison').value && item.scope === memory?.scope);
  state.judgmentRevision += 1; $('#judgment-result').replaceChildren(); $('#judgment-confirm').checked = false;
  if (memory) renderJudgmentPreview(memory, comparison); updateJudgmentRun();
});
$('#run-judgment').addEventListener('click', () => {
  const memory = state.judgmentMemory;
  const skills = state.judgmentMode === 'skills';
  if (!memory || (!skills && !memory.source?.excerpt) || !$('#judgment-confirm').checked) return;
  const comparisonId = $('#judgment-comparison').value;
  const comparison = state.memories.find((item) => item.memory_id === comparisonId && item.scope === memory.scope);
  const revision = ++state.judgmentRevision;
  const payload = { memory_id: memory.memory_id, scope: memory.scope, expected_revision: memory.judgment_revision, confirmed: true };
  if (skills) payload.expected_config = state.judgmentConfigKey;
  else if (comparison) { payload.comparison_id = comparison.memory_id; payload.comparison_revision = comparison.judgment_revision; }
  perform(async () => {
    try {
      const response = await request(skills ? '/api/jev-skills' : '/api/judgment', payload);
      if (revision !== state.judgmentRevision || state.judgmentMemory?.memory_id !== memory.memory_id || state.scope !== memory.scope) return;
      renderJudgmentResult(response);
      try {
        const operational = await request(`/api/state?scope=${encodeURIComponent(state.scope)}`);
        renderOperational(operational);
        $('#judgment-result').append(element('span', `Today's shared usage: ${operational.usage.calls} attempts · ${operational.usage.tokens} tokens. See Activity for estimates; missing model prices do not mean free usage.`, 'judgment-line'));
      } catch (_) { notify('Assessment completed; refresh Activity to update usage.'); }
    } catch (error) {
      if (revision === state.judgmentRevision && state.judgmentMemory?.memory_id === memory.memory_id) renderJudgmentResult({ status: 'unassessed', shadow_only: true, writes_canonical_memory: false, source_authenticity: 'unverified', reason: 'request_failed', result: {} });
      throw error;
    }
  });
});
document.querySelectorAll('.save-settings').forEach((item) => item.addEventListener('click', () => {
  const invalid = [...document.querySelectorAll('#providers input, #consolidation input, #modules input, #modules textarea')].find((input) => !input.checkValidity());
  if (invalid) { location.hash = invalid.closest('.page').id; showPage(); invalid.reportValidity(); return; }
  perform(async () => { collectSettings(); await request('/api/settings', state.settings); markDirty(false); await refresh(); notify('Settings saved.'); });
}));
for (const id of ['providers', 'consolidation', 'modules']) {
  const changed = (event) => { if (!event.target.closest('#jev-evaluation-panel')) markDirty(); };
  $( `#${id}`).addEventListener('input', changed);
  $( `#${id}`).addEventListener('change', changed);
}
$('#schedule-mode').addEventListener('change', updateScheduleTargetControls);
$('#preview-jev-evaluation').addEventListener('click', () => perform(async () => {
  if (state.dirty) throw new Error('Save module/provider settings before previewing the pilot.');
  const preview = await request('/api/jev-evaluation/preview', {});
  state.jevEvaluationKey = preview.config_key;
  const target = $('#jev-evaluation-preview'); target.hidden = false; target.textContent = JSON.stringify(preview, null, 2);
  $('#jev-evaluation-confirm').disabled = false; $('#jev-evaluation-confirm').checked = false;
  $('#run-jev-evaluation').disabled = true; $('#jev-evaluation-result').hidden = true;
}));
$('#jev-evaluation-confirm').addEventListener('change', () => { $('#run-jev-evaluation').disabled = !$('#jev-evaluation-confirm').checked; });
$('#run-jev-evaluation').addEventListener('click', () => perform(async () => {
  if (state.dirty || !state.jevEvaluationKey || !$('#jev-evaluation-confirm').checked) throw new Error('Preview and confirm the saved configuration first.');
  const result = await request('/api/jev-evaluation', {confirmed:true, expected_config:state.jevEvaluationKey});
  const target = $('#jev-evaluation-result'); target.hidden = false; target.textContent = JSON.stringify(result, null, 2);
  $('#jev-evaluation-summary').textContent = result.status === 'assessed'
    ? `Synthetic pilot: language ${result.measured.language_correct}/8; usefulness ${result.measured.usefulness_correct}/8 vs keep-all 4/8. Useful records rejected: ${result.measured.useful_rejected}; noise kept: ${result.measured.noise_kept}. Cached: ${result.cached ? 'yes' : 'no'}. This is not production efficacy or a calibrated threshold.`
    : `Not assessed: ${result.reason || result.status}. No memory changed.`;
  $('#jev-evaluation-confirm').checked = false; $('#run-jev-evaluation').disabled = true;
  const operational = await request(`/api/state?scope=${encodeURIComponent(state.scope)}`); renderOperational(operational);
}));
$('#add-provider').addEventListener('click', () => openProvider());
$('#add-override').addEventListener('click', () => openOverride());
$('#refresh').addEventListener('click', () => perform(async () => { await refresh(); notify(state.dirty ? 'Activity and memory refreshed. Your unsaved settings are preserved.' : 'Up to date.'); }));
function changeScope(value) {
  if (!/^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$/.test(value)) { notify('Use a short scope name, such as global or project:your-project.', true); return; }
  state.scope = value; $('#scope').value = '';
  clearRecallResults(); clearJudgment();
  notify('');
  state.sources.forEach(item => { item.preview = null; item.result = ''; item.open = false; }); renderSources(); perform(refresh);
}
$('#scope-form').addEventListener('submit', (event) => { event.preventDefault(); changeScope($('#scope').value.trim()); });
$('#scope-selector').addEventListener('change', event => changeScope(event.target.value));
$('#inactive').addEventListener('change', () => perform(refresh));
$('#recall-form').addEventListener('submit', (event) => {
  event.preventDefault();
  const query = event.currentTarget.elements.query.value.trim(), scope = state.scope;
  const revision = ++state.recallRevision, list = $('#recall-results');
  list.replaceChildren(element('p', `Searching ${scopeLabel(scope)}…`, 'hint')); list.hidden = false;
  perform(async () => {
    try {
      const hits = await request('/api/recall', { query, scope });
      if (revision !== state.recallRevision || scope !== state.scope) return;
      renderRecallResults(Array.isArray(hits) ? hits : [], scope);
    } catch (error) {
      if (revision === state.recallRevision && scope === state.scope) list.replaceChildren(element('p', 'Search unavailable. Try again.', 'memory-empty'));
      throw error;
    }
  });
});
$('#remember-form').addEventListener('submit', (event) => {
  event.preventDefault(); const form = event.currentTarget;
  const payload = { title: form.elements.title.value.trim(), content: form.elements.content.value.trim(), scope: state.scope, importance: form.elements.importance.value || 'normal', memory_kind: form.elements.memory_kind.value || 'unspecified', expires_at: isoDateTime(form.elements.expires_at.value) };
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
  $('#source-selection').textContent = `${selected.length} selected · destination ${scopeLabel(state.scope)}. Preview each selected conversation before extracting. Each conversation uses its own bounded model call.`;
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
      details.append(element('p',`${p.messages.length} user messages → ${scopeLabel(p.scope)} · ${p.destinations.join(' → ') || 'No extraction route configured'}`, 'hint'));
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
    try { const result = await request('/api/sources/extract',{preview_token:item.preview.preview_token,confirmed:true}); item.result = `${(result.learned || []).length} learnings saved to ${scopeLabel(item.preview.scope)}`; item.selected = false; }
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
    card.append(element('h3',`${rule.format} → ${scopeLabel(rule.scope)}`),element('p',rule.root,'source-path'),element('p',`${rule.enabled?'Enabled':'Paused'} · every ${rule.interval_hours}h · ${rule.last_result}${rule.enabled?' · next '+new Date(rule.next_run*1000).toLocaleString():''}`,'hint'));
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
$('#run-consolidation').addEventListener('click', () => perform(async () => { notify(`Running consolidation in ${scopeLabel(state.scope)}…`); const result = await request('/api/consolidate', { scope: state.scope }); await refresh(); notify(`Consolidation in ${scopeLabel(result.scope)} complete: ${result.cleaned || 0} duplicates removed; ${result.proposals || 0} summaries proposed.`); }));
window.addEventListener('hashchange', showPage);
window.addEventListener('beforeunload', (event) => { if (state.dirty) { event.preventDefault(); event.returnValue = ''; } });
showPage(); perform(refresh);
