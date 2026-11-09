import json
import tempfile
import threading
import unittest
from http.client import HTTPConnection
from pathlib import Path
from reach.server import make_server


class ReachHttpTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.httpd=make_server('127.0.0.1',0,str(Path(self.tmp.name)/'data.sqlite'))
        self.thread=threading.Thread(target=self.httpd.serve_forever,daemon=True)
        self.thread.start()
        self.addCleanup(self.shutdown)

    def shutdown(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=2)

    def request(self,method,path,body=None,headers=None):
        c=HTTPConnection('127.0.0.1',self.httpd.server_port,timeout=3)
        c.request(method,path,body=body,headers=headers or {})
        r=c.getresponse();data=r.read();code=r.status;h=dict(r.getheaders());c.close()
        return code,data,h

    def test_non_loopback_binding_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'loopback only'):
            make_server('0.0.0.0', 0, str(Path(self.tmp.name) / 'unsafe.sqlite'))

    def test_home_and_health(self):
        status,body,headers=self.request('GET','/')
        self.assertEqual(status,200)
        self.assertIn(b'NABU',body)
        self.assertIn("default-src 'self'",headers['Content-Security-Policy'])
        status,body,_=self.request('GET','/healthz')
        self.assertEqual(json.loads(body)['mode'],'draft_only')

    def test_cross_origin_write_rejected(self):
        status,body,_=self.request('POST','/api/accounts',b'{}',{'Origin':'https://evil.example','Content-Type':'application/json'})
        self.assertEqual(status,403)

    def test_account_post(self):
        body=json.dumps({'label':'QA','provider':'mock'}).encode()
        status,response,_=self.request('POST','/api/accounts',body,{'Content-Type':'application/json'})
        self.assertEqual(status,200)
        self.assertEqual(json.loads(response)['status'],'mock_ready')

    def test_invalid_import_content_type(self):
        status,body,_=self.request('POST','/api/contacts/import',b'hi',{'Content-Type':'application/json'})
        self.assertEqual(status,415)

if __name__=='__main__':unittest.main()
