import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
spec=importlib.util.spec_from_file_location('guard',Path(__file__).resolve().parents[1]/'scripts'/'workflow_guard.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class WorkflowTests(unittest.TestCase):
    def setUp(self):self.state=m.initial('Fictional test','Prepare a fictional summary')
    def requirement(self):return m.transition(self.state,'confirm_requirement',{'requirement_version':1,'quote':'Fictional user: requirement correct','message_ref':'fictional-message-1'})
    def plans(self,state=None):return m.transition(state or self.requirement(),'propose_plans',{'plans':[{'id':'A','description':'Read-only summary','deliverables':'JSON result','constraints':'No external changes','actions':['metrics']}]})
    def ready(self):return m.transition(self.plans(),'confirm_plan',{'requirement_version':1,'plan_version':1,'plan_id':'A','quote':'Fictional user: choose A, start','message_ref':'fictional-message-2'})
    def test_initial_cannot_execute(self):
        with self.assertRaises(ValueError):m.check(self.state,'metrics',1,0)
    def test_requirement_only_cannot_execute(self):
        with self.assertRaises(ValueError):m.check(self.requirement(),'metrics',1,0)
    def test_cannot_propose_before_requirement(self):
        with self.assertRaises(ValueError):self.plans(self.state)
    def test_no_auto_selection(self):
        with self.assertRaises(ValueError):m.check(self.plans(),'metrics',1,1)
    def test_two_confirmations_allow(self):self.assertTrue(m.check(self.ready(),'metrics',1,1))
    def test_action_scope(self):
        with self.assertRaises(ValueError):m.check(self.ready(),'ocr',1,1)
    def test_old_versions_rejected(self):
        with self.assertRaises(ValueError):m.check(self.ready(),'metrics',1,0)
    def test_revise_requirement_invalidates(self):
        s=m.transition(self.ready(),'revise_requirement',{'requirement':'Different task'})
        self.assertEqual(s['requirement_version'],2);self.assertIsNone(s['plan_confirmation'])
        with self.assertRaises(ValueError):m.check(s,'metrics',1,1)
    def test_new_plan_invalidates(self):
        s=self.plans(self.ready());self.assertEqual(s['plan_version'],2)
        with self.assertRaises(ValueError):m.check(s,'metrics',1,1)
    def test_missing_confirmation_evidence(self):
        with self.assertRaises(ValueError):m.transition(self.state,'confirm_requirement',{'requirement_version':1,'quote':'yes'})
    def test_unknown_selection(self):
        with self.assertRaises(ValueError):m.transition(self.plans(),'confirm_plan',{'requirement_version':1,'plan_version':1,'plan_id':'B','quote':'yes','message_ref':'test'})
    def test_cancel_prevents_execution(self):
        s=m.transition(self.ready(),'cancel',{})
        with self.assertRaises(ValueError):m.check(s,'metrics',1,1)
        with self.assertRaises(ValueError):m.transition(s,'revise_requirement',{'requirement':'restart'})
    def test_delivery_not_success(self):
        s=m.transition(self.ready(),'deliver',{'output':'fictional.json','verification':'Fictional tool check'})
        self.assertEqual(s['phase'],'delivered')
        s=m.transition(s,'confirm_success',{'quote':'Fictional user: solved','message_ref':'fictional-message-3'});self.assertEqual(s['phase'],'success_confirmed')
    def test_cannot_confirm_success_before_delivery(self):
        with self.assertRaises(ValueError):m.transition(self.ready(),'confirm_success',{'quote':'solved','message_ref':'test'})
    def test_file_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'state.json';m.save(p,self.ready());self.assertTrue(m.require_execution(p,1,1,'metrics'))
    def test_cli_blocks_before_output(self):
        scripts=Path(__file__).resolve().parents[1]/'scripts'
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'no-output'
            result=subprocess.run([sys.executable,'-B',str(scripts/'research_tools.py'),'images','--input','nonexistent.xlsx','--output',str(out)],capture_output=True,text=True)
            self.assertEqual(result.returncode,2);self.assertIn('workflow',result.stdout);self.assertFalse(out.exists())
    def test_cli_metrics_approved_and_unapproved(self):
        scripts=Path(__file__).resolve().parents[1]/'scripts'
        with tempfile.TemporaryDirectory() as tmp:
            d=Path(tmp);p=d/'state.json';m.save(p,self.ready());source=d/'test.csv';source.write_text('property_id,business_date,currency,available_room_nights,sold_room_nights,room_revenue\nA,2026-11-01,CNY,100,70,21000\n'.replace('\\n','\n'),encoding='utf-8')
            # Use actual newlines in the fixture.
            source.write_text('property_id,business_date,currency,available_room_nights,sold_room_nights,room_revenue'+chr(10)+'A,2026-11-01,CNY,100,70,21000'+chr(10),encoding='utf-8')
            denied=subprocess.run([sys.executable,'-B',str(scripts/'check_daily_metrics.py'),str(source)],capture_output=True,text=True);self.assertEqual(denied.returncode,2)
            allowed=subprocess.run([sys.executable,'-B',str(scripts/'check_daily_metrics.py'),str(source),'--workflow',str(p),'--requirement-version','1','--plan-version','1'],capture_output=True,text=True);self.assertEqual(allowed.returncode,0,allowed.stdout+allowed.stderr);self.assertEqual(json.loads(allowed.stdout)['rows'][0]['metrics']['adr']['value'],'300.00')
if __name__=='__main__':unittest.main()
