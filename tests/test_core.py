import json
import tempfile
import unittest
from pathlib import Path

from reach.core import Store, ValidationError


def csv_bytes(rows):
    return ('phone,name,consent,consent_source,consent_at\n'+rows).encode()


class ReachCoreTests(unittest.TestCase):
    def setUp(self):
        self.dir=tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.store=Store(str(Path(self.dir.name)/'db.sqlite'))

    def test_import_valid_opt_in_with_consent_evidence(self):
        result=self.store.import_csv(csv_bytes('+15550100001,Alex,yes,signup_form,2026-01-01T12:00:00Z\n'))
        self.assertEqual(result['imported'],1)
        self.assertEqual(self.store.summary()['opted_in'],1)

    def test_missing_consent_evidence_rejected(self):
        result=self.store.import_csv(csv_bytes('+15550100001,Alex,yes,,\n'))
        self.assertEqual(result['skipped'],1)
        self.assertEqual(self.store.summary()['opted_in'],0)

    def test_import_opt_out_overrides_but_never_reopts_in(self):
        self.store.import_csv(csv_bytes('+15550100001,Alex,yes,form,2026-01-01T12:00:00Z\n'))
        self.store.opt_out('+15550100001')
        result=self.store.import_csv(csv_bytes('+15550100001,Alex,yes,another_form,2026-02-01T12:00:00Z\n'))
        self.assertEqual(result['skipped'],1)
        self.assertEqual(self.store.summary()['opted_out'],1)

    def test_import_opt_out_csv_overrides_opt_in(self):
        self.store.import_csv(csv_bytes('+15550100001,Alex,yes,form,2026-01-01T12:00:00Z\n'))
        self.store.import_csv(csv_bytes('+15550100001,Alex,no,,\n'))
        self.assertEqual(self.store.summary()['opted_out'],1)

    def test_future_consent_rejected(self):
        result=self.store.import_csv(csv_bytes('+15550100001,Alex,yes,form,2099-01-01T12:00:00Z\n'))
        self.assertEqual(result['skipped'],1)

    def test_bad_phone_rejected(self):
        result=self.store.import_csv(csv_bytes('001,Alex,yes,form,2026-01-01T12:00:00Z\n'))
        self.assertEqual(result['skipped'],1)

    def test_preview_excludes_opted_out_and_renders(self):
        self.store.import_csv(csv_bytes('+15550100001,Alex,yes,form,2026-01-01T12:00:00Z\n+15550100002,Sam,no,,\n'))
        result=self.store.preview('Hi {{name}} at {{phone}}')
        self.assertEqual(result['eligible'],1)
        self.assertEqual(len(result['examples']),1)
        self.assertEqual(result['examples'][0]['message'],'Hi Alex at +15550100001')
        self.assertFalse(result['sending_enabled'])

    def test_template_rejects_unknown_tags(self):
        with self.assertRaises(ValidationError):
            self.store.preview('Hi {{secret}}')

    def test_draft_account_required_and_draft_only(self):
        account=self.store.add_account('Example Account','mock')
        saved=self.store.add_draft('Newsletter',account['id'],'Hello {{name}}')
        self.assertEqual(saved['status'],'draft')
        self.assertEqual(self.store.summary()['drafts'],1)
        self.assertFalse(saved['sending_enabled'])

    def test_provider_placeholders_not_connected(self):
        account=self.store.add_account('Business','gowa')
        self.assertEqual(account['status'],'setup_required')

    def test_csv_row_cap(self):
        payload=csv_bytes('+15550100001,Alex,no,,\n'*1001)
        with self.assertRaises(ValidationError):
            self.store.import_csv(payload)


if __name__=='__main__': unittest.main()
