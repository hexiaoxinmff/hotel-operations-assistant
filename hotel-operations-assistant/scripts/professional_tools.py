"""Local hotel scenario calculations. No network, accounting posting or forecasts inferred."""
import csv
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import hashlib
import io
import json
import re

def text(d, key):
    v=d.get(key)
    if not isinstance(v,str) or not v.strip(): raise ValueError("Missing text: "+key)
    return v

def day(v):
    if not isinstance(v,str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}",v): raise ValueError("Use YYYY-MM-DD")
    return date.fromisoformat(v)

def money(v, signed=False):
    if not isinstance(v,str) or not re.fullmatch(r"-?\d+(\.\d{1,2})?",v): raise ValueError("Money must be a decimal string, max 2 places")
    n=Decimal(v)
    if not signed and n<0: raise ValueError("Negative amount not permitted")
    return n

def count(v):
    if type(v) is not int or v<0: raise ValueError("Count must be nonnegative integer")
    return v

def rate(v):
    if not isinstance(v,str) or not re.fullmatch(r"0(\.\d+)?|1(\.0+)?",v): raise ValueError("Rate must be string between 0 and 1")
    return Decimal(v)

def fmt(v): return str(v.quantize(Decimal(".01"),rounding=ROUND_HALF_UP))

def context(d):
    c=d.get("context",{})
    for k in ("property_id","currency","tax_basis","source","basis"): text(c,k)
    if not re.fullmatch("[A-Z]{3}",c["currency"]): raise ValueError("Currency must be ISO-like 3 letters; no FX conversion")
    if c["tax_basis"] not in ("tax_inclusive","tax_exclusive","not_applicable"): raise ValueError("Unknown tax basis")
    start,end=day(c.get("period_start")),day(c.get("period_end"))
    day(c.get("as_of"))
    if start>end: raise ValueError("Period reversed")
    return c

def rows(d,key="rows"):
    r=d.get(key)
    if not isinstance(r,list) or not r or not all(isinstance(x,dict) for x in r): raise ValueError("Nonempty row objects required: "+key)
    return r

def unique(rs,keys):
    seen=set()
    for r in rs:
        item=tuple(text(r,k) for k in keys)
        if item in seen: raise ValueError("Duplicate key requires review: "+str(item))
        seen.add(item)

def channel(d):
    c=context(d);rs=rows(d);unique(rs,["channel"])
    out=[]
    for i,r in enumerate(rs,1):
        n=count(r.get("room_nights"))
        m={k:money(r.get(k)) for k in ("gross_room_revenue","refunds","commission","payment_fee","marketing_cost","variable_room_cost","ancillary_contribution")}
        net=m["gross_room_revenue"]-m["refunds"]-m["commission"]-m["payment_fee"]-m["marketing_cost"]-m["variable_room_cost"]+m["ancillary_contribution"]
        out.append({"source_record":i,"channel":r["channel"],"room_nights":n,"contribution":fmt(net),"contribution_per_room_night":fmt(net/n) if n else None})
    return {"context":c,"rows":out,"limitations":["Scenario contribution, not GOP or bank cash. Ancillary contribution is already net; do not subtract its costs twice.","All input costs must belong to the same confirmed period and basis."]}

def group(d):
    c=context(d);rs=rows(d,"nights");seen=set();out=[];total=Decimal(0)
    for i,r in enumerate(rs,1):
        dt=day(r.get("stay_date"))
        if dt in seen or not day(c["period_start"])<=dt<=day(c["period_end"]): raise ValueError("Duplicate/out-of-period night")
        seen.add(dt)
        remaining=count(r.get("remaining_rooms"));g=count(r.get("group_rooms"));demand=count(r.get("additional_transient_demand"))
        if g>remaining: raise ValueError("Group exceeds remaining capacity; no oversell assumed")
        gr,tc,vc=[money(r.get(k)) for k in ("group_rate","transient_rate","variable_cost_per_room")]
        gc,tr=rate(r.get("group_commission_rate")),rate(r.get("transient_commission_rate"))
        ancillary=money(r.get("group_ancillary_contribution"),signed=True);extra=money(r.get("extra_group_cost"))
        displaced=min(demand,remaining)-min(demand,remaining-g)
        contribution=Decimal(g)*(gr*(1-gc)-vc)+ancillary-extra
        foregone=Decimal(displaced)*(tc*(1-tr)-vc)
        delta=contribution-foregone;total+=delta
        out.append({"source_record":i,"stay_date":r["stay_date"],"displaced_room_nights":displaced,"group_contribution":fmt(contribution),"foregone_transient_contribution":fmt(foregone),"incremental_contribution":fmt(delta)})
    return {"context":c,"nights":out,"incremental_contribution":fmt(total),"interpretation":"positive supports further commercial review; not automatic acceptance","limitations":["Remaining capacity excludes existing commitments and out-of-order rooms.","Additional transient demand is supplied scenario input, not a forecast created by this tool.","No wash, room-type substitution, meeting-space displacement or strategic account value modeled. Run explicit low/base/high demand cases separately."]}

def ota(d):
    c=context(d);expected=rows(d,"expected");actual=d.get("actual")
    if not isinstance(actual,list) or not all(isinstance(x,dict) for x in actual): raise ValueError("actual must be a list; empty means no settlement records supplied")
    keys=["channel","reservation_id","settlement_id"]
    unique(expected,keys);unique(actual,keys)
    exp={tuple(text(r,k) for k in keys):r for r in expected}
    act={tuple(text(r,k) for k in keys):r for r in actual}
    out=[]
    for key in sorted(set(exp)|set(act)):
        e,a=exp.get(key),act.get(key)
        net=None
        if e:
            net=money(e.get("gross"))-money(e.get("refunds"))-money(e.get("commission"))-money(e.get("fees"))
            day(e.get("due_date"))
        paid=money(a.get("net_paid"),signed=True) if a else None
        difference=paid-net if a and e else None
        status="matched" if difference==0 else "difference" if difference is not None else "missing_actual" if e else "unmatched_actual"
        if status=="missing_actual" and day(e["due_date"])>day(c["as_of"]): status="not_due_no_actual"
        out.append(dict(zip(keys,key),expected_net=fmt(net) if net is not None else None,actual_net=fmt(paid) if paid is not None else None,difference=fmt(difference) if difference is not None else None,status=status))
    return {"context":c,"rows":out,"limitations":["One row per confirmed settlement key. Split payments must be explicitly mapped/aggregated before use.","Missing actual is not proof of nonpayment. Deposits, chargebacks, invoices and bank receipts need separate verification."]}

def aging(d):
    c=context(d);rs=rows(d);unique(rs,["invoice_id"]);out=[];totals={k:Decimal(0) for k in ("not_due","1_30","31_60","61_90","over_90","credit_balance")}
    asof=day(c["as_of"])
    for i,r in enumerate(rs,1):
        issued,due=day(r.get("invoice_date")),day(r.get("due_date"))
        if issued>asof or due<issued: raise ValueError("Invoice dates inconsistent with as-of")
        balance=money(r.get("original_amount"))-money(r.get("credits"))-money(r.get("paid"))
        overdue=(asof-due).days
        bucket="credit_balance" if balance<0 else "not_due" if overdue<=0 else "1_30" if overdue<=30 else "31_60" if overdue<=60 else "61_90" if overdue<=90 else "over_90"
        totals[bucket]+=balance
        out.append({"source_record":i,"invoice_id":r["invoice_id"],"balance":fmt(balance),"days_past_due":max(overdue,0),"bucket":bucket})
    return {"context":c,"rows":out,"totals":{k:fmt(v) for k,v in totals.items()},"limitations":["Paid and credits must be cumulative through as_of only. Due date comes from confirmed terms.","Credit balances are shown separately; no bad-debt policy or DSO threshold inferred."]}

CASH_IN=("guest_receipts","other_receipts","financing_in")
CASH_OUT=("operating_payments","tax_payments","capex","debt_service","owner_distributions")

def cash(d):
    c=context(d);rs=rows(d,"weeks")
    if len(rs)!=13: raise ValueError("Exactly 13 consecutive weeks required; missing weeks cannot be assumed zero")
    start=day(c["period_start"])
    if day(c["period_end"])!=start+timedelta(days=90): raise ValueError("Cash period must cover 13 full weeks inclusive")
    opening=money(d.get("opening_cash"),signed=True);out=[]
    for i,r in enumerate(rs):
        if day(r.get("week_start"))!=start+timedelta(days=7*i): raise ValueError("Weeks must be consecutive and ordered")
        amounts={k:money(r.get(k)) for k in CASH_IN+CASH_OUT}
        receipts=sum((amounts[k] for k in CASH_IN),Decimal(0));payments=sum((amounts[k] for k in CASH_OUT),Decimal(0))
        close=opening+receipts-payments
        out.append({"week":i+1,"week_start":r["week_start"],"opening_cash":fmt(opening),"inflows":fmt(receipts),"outflows":fmt(payments),"closing_cash":fmt(close),"negative_cash":close<0})
        opening=close
    return {"context":c,"weeks":out,"closing_cash":fmt(opening),"limitations":["User-supplied cash scenario, not automated demand/revenue prediction.","Use cash timing, not accounting revenue; confirm deposit/refund/tax/financing classification to prevent double counts.","Negative cash flags a funding gap, not insolvency or a financing recommendation."]}

def pnl(d):
    c=context(d);rs=rows(d);unique(rs,["department"]);out=[];total=Decimal(0)
    for i,r in enumerate(rs,1):
        revenue=money(r.get("revenue"),signed=True)
        expense=sum((money(r.get(k)) for k in ("cost_of_sales","payroll","other_direct_cost")),Decimal(0))
        profit=revenue-expense;total+=profit
        out.append({"source_record":i,"department":r["department"],"revenue":fmt(revenue),"direct_expense":fmt(expense),"departmental_profit":fmt(profit)})
    undistributed=money(d.get("undistributed_cost"))
    return {"context":c,"rows":out,"departmental_profit_total":fmt(total),"result_after_undistributed_cost":fmt(total-undistributed),"limitations":["Management worksheet only, not USALI-compliant audited P&L or net profit.","Excluded items and allocation policy must be stated in context.basis; do not label result GOP without approved line mapping."]}

def facts(d):
    on=day(d.get("on"));claims=rows(d,"claims");unique(claims,["claim_id"])
    allowed={"unknown","user_confirmed","documented","assumption","disputed","expired"}
    out=[];usable={}
    for r in claims:
        key=text(r,"key");status=r.get("status")
        if status not in allowed: raise ValueError("Unknown claim status")
        text(r,"scope");text(r,"unit");text(r,"owner")
        if status=="unknown":
            if r.get("value") is not None: raise ValueError("Unknown must have null value")
        else:
            if r.get("value") is None: raise ValueError("Known claim requires value")
            sources=rows(r,"sources")
            for s in sources:
                for k in ("source","locator","evidence"):text(s,k)
                if day(s.get("observed_on"))>on: raise ValueError("Future evidence relative to evaluation")
            if status=="user_confirmed":text(r,"confirmation_quote");text(r,"message_ref")
        start=day(r["valid_from"]) if r.get("valid_from") else None
        end=day(r["valid_until"]) if r.get("valid_until") else None
        if start and end and start>end:raise ValueError("Reversed validity")
        eligible=status=="user_confirmed" and (not start or start<=on) and (not end or on<=end)
        identity=(r["scope"],key)
        if eligible:usable.setdefault(identity,[]).append(r["claim_id"])
        out.append({"claim_id":r["claim_id"],"key":key,"scope":r["scope"],"eligible":eligible,"status":status})
    conflicts=[{"scope":s,"key":k,"claim_ids":v} for (s,k),v in usable.items() if len(v)>1]
    blocked={x for v in usable.values() if len(v)>1 for x in v}
    for r in out:
        if r["claim_id"] in blocked:r["eligible"]=False
    return {"on":d["on"],"claims":out,"conflicts":conflicts,"usable_claim_ids":[r["claim_id"] for r in out if r["eligible"]],"limitations":["Eligibility checks structure/status only; no authentication of user quotes or factual truth.","Documented, disputed and assumed values never silently become approved property facts."]}

def import_csv(d,raw):
    c=context(d);mapping=d.get("mapping");schema=d.get("schema")
    if not isinstance(mapping,dict) or not mapping or not isinstance(schema,dict) or set(mapping)!=set(schema): raise ValueError("Explicit same-key mapping/schema required")
    if not all(isinstance(k,str) and isinstance(v,str) and v for k,v in mapping.items()):raise ValueError("Invalid mapping")
    if len(set(mapping.values()))!=len(mapping):raise ValueError("Ambiguous mapping")
    if not set(schema.values())<={"text","date","money","integer"}:raise ValueError("Unsupported transform; no guessed conversion")
    if d.get("encoding","utf-8-sig") not in ("utf-8","utf-8-sig"):raise ValueError("Only explicit UTF-8 CSV supported")
    reader=csv.DictReader(io.StringIO(raw.decode(d.get("encoding","utf-8-sig"))))
    if not reader.fieldnames or len(set(reader.fieldnames))!=len(reader.fieldnames):raise ValueError("Missing/duplicate headers")
    if not set(mapping.values())<=set(reader.fieldnames):raise ValueError("Missing mapped headers")
    out=[];issues=[]
    for i,r in enumerate(reader,1):
        converted={};errors=[]
        if None in r:errors.append("Extra columns")
        for target,source in mapping.items():
            v=r.get(source);kind=schema[target]
            try:
                if kind=="text":
                    if not isinstance(v,str) or not v.strip():raise ValueError("Blank text")
                    converted[target]=v
                elif kind=="date":converted[target]=day(v).isoformat()
                elif kind=="money":converted[target]=fmt(money(v,signed=True))
                else:
                    if not isinstance(v,str) or not re.fullmatch(r"\d+",v):raise ValueError("Invalid integer")
                    converted[target]=int(v)
            except (ValueError,TypeError,InvalidOperation) as e:errors.append(target+": "+str(e))
        if errors:issues.append({"source_record":i,"errors":errors,"raw":r})
        else:out.append({"source_record":i,"raw":r,"values":converted})
    keys=d.get("unique_keys")
    if not isinstance(keys,list) or not keys or not set(keys)<=set(mapping):raise ValueError("Explicit mapped unique_keys required")
    seen={}
    for r in out:seen.setdefault(tuple(str(r["values"][k]) for k in keys),[]).append(r["source_record"])
    duplicates=[v for v in seen.values() if len(v)>1]
    return {"context":c,"source_sha256":hashlib.sha256(raw).hexdigest(),"rows":out,"issues":issues,"duplicate_source_records":duplicates,"ready_for_analysis":not issues and not duplicates,"limitations":["Record numbers are logical CSV records, not physical line numbers.","Original values retained; duplicates and bad values are not dropped or merged.","No PMS/API connection, formula evaluation, automatic currency/tax conversion or macros."]}

OPERATIONS={"channel":channel,"group":group,"ota":ota,"aging":aging,"cash":cash,"pnl":pnl,"facts":facts}

def handover(d):
    c=context(d);rs=rows(d);unique(rs,["task_id"]);out=[]
    transitions={"queued":{"assigned","blocked"},"assigned":{"in_progress","blocked"},"in_progress":{"completed","blocked"},"completed":{"inspected","in_progress","blocked"},"inspected":{"closed","in_progress","blocked"},"blocked":{"assigned","in_progress"},"closed":set()}
    from datetime import datetime
    for r in rs:
        text(r,"task_type");text(r,"location");state="queued";inspection=None;previous=None
        events=r.get("events")
        if not isinstance(events,list) or not all(isinstance(e,dict) for e in events):raise ValueError("events must be a list")
        for e in events:
            target=text(e,"status");text(e,"actor");text(e,"evidence")
            at=datetime.fromisoformat(text(e,"at"))
            if at.tzinfo is None or (previous and at<previous):raise ValueError("Event time must be zoned and ordered")
            if target not in transitions[state]:raise ValueError("Invalid task transition: "+state+" -> "+target)
            if target=="inspected":
                inspection=e.get("inspection_result")
                if inspection not in ("pass","fail"):raise ValueError("Inspection result required")
            elif target=="closed":
                if inspection!="pass":raise ValueError("Failed/unverified task cannot close")
                text(e,"confirmation_quote");text(e,"message_ref")
            elif target in ("in_progress","completed"):inspection=None
            previous=at;state=target
        out.append({"task_id":r["task_id"],"location":r["location"],"status":state,"inspection_result":inspection,"closed":state=="closed"})
    return {"context":c,"rows":out,"limitations":["Validates supplied event records only; no staff dispatch, PMS room-state update or authenticity guarantee.","A cleaning task completion is not a verified sellable-room release."]}
OPERATIONS["handover"]=handover


