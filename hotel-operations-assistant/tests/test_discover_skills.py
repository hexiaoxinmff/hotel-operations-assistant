import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import urllib.error
spec=importlib.util.spec_from_file_location('discovery',Path(__file__).resolve().parents[1]/'scripts'/'discover_skills.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class Response:
    def __init__(self,data,url='https://skills.sh/api/search'):self.data=data;self.url=url
    def __enter__(self):return self
    def __exit__(self,*args):pass
    def geturl(self):return self.url
    def read(self,n):return self.data[:n]
class DiscoveryTests(unittest.TestCase):
    def item(self):return {'id':'owner/repo/pdf','source':'owner/repo','name':'PDF','installs':10}
    def response(self,items):return json.dumps({'skills':items}).encode()
    def test_valid_candidate_not_verified(self):
        r=m.search('pdf-ocr',opener=lambda *a,**k:Response(self.response([self.item()])));self.assertEqual(r['status'],'ok');self.assertEqual(r['results'][0]['status'],'candidate_not_verified')
    def test_no_results(self):self.assertEqual(m.search('word',opener=lambda *a,**k:Response(self.response([])))['status'],'no_results')
    def test_network_error_not_no_results(self):
        def fail(*a,**k):raise urllib.error.URLError('offline')
        r=m.search('word',opener=fail);self.assertEqual(r['status'],'unavailable');self.assertEqual(r['next_step'],'platform_fallback')
    def test_invalid_payload(self):self.assertEqual(m.search('word',opener=lambda *a,**k:Response(b'bad json'))['status'],'unavailable')
    def test_path_traversal_rejected(self):
        for slug in ['owner/repo/../pdf','owner/repo//pdf','owner/repo/pdf?x=1','owner/repo/pdf%2fsecret','owner/repo/..']:
            x=self.item();x['id']=slug;r=m.search('word',opener=lambda *a,**k:Response(self.response([x])));self.assertEqual(r['status'],'invalid_results')
    def test_source_mismatch(self):
        x=self.item();x['source']='other/repo';self.assertEqual(m.normalize({'skills':[x]})[0],[])
    def test_duplicate_results(self):self.assertEqual(len(m.normalize({'skills':[self.item(),self.item()]})[0]),1)
    def test_redirect_endpoint_rejected(self):self.assertEqual(m.search('word',opener=lambda *a,**k:Response(self.response([]),'http://example.com/'))['status'],'unavailable')
    def test_oversize_response(self):self.assertEqual(m.search('word',opener=lambda *a,**k:Response(b'x'*1048577))['status'],'unavailable')
    def test_only_predefined_generic_queries(self):
        for q in ['hotel-company-name','C:/private','user@example.com']:
            with self.assertRaises(ValueError):m.search(q)
    def test_search_stops_at_limit(self):
        items=[]
        for i in range(10):x=self.item();x['id']='owner/repo/skill'+str(i);items.append(x)
        self.assertEqual(len(m.normalize({'skills':items},3)[0]),3)
    def test_workflow_requires_confirmed_current_requirement(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'state.json'
            for phase in ['requirement_pending','cancelled','delivered']:
                p.write_text(json.dumps({'schema':1,'phase':phase,'requirement_version':1,'requirement_confirmation':{'requirement_version':1,'quote':'fictional confirmation','message_ref':'fictional-message'}}))
                with self.assertRaises(ValueError):m.require_discovery(p,1)
            p.write_text(json.dumps({'schema':1,'phase':'solution_research','requirement_version':1,'requirement_confirmation':{'requirement_version':1,'quote':'fictional confirmation','message_ref':'fictional-message'}}));self.assertTrue(m.require_discovery(p,1))
            with self.assertRaises(ValueError):m.require_discovery(p,2)
if __name__=='__main__':unittest.main()
