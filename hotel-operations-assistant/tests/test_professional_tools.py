import copy
from datetime import timedelta
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import professional_tools as p
import bound_execution as b
import workflow_guard as w
from local_memory import MemoryStore

def example(name):return json.loads((ROOT/"assets"/"professional-examples"/(name+".json")).read_text(encoding="utf-8"))

class ProfessionalTests(unittest.TestCase):
    def test_channel_net_and_not_adr(self):
        r=p.channel(example("channel"))["rows"]
        self.assertEqual([x["contribution"] for x in r],["2690.00","2664.00"])
        self.assertEqual(r[0]["contribution_per_room_night"],"269.00")
    def test_channel_zero_nights(self):
        d=example("channel");d["rows"][0]["room_nights"]=0
        self.assertIsNone(p.channel(d)["rows"][0]["contribution_per_room_night"])
    def test_missing_cost_not_zero(self):
        d=example("channel");del d["rows"][0]["commission"]
        with self.assertRaises(ValueError):p.channel(d)
    def test_duplicate_channel_not_sum(self):
        d=example("channel");d["rows"].append(d["rows"][0])
        with self.assertRaises(ValueError):p.channel(d)
    def test_group_displacement(self):
        r=p.group(example("group"))
        self.assertEqual(r["nights"][0]["displaced_room_nights"],15)
        self.assertEqual(r["incremental_contribution"],"-137.50")
    def test_group_low_demand(self):
        d=example("group");d["nights"][0]["additional_transient_demand"]=5
        r=p.group(d);self.assertEqual(r["incremental_contribution"],"4700.00")
    def test_group_over_capacity_reject(self):
        d=example("group");d["nights"][0]["group_rooms"]=31
        with self.assertRaises(ValueError):p.group(d)
    def test_group_per_night_not_average(self):
        d=example("group");d["context"]["period_end"]="2026-11-02"
        r=copy.deepcopy(d["nights"][0]);r["stay_date"]="2026-11-02";r["additional_transient_demand"]=0
        d["nights"].append(r)
        self.assertEqual(p.group(d)["incremental_contribution"],"4562.50")
    def test_group_rate_reject(self):
        d=example("group");d["nights"][0]["group_commission_rate"]="15"
        with self.assertRaises(ValueError):p.group(d)
    def test_ota_difference_and_not_due(self):
        rs=p.ota(example("ota"))["rows"]
        self.assertEqual(rs[0]["difference"],"-10.00")
        self.assertEqual(rs[1]["status"],"not_due_no_actual")
    def test_ota_unmatched_actual(self):
        d=example("ota");d["actual"].append(dict(channel="OTA-A",reservation_id="009",settlement_id="X",net_paid="30.00"))
        self.assertEqual(p.ota(d)["rows"][-1]["status"],"unmatched_actual")
    def test_ota_duplicate_reject(self):
        d=example("ota");d["actual"].append(d["actual"][0])
        with self.assertRaises(ValueError):p.ota(d)
    def test_aging_boundary_and_credit(self):
        r=p.aging(example("aging"))
        self.assertEqual([x["bucket"] for x in r["rows"]],["not_due","31_60","credit_balance"])
        self.assertEqual(r["totals"]["credit_balance"],"-20.00")
    def test_aging_all_bucket_boundaries(self):
        for days,bucket in [(0,"not_due"),(1,"1_30"),(30,"1_30"),(31,"31_60"),(60,"31_60"),(61,"61_90"),(90,"61_90"),(91,"over_90")]:
            with self.subTest(days=days):
                d=example("aging");r=d["rows"][0];r["invoice_date"]="2026-01-01";r["due_date"]=(p.day(d["context"]["as_of"])-timedelta(days=days)).isoformat();d["rows"]=[r]
                self.assertEqual(p.aging(d)["rows"][0]["bucket"],bucket)
    def test_cash_rollforward(self):
        r=p.cash(example("cash"))
        self.assertEqual(r["weeks"][0]["closing_cash"],"9500.00")
        self.assertEqual(r["weeks"][1]["opening_cash"],"9500.00")
        self.assertEqual(r["closing_cash"],"15500.00")
    def test_cash_missing_week_reject(self):
        d=example("cash");d["weeks"].pop()
        with self.assertRaises(ValueError):p.cash(d)
    def test_cash_reordered_reject(self):
        d=example("cash");d["weeks"][1],d["weeks"][2]=d["weeks"][2],d["weeks"][1]
        with self.assertRaises(ValueError):p.cash(d)
    def test_cash_funding_gap(self):
        d=example("cash");d["opening_cash"]="0.00"
        self.assertTrue(p.cash(d)["weeks"][0]["negative_cash"])
    def test_pnl_excluded_costs_label(self):
        r=p.pnl(example("pnl"));self.assertEqual(r["departmental_profit_total"],"19500.00");self.assertEqual(r["result_after_undistributed_cost"],"15500.00")
        self.assertNotIn("gop",r)
    def test_money_invalid_and_decimal_exactness(self):
        for v in [None,0.1,"1,000","NaN","1.001",""]:
            with self.assertRaises(ValueError):p.money(v)
        self.assertEqual(p.fmt(p.money("0.10")+p.money("0.20")),"0.30")
    def test_context_required(self):
        d=example("channel");d["context"]["tax_basis"]="unknown"
        with self.assertRaises(ValueError):p.channel(d)
    def test_facts_unknown_not_zero(self):
        r=p.facts(example("facts"));self.assertEqual(r["usable_claim_ids"],["F03"])
    def test_facts_conflicting_approved_blocked(self):
        d=example("facts");r=copy.deepcopy(d["claims"][2]);r["claim_id"]="F04";r["value"]="USD";d["claims"].append(r)
        result=p.facts(d);self.assertEqual(result["usable_claim_ids"],[]);self.assertEqual(len(result["conflicts"]),1)
    def test_facts_expired_not_use(self):
        d=example("facts");d["claims"][2]["valid_until"]="2026-11-15";self.assertEqual(p.facts(d)["usable_claim_ids"],[])
    def test_facts_missing_confirmation(self):
        d=example("facts");del d["claims"][2]["message_ref"]
        with self.assertRaises(ValueError):p.facts(d)
    def test_import_preserves_id_and_raw(self):
        d=example("import-config");raw=(ROOT/"assets/professional-examples/import-source.csv").read_bytes()
        r=p.import_csv(d,raw)
        self.assertTrue(r["ready_for_analysis"]);self.assertEqual(r["rows"][0]["values"]["reservation_id"],"001");self.assertEqual(r["rows"][0]["raw"]["房费"],"400.00")
    def test_import_bad_value_and_duplicate_not_drop(self):
        d=example("import-config");raw="订单号,营业日,房费,房晚\n001,2026-11-01,400,1\n001,2026-11-01,400,1\n002,2026-11-01,,1\n".encode()
        r=p.import_csv(d,raw);self.assertFalse(r["ready_for_analysis"]);self.assertEqual(r["duplicate_source_records"],[[1,2]]);self.assertEqual(len(r["issues"]),1)
    def test_import_duplicate_headers_reject(self):
        with self.assertRaises(ValueError):p.import_csv(example("import-config"),"订单号,订单号\n001,002".encode())
    def test_handover_closed(self):
        self.assertEqual(p.handover(example("handover"))["rows"][0]["status"],"closed")
    def test_handover_unassigned_task(self):
        d=example("handover");d["rows"][0]["events"]=[]
        self.assertEqual(p.handover(d)["rows"][0]["status"],"queued")
    def test_handover_no_inspection_cannot_close(self):
        d=example("handover");d["rows"][0]["events"].pop(3)
        with self.assertRaises(ValueError):p.handover(d)
    def test_handover_failed_cannot_close(self):
        d=example("handover");d["rows"][0]["events"][3]["inspection_result"]="fail"
        with self.assertRaises(ValueError):p.handover(d)
    def test_handover_completion_not_close(self):
        d=example("handover");d["rows"][0]["events"]=d["rows"][0]["events"][:3]
        self.assertFalse(p.handover(d)["rows"][0]["closed"])
    def test_handover_bad_time_order(self):
        d=example("handover");d["rows"][0]["events"][1]["at"]="2026-11-16T07:00:00+08:00"
        with self.assertRaises(ValueError):p.handover(d)

class BoundTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.dir=Path(self.tmp.name)
        self.source=self.dir/"input.json";self.source.write_text(json.dumps(example("channel")),encoding="utf-8")
        self.job=self.dir/"job.json";self.out=self.dir/"out"/"result.json";self.state=self.dir/"state.json"
        self.payload={"schema":1,"operation":"channel","input_files":{"data":{"path":str(self.source),"sha256":b.digest(self.source.read_bytes())}},"output_root":str(self.out.parent),"output_file":str(self.out)}
        self.writejob()
        s=w.initial("Fictional unit test","No real hotel data")
        s=w.transition(s,"confirm_requirement",{"requirement_version":1,"quote":"Fictional test requirement","message_ref":"fictional-req"})
        self.plan={"id":"A","description":"Fictional local job","deliverables":"JSON","constraints":"Test only","actions":["metrics"],"job_sha256":[b.digest(self.job.read_bytes())]}
        s=w.transition(s,"propose_plans",{"plans":[self.plan]})
        self.pending=s
        s=w.transition(s,"confirm_plan",{"requirement_version":1,"plan_version":1,"plan_id":"A","quote":"Fictional choose A","message_ref":"fictional-plan"})
        w.save(self.state,s)
    def writejob(self):self.job.write_text(json.dumps(self.payload),encoding="utf-8")
    def execute(self):return b.execute(self.job,self.state,1,1)
    def test_bound_run_receipt(self):
        r=self.execute();self.assertEqual(r["status"],"completed");self.assertEqual(r["output_sha256"],b.digest(self.out.read_bytes()));self.assertEqual(r["acceptance"],"pending_user_review")
    def test_changed_input_denied_no_output(self):
        self.source.write_text("{}",encoding="utf-8")
        with self.assertRaises(ValueError):self.execute()
        self.assertFalse(self.out.exists())
    def test_changed_job_denied(self):
        self.payload["output_file"]=str(self.dir/"different.json");self.writejob()
        with self.assertRaises(ValueError):self.execute()
        self.assertFalse(self.out.exists())
    def test_pending_plan_denied(self):
        w.save(self.state,self.pending)
        with self.assertRaises(ValueError):self.execute()
        self.assertFalse(self.out.parent.exists())
    def test_old_version_denied(self):
        with self.assertRaises(ValueError):b.execute(self.job,self.state,1,0)
    def test_no_overwrite(self):
        self.execute();raw=self.out.read_bytes()
        with self.assertRaises(ValueError):self.execute()
        self.assertEqual(self.out.read_bytes(),raw)
    def test_root_escape(self):
        self.payload["output_file"]=str(self.dir/"escape.json");self.writejob()
        with self.assertRaises(ValueError):b.inspect_job(self.job.read_bytes())
    def test_calculation_failure_has_receipt(self):
        d=example("channel");d["rows"][0]["commission"]=""
        self.source.write_text(json.dumps(d),encoding="utf-8")
        self.payload["input_files"]["data"]["sha256"]=b.digest(self.source.read_bytes());self.writejob()
        s=json.loads(self.state.read_text());s["plans"][0]["job_sha256"]=[b.digest(self.job.read_bytes())];w.save(self.state,s)
        # State mutation is fixture setup only, never an approved business pattern.
        with self.assertRaises(ValueError):self.execute()
        receipt=json.loads(self.out.with_name(self.out.name+".receipt.json").read_text())
        self.assertEqual(receipt["status"],"failed");self.assertFalse(self.out.exists())
    def test_cli_blocks_without_workflow(self):
        r=subprocess.run([sys.executable,"-B",str(ROOT/"scripts/bound_execution.py"),"--job",str(self.job)],capture_output=True)
        self.assertNotEqual(r.returncode,0);self.assertFalse(self.out.exists())

class LessonTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.store=MemoryStore(self.tmp.name)
        self.lesson=dict(kind="lesson",title="Fictional rejected cloud route",scope="DEMO",problem="Cloud route declined",outcome="rejected",reason="Fictional preference for local method",alternative="Local file",limitations="This scenario only",feedback_quote="Fictional feedback",confirmation_quote="Fictional save authorization",review_after="2026-12-01",tags=["OCR"])
    def test_lesson_requires_consent(self):
        with self.assertRaises(ValueError):self.store.put(self.lesson)
        self.assertFalse(self.store.path.exists())
    def test_lesson_persist_and_search(self):
        saved=self.store.put(self.lesson,True);r=MemoryStore(self.tmp.name).summaries("lesson","OCR")
        self.assertEqual(r[0]["id"],saved["id"]);self.assertEqual(r[0]["outcome"],"rejected")
    def test_lesson_does_not_replace_preference(self):
        pref=dict(kind="preference",title="Format",scope="DEMO",key="format",value="XLSX",confirmation_quote="Fictional save")
        r=self.store.put(pref,True)
        with self.assertRaises(ValueError):self.store.put(self.lesson,True,r["id"])
    def test_lesson_invalid_review_date(self):
        self.lesson["review_after"]="not-a-date"
        with self.assertRaises(ValueError):self.store.put(self.lesson,True)

if __name__=="__main__":unittest.main()

