import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from ai_dememory.modules import enable_module, disable_module
from ai_dememory.source_jobs import SourceJobs
from ai_dememory.vault import Vault


class SourceJobTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.root=Path(temp.name); self.sources=self.root/'sessions'; self.sources.mkdir()
        self.env=patch.dict(os.environ,AI_DEMEMORY_CONFIG_DIR=str(self.root/'config')); self.env.start(); self.addCleanup(self.env.stop)
        self.jobs=Mock(); self.jobs.extract.return_value={'learned':[{}]}
        self.manager=SourceJobs(Vault.create(self.root/'vault'),self.jobs)
        self.payload={'root':str(self.sources),'format':'generic','scope':'project:test','interval_hours':1,'enabled':True,'confirmed':True}

    def test_opt_in_schedule_and_stable_receipts(self):
        with self.assertRaises(ValueError): self.manager.save(self.payload)
        enable_module('sources')
        with self.assertRaises(ValueError): self.manager.save({**self.payload,'confirmed':False})
        (self.sources/'a.json').write_text(json.dumps({'messages':[{'role':'user','content':'Synthetic preference'}]}))
        id=self.manager.save(self.payload)['saved']
        self.assertTrue(self.manager.run()['skipped'])
        self.assertEqual(self.manager.run(id)['learned'],1)
        self.assertEqual(self.manager.run(id)['processed'],0)
        self.jobs.extract.assert_called_once()
        self.assertEqual(self.jobs.extract.call_args.args[1],'project:test')
        self.assertEqual(self.jobs.extract.call_args.kwargs['route_key'],'skill:source-generic')
        self.assertNotIn('seen',self.manager.public()[0])
        self.manager.change(id,'pause'); self.assertFalse(self.manager.public()[0]['enabled'])
        disable_module('sources')
        with self.assertRaises(ValueError): self.manager.run(id)

    def test_failure_does_not_mark_source_consumed(self):
        enable_module('sources')
        (self.sources/'a.json').write_text('[{"role":"user","content":"Keep this"}]')
        id=self.manager.save(self.payload)['saved']
        self.jobs.extract.side_effect=ValueError('private provider exception')
        self.assertTrue(self.manager.run(id)['failed'])
        self.assertEqual(self.manager.load()['rules'][0]['seen'],{})
        self.assertNotIn('private provider exception',str(self.manager.public()))

    def test_assistant_activity_does_not_repeat_extraction_and_bad_file_is_skipped(self):
        enable_module('sources')
        file=self.sources/'a.json'
        rows=[{'role':'user','content':'Useful stable preference'}]
        file.write_text(json.dumps(rows))
        id=self.manager.save(self.payload)['saved']
        self.manager.run(id)
        rows.append({'role':'assistant','content':'New assistant activity'})
        file.write_text(json.dumps(rows))
        (self.sources/'broken.json').write_text('{invalid')
        result=self.manager.run(id)
        self.assertEqual(result['processed'],0)
        self.assertEqual(result['skipped'],1)
        self.jobs.extract.assert_called_once()
