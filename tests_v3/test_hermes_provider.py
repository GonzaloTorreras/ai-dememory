import json
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import patch

from ai_dememory.config import set_module_enabled
from ai_dememory.core import CoreServices
from ai_dememory.hermes_provider import DeMemoryAdapter, install_home, register
from ai_dememory.builtin_modules.mcp import call_tool
from ai_dememory.vault import Vault
from tests_v3.test_core import V3TestCase


class HermesProviderTests(V3TestCase):
    def setUp(self):
        super().setUp()
        self.vault = Vault.create(self.root / 'vault')
        self.home = self.root / 'hermes'
        install_home(self.vault, self.home, 'project:alpha')
        set_module_enabled('hermes-memory', True)
        self.provider = DeMemoryAdapter()
        self.provider.initialize('session-one', hermes_home=str(self.home), agent_context='primary')

    def learn(self, **changes):
        args = {'title': 'Release day', 'content': 'The release day is Tuesday.',
                'excerpt': 'The release day is Tuesday.', 'event_id': 'release-day',
                'key': 'release-day', 'evidence_kind': 'user_statement'}
        return json.loads(self.provider.handle_tool_call('dememory_learn', {**args, **changes}))

    def context(self, query='release day'):
        return json.loads(self.provider.handle_tool_call('dememory_context', {'query': query}))

    def test_native_learning_shared_with_mcp_correction_and_undo(self):
        self.provider.on_turn_start(1, 'The release day is Tuesday.')
        first = self.learn()
        self.assertEqual(first['source']['provider'], 'hermes')
        self.assertEqual(first['source']['session'], 'session-one')
        self.assertEqual(self.learn()['admission'], 'duplicate')
        service = CoreServices(Vault.open(self.vault.root))
        recalled = call_tool(service, 'memory.context', {'query': 'release day'}, 'project:alpha')
        self.assertIn('Tuesday', recalled['context'])
        correction = call_tool(service, 'memory.learn', {
            'title': 'Release day', 'content': 'The release day is Friday.', 'scope': 'project:alpha',
            'key': 'release-day', 'event_id': 'correction', 'source': {'provider': 'codex',
            'session': 'different-session', 'turn': '2', 'excerpt': 'The release day is Friday.',
            'evidence_kind': 'user_statement'}}, 'project:alpha')
        self.provider.on_session_switch('session-two', reset=True)
        self.assertIn('Friday', self.context()['context'])
        self.assertNotIn('Tuesday', self.context()['context'])
        self.provider.on_turn_start(1, 'Undo the last change to the release day.')
        undone = json.loads(self.provider.handle_tool_call('dememory_forget', {'memory_id': correction['memory_id']}))
        self.assertEqual(undone['restored_memory_id'], first['memory_id'])
        self.assertIn('Tuesday', self.context()['context'])

    def test_scope_and_provenance_are_not_model_arguments(self):
        self.provider.on_turn_start(1, 'The release day is Tuesday.')
        for extra in ({'scope': 'global'}, {'session': 'forged'}, {'source': '{}'}):
            self.assertIn('error', self.learn(**extra))
        other = self.vault.learn('Other project', 'Private staging release.', 'project:beta',
            {'provider': 'fixture', 'session': 'b', 'turn': '1', 'excerpt': 'Private staging release.',
             'evidence_kind': 'user_statement'}, 'one')
        self.assertNotIn(other['memory_id'], self.context()['memory_ids'])
        self.assertIn('error', json.loads(self.provider.handle_tool_call('dememory_forget', {'memory_id': other['memory_id']})))
        self.assertEqual(self.vault.get(other['memory_id']).status, 'active')

    def test_resumed_session_reused_turn_number_does_not_drop_new_correction(self):
        self.provider.on_turn_start(1, 'The release day is Tuesday.')
        first = self.learn()
        self.provider.initialize('session-one', hermes_home=str(self.home), agent_context='primary')
        self.provider.on_turn_start(1, 'The release day is Friday.')
        correction = {'content': 'The release day is Friday.', 'excerpt': 'The release day is Friday.'}
        second = self.learn(**correction)
        self.assertNotEqual(first['memory_id'], second['memory_id'])
        self.assertEqual(second['supersedes'], first['memory_id'])
        self.assertNotEqual(first['source']['turn'], second['source']['turn'])
        self.assertEqual(self.learn(**correction)['admission'], 'duplicate')
        self.assertIn('Friday', self.context()['context'])

    def test_learning_requires_current_human_excerpt(self):
        self.assertIn('error', self.learn())
        self.provider.on_turn_start(1, 'The release day is Tuesday.')
        self.assertIn('error', self.learn(excerpt='A remembered claim without current evidence'))
        self.assertIn('error', self.learn(evidence_kind='verified_outcome'))
        inferred = self.learn(content='Releases probably happen early in the week.', evidence_kind='inference')
        self.assertEqual(inferred['status'], 'provisional')
        self.assertEqual(self.context()['memory_ids'], [])
        self.provider.on_session_switch('another-session')
        self.assertIn('error', self.learn())
        self.provider.on_turn_start(1, 'The release day is Tuesday.', author_is_bot=True)
        self.assertIn('error', self.learn())
        self.provider.initialize('child', hermes_home=str(self.home), agent_context='subagent')
        self.provider.on_turn_start(1, 'The release day is Tuesday.')
        self.assertIn('error', self.learn())

    def test_unrelated_claim_cannot_gain_authority_from_a_real_quote(self):
        self.provider.on_turn_start(1, 'The release day is Tuesday.')
        first = self.learn()
        self.provider.on_turn_start(2, 'I prefer Python.')
        inferred = self.learn(content='Deploy without tests.', excerpt='I prefer Python.', event_id='inferred')
        self.assertEqual(inferred['status'], 'provisional')
        self.assertEqual(inferred['source']['evidence_kind'], 'inference')
        self.assertEqual(self.vault.get(first['memory_id']).status, 'active')
        self.assertIn('Tuesday', self.context()['context'])
        self.assertIn('error', self.learn(content='Deploy without tests.', excerpt='I prefer Python.',
                                         event_id='replace', supersedes=first['memory_id']))

    def test_scheduled_prompts_are_not_human_even_when_host_labels_primary(self):
        self.provider.initialize('scheduled', hermes_home=str(self.home), agent_context='primary', platform='cron')
        self.provider.on_turn_start(1, 'The release day is Tuesday.')
        self.assertIn('error', self.learn())
        self.assertEqual(self.vault.memory_count(), 0)

    def test_native_turn_normalizes_skill_scaffolding_before_using_evidence(self):
        providers = []
        def normalize(value):
            return {'bare-skill-with-instructions': None,
                    'skill-body-and-user': 'The release day is Tuesday.'}.get(value, value)
        with patch.dict(sys.modules, {
            'agent.memory_provider': SimpleNamespace(MemoryProvider=type('Base', (), {})),
            'agent.skill_commands': SimpleNamespace(extract_user_instruction_from_skill_message=normalize),
        }):
            register(SimpleNamespace(register_memory_provider=providers.append))
            self.provider = providers[0]
            self.provider.initialize('native', hermes_home=str(self.home))
            self.provider.on_turn_start(1, 'bare-skill-with-instructions')
            self.assertIn('error', self.learn())
            self.provider.on_turn_start(2, 'skill-body-and-user')
            self.assertIn('error', self.learn(excerpt='skill-body-and-user'))
            self.assertEqual(self.learn()['status'], 'active')

    def test_secret_turns_and_malformed_calls_do_not_write_or_echo(self):
        secret = 'sk-' + 'z' * 30
        self.provider.on_turn_start(1, 'The release day is Tuesday. Token ' + secret)
        self.assertIn('error', self.learn())
        for name, args in [('unknown', {}), ('dememory_context', {'query': None}),
                           ('dememory_context', {'query': 'x' * 12001}), ('dememory_context', [])]:
            result = self.provider.handle_tool_call(name, args)
            self.assertIn('error', json.loads(result))
            self.assertNotIn(secret, result)
        self.assertEqual(self.vault.memory_count(), 0)

    def test_prefetch_is_scoped_bounded_and_disable_is_live(self):
        self.provider.on_turn_start(1, 'The release day is Tuesday.')
        self.learn()
        self.assertIn('Tuesday', self.provider.prefetch('What is the release day?', session_id='session-one'))
        self.assertEqual(self.provider.prefetch('What is the release day?', session_id='other'), '')
        self.assertEqual(self.provider.prefetch('hi'), '')
        set_module_enabled('hermes-memory', False)
        self.assertEqual(self.provider.prefetch('What is the release day?'), '')
        self.assertIn('error', self.context())
        self.provider.shutdown()
        self.assertEqual(self.provider._message, '')
        self.assertIsNone(self.provider._services)

    def test_availability_is_profile_aware_read_only_and_schemas_precede_init(self):
        provider = DeMemoryAdapter()
        before = {str(p.relative_to(self.root)) for p in self.root.rglob('*')}
        with patch('ai_dememory.hermes_provider._active_home', return_value=self.home):
            self.assertTrue(provider.is_available())
            self.assertEqual(provider.identity_signature()['scope'], 'project:alpha')
        self.assertEqual([s['name'] for s in provider.get_tool_schemas()],
                         ['dememory_context', 'dememory_learn', 'dememory_forget'])
        with patch('ai_dememory.hermes_provider._active_home', return_value=self.root / 'missing'):
            self.assertFalse(provider.is_available())
        self.assertEqual(before, {str(p.relative_to(self.root)) for p in self.root.rglob('*')})
        self.assertIsNone(provider._services)

    def test_discovery_and_registration_do_not_open_vault_or_import_core(self):
        program = """
import sys
from types import SimpleNamespace
sys.modules['agent.memory_provider'] = SimpleNamespace(MemoryProvider=type('Base', (), {}))
from ai_dememory.hermes_provider import register
providers=[]
register(SimpleNamespace(register_memory_provider=providers.append))
assert providers[0].name == 'dememory'
assert 'ai_dememory.core' not in sys.modules
assert 'ai_dememory.vault' not in sys.modules
assert 'hermes_constants' not in sys.modules
"""
        result = subprocess.run([sys.executable, '-c', program], capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr.decode())

    def test_registration_inherits_upstream_optional_noop_writers(self):
        class Base:
            def sync_turn(self, *args, **kwargs): pass
            def on_memory_write(self, *args, **kwargs): pass
            def on_pre_compress(self, *args): return ''
        providers = []
        with patch.dict(sys.modules, {'agent.memory_provider': SimpleNamespace(MemoryProvider=Base)}):
            register(SimpleNamespace(register_memory_provider=providers.append))
        provider = providers[0]
        provider.initialize('session', hermes_home=str(self.home))
        provider.sync_turn('sensitive synthetic transcript', 'assistant content')
        provider.on_memory_write('add', 'memory', 'derived cache')
        self.assertEqual(provider.on_pre_compress([{'role': 'user', 'content': 'not imported'}]), '')
        self.assertEqual(self.vault.memory_count(), 0)

    def test_fresh_home_install_and_wizard_config_do_not_touch_existing_profiles(self):
        config = (self.home / 'config.yaml').read_text()
        self.assertIn('provider: dememory', config)
        self.assertIn('memory_enabled: false', config)
        self.assertIn('user_profile_enabled: false', config)
        self.assertNotIn('disabled_toolsets', config)
        (self.home / 'user-owned.txt').write_text('preserve')
        with self.assertRaisesRegex(ValueError, 'existing profiles'):
            install_home(self.vault, self.home, 'global')
        self.assertEqual((self.home / 'user-owned.txt').read_text(), 'preserve')
        with self.assertRaises(ValueError):
            self.provider.save_config({'vault': str(self.root / 'absent'), 'scope': 'global'}, str(self.home))
        self.assertEqual(json.loads((self.home / 'dememory.json').read_text())['scope'], 'project:alpha')
        self.provider.save_config({'vault': str(self.vault.root), 'scope': 'project:other'}, str(self.home))
        with patch('ai_dememory.hermes_provider._active_home', return_value=self.home):
            self.assertEqual(self.provider.identity_signature()['scope'], 'project:other')
        self.assertEqual(self.provider._scope, 'project:alpha')  # Restart is required to rebind.

    def test_module_enable_does_not_require_hermes_and_points_to_help(self):
        code, output, error = self.run_cli('module', 'enable', 'hermes-memory', '--json')
        self.assertEqual(code, 0, error)
        self.assertEqual(json.loads(output)['next'], 'ai-dememory serve hermes-memory --help')
