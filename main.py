import json
from datetime import date
import streamlit as st
import os
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

st.set_page_config(page_title="Continued-Stay Scoring", page_icon="CS", layout="wide")

D = [
("Safety & acuity", "Withdrawal, biomedical, risk, and clinical-instability considerations.", [("risk","Risk of harm","Risk of harm",
                                                                                                [("None / no indicators",0),("Mild ideation, no plan or intent",1),
                                                                                                 ("Moderate — needs structured environment to stay safe",3),
                                                                                                 ("High, acute — needs close monitoring",4)]),
                                                                                                 ("biomedical","ASAM Dim. 1-2","Medical / withdrawal instability requiring monitoring at this level",
                                                                                                  [("None / medically stable",0),("Mild, manageable with routine monitoring",1),
                                                                                                   ("Moderate, needs structured medical oversight",3),("Severe, needs 24-hour medical monitoring",4)]),
                                                                                                   ("psychiatricSeverity","ASAM Dim. 3 / LOCG","Psychiatric / behavioral symptom severity",
                                                                                                    [("Stable, mild symptoms",0),("Moderate symptoms",2),("Marked symptoms, significant distress",3),
                                                                                                     ("Severe, unstable presentation",4)])]),
("Function & engagement", "Reflects the payer's active-treatment requirement.", [("functionalImpairment","Functional status","Functional impairment preventing safe step-down",
                                                                                  [("Minimal impairment",0),("Moderate impairment",2),("Marked impairment",3),("Severe impairment",4)]),
                                                                                  ("engagement","Active treatment","Active treatment engagement this review period",
                                                                                   [("Refusing / non-adherent",0),("Minimal engagement",1),("Partial engagement",2),("Full, active engagement",4)]),
                                                                                   ("trajectory","Response to tx","Clinical trajectory since last review",
                                                                                    [("Improved & stabilized — likely ready for a lower level",0),("No meaningful change / plateaued",2),
                                                                                     ("Worsening / decompensating",3),("Improving, but still clinically fragile without this structure",4)])]),
("Setting & planning", "Recovery environment, lower-level rule-out, discharge planning, and LOS.", [("environment","ASAM Dim. 5-6","Recovery / living environment safety & support",
                                                                                                     [("Safe & supportive, available now",0),("Not yet assessed",1),("Some risk factors / limited support",2),
                                                                                                      ("Unsafe or no support available",4)]),
                                                                                                      ("lrocAttempt","Less-restrictive rule-out","Lower level of care: attempted, or clinically contraindicated?",
                                                                                                       [("Not attempted, no contraindication documented",0),("N/A — appropriate entry level per assessment",2),
                                                                                                        ("Not attempted, but clinically contraindicated & documented",3),("Attempted and failed at a lower level of care",4)]),
                                                                                                        ("dischargePlanning","Discharge planning","Discharge / step-down planning",
                                                                                                         [("Not documented",0),("Minimal / generic",1),("Present, not updated this period",2),
                                                                                                          ("Robust, updated this review period",3)]),
                                                                                                          ("losVsTypical","LOS benchmark","Length of stay at this level vs. typical benchmark",
                                                                                                           [("Significantly exceeds typical, no new acute factor documented",0),("Moderately exceeds typical, some new factor noted",2),
                                                                                                            ("Within typical range for this level",3),("Exceeds typical, but new acute complication clearly documented",3)])])]
Q = [q for _, _, qs in D for q in qs]

W = {"sud":{"label":"Substance Use Disorder","locs":{"residential":("Residential",14,{"risk":3,"biomedical":3,"psychiatricSeverity":1.5,"functionalImpairment":2,"engagement":2,"trajectory":2.5,"environment":2,"lrocAttempt":1.5,"dischargePlanning":1,"losVsTypical":1.5}),"php":("Partial Hospitalization ",10,{"risk":2,"biomedical":2,"psychiatricSeverity":2,"functionalImpairment":2.5,"engagement":2.5,"trajectory":2.5,"environment":2,"lrocAttempt":1.5,"dischargePlanning":1.5,"losVsTypical":1.5}),"iop":("Intensive Outpatient",21,{"risk":1,"biomedical":.5,"psychiatricSeverity":2,"functionalImpairment":3,"engagement":3,"trajectory":2.5,"environment":2,"lrocAttempt":1,"dischargePlanning":1.5,"losVsTypical":1.5})}},"mh":{"label":"Mental Health","locs":{"residential":("Residential / Inpatient",10,{"risk":3.5,"biomedical":1,"psychiatricSeverity":3,"functionalImpairment":2.5,"engagement":1.5,"trajectory":2.5,"environment":2,"lrocAttempt":1.5,"dischargePlanning":1,"losVsTypical":1.5}),"php":("Partial Hospitalization",10,{"risk":2,"biomedical":.5,"psychiatricSeverity":2.5,"functionalImpairment":3,"engagement":2.5,"trajectory":2.5,"environment":2,"lrocAttempt":1.5,"dischargePlanning":1.5,"losVsTypical":1.5}),"iop":("Intensive Outpatient",21,{"risk":1,"biomedical":.25,"psychiatricSeverity":2,"functionalImpairment":3,"engagement":3,"trajectory":2.5,"environment":2,"lrocAttempt":1,"dischargePlanning":1.5,"losVsTypical":1.5})}}}
SAMPLES={"Approve — SUD Residential":("sud","residential",9,14,[3,3,1,2,3,3,3,1,3,2]),"Borderline — MH PHP":("mh","php",16,10,[1,0,1,1,2,1,2,1,1,1]),"High denial risk — SUD IOP":("sud","iop",40,21,[0,0,0,0,3,0,0,1,2,0])}

for k,v in {"track":"sud","loc":"residential","answers":{},"evidence":{},"days":0,"benchmark":14,"revision":0}.items(): st.session_state.setdefault(k,v)

def calculate(a, track, loc, days, bench):
    weights=W[track]["locs"][loc][2]; max_score=sum(weights[q[0]]*max(x[1] for x in q[3]) for q in Q)
    value=sum(weights[q[0]]*q[3][a[q[0]]][1] for q in Q if q[0] in a); pct=value/max_score*100
    flags=[]; docs=[]
    if a.get("risk")==3 and loc in ("php","iop"): pct=min(pct,30); flags.append("Acute risk exceeds what this outpatient level is designed to manage; evaluate a higher level of care.")
    if a.get("trajectory")==0 and a.get("functionalImpairment") in (0,1): pct=min(pct,45); flags.append("Stabilization with low residual impairment raises step-down and denial-risk concerns.")
    if a.get("engagement")==0: pct=min(pct,35); flags.append("Lack of active participation may not meet the active-treatment requirement.")
    if a.get("losVsTypical")==0: pct-=15; flags.append("LOS substantially exceeds the benchmark without a new acute factor documented.")
    if a.get("dischargePlanning")==0: docs.append("Add a discharge/step-down plan with target level and timeframe.")
    if a.get("lrocAttempt")==0: docs.append("Document why a lower level is unsafe or insufficient, or that it was tried and failed.")
    if a.get("environment")==1: docs.append("Complete and document the recovery/living-environment assessment.")
    if a.get("psychiatricSeverity", -1)>=3: docs.append("Add specific current symptom examples rather than only a severity rating.")
    if days>bench*1.5: docs.append(f"Days at this level ({days}) are well beyond the {bench}-day benchmark; add a same-day clinical justification.")
    complete=len(a)==len(Q); pct=max(0,min(100,pct)); band="Awaiting answers" if not complete else "Strong support — likely approved" if pct>=75 else "Borderline — document further" if pct>=50 else "High denial risk"
    return pct,complete,band,flags,docs

def extract(note):
    schema=[{"id":q[0],"question":q[2],"options":[{"index":i,"text":x[0]} for i,x in enumerate(q[3])]} for q in Q]
    prompt="You are a behavioral-health utilization-review assistant. Choose one option index only when explicitly supported. Return ONLY JSON: {question_id: {optionIndex: integer|null, evidence: short quote|null}}. Do not infer.\nQuestions:\n"+json.dumps(schema)+"\nClinical note:\n"+note
    response=client.chat.completions.create(model="openai/gpt-oss-120b",messages=[{"role":"user","content":prompt}],temperature=0,response_format={"type":"json_object"})
    return json.loads(response.choices[0].message.content)

st.markdown("""<style>
.block-container { padding-top:1.5rem; }
.score { color:#eaf1f0; padding:1.2rem; border-radius:10px; }

@media (min-width: 900px) {
    
    .st-key-app_shell [data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"]:nth-child(3)) {
        align-items:flex-start;
    }
    .st-key-app_shell [data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"]:nth-child(3)) > [data-testid="stColumn"]:nth-child(1) > div,
    .st-key-app_shell [data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"]:nth-child(3)) > [data-testid="stColumn"]:nth-child(3) > div {
        position:sticky;
        top:1rem;
    }
}
</style>""",unsafe_allow_html=True)
st.title("Continued-Stay Scoring");

shell = st.container(key="app_shell")
left,mid,right=shell.columns([1,1.8,1.15],gap="large")
with left:
    st.subheader("Case setup")
    track_name=st.radio("Clinical track",[W[x]["label"] for x in W],index=list(W).index(st.session_state.track),horizontal=True); track=next(x for x in W if W[x]["label"]==track_name)
    if track!=st.session_state.track: st.session_state.track,st.session_state.loc,st.session_state.answers,st.session_state.evidence=track,"residential",{},{};st.session_state.benchmark=W[track]["locs"]["residential"][1];st.session_state.revision+=1;st.rerun()
    loc=st.radio("Level of care",list(W[track]["locs"]),format_func=lambda x:W[track]["locs"][x][0],index=list(W[track]["locs"]).index(st.session_state.loc))

    if loc!=st.session_state.loc: st.session_state.loc,st.session_state.answers,st.session_state.evidence=loc,{},{};st.session_state.benchmark=W[track]["locs"][loc][1];st.session_state.revision+=1;st.rerun()
    st.session_state.days=st.number_input("Days at current level of care",min_value=0,value=st.session_state.days)
    st.session_state.benchmark=st.number_input("Typical duration benchmark (days)",min_value=1,value=st.session_state.benchmark)
    
    los_key = (st.session_state.days, st.session_state.benchmark)
    if st.session_state.get("los_auto_key") != los_key:
        ratio = st.session_state.days / st.session_state.benchmark
        auto_idx = 2 if ratio <= 1.0 else 1 if ratio <= 1.5 else 0
        st.session_state.answers["losVsTypical"] = auto_idx
        st.session_state.evidence.pop("losVsTypical", None)
        st.session_state.los_auto_key = los_key
        st.session_state.revision += 1
    st.subheader("Sample synthetic cases")
    sample=st.radio("Load a sample",list(SAMPLES),index=None)
    if st.button("Load sample",disabled=sample is None):
        t,l,d,b,vals=SAMPLES[sample];st.session_state.track,st.session_state.loc,st.session_state.days,st.session_state.benchmark=t,l,d,b;st.session_state.answers={q[0]:v for q,v in zip(Q,vals)};st.session_state.evidence={};st.session_state.los_auto_key=(d,b);st.session_state.revision+=1;st.rerun()
    if st.button("Clear form"): st.session_state.answers,st.session_state.evidence,st.session_state.days={},{},0;st.session_state.revision+=1;st.rerun()
    st.subheader("Authorization & billing"); auth_end=st.date_input("Auth end date",value=None)
    
    if auth_end: st.info(f"Days remaining on authorization: {(auth_end-date.today()).days}")
with mid:
    st.subheader("Clinical note (optional)"); note=st.text_area("Paste a progress note or clinical update",height=180,placeholder="Paste a clinical note here…")
    if st.button("Extract from note",type="primary"):
        if not note.strip(): st.error("Paste a note first.")
        else:
            try:
                with st.spinner("Reading note…"): result=extract(note)
                filled=0
                for q in Q:
                    item=result.get(q[0],{}); idx=item.get("optionIndex")
                    if isinstance(idx,int) and 0<=idx<len(q[3]): st.session_state.answers[q[0]]=idx;st.session_state.evidence[q[0]]=item.get("evidence") or "";filled+=1
          
                st.session_state.revision+=1
                st.success(f"Extracted {filled} of {len(Q)} fields. Review every answer before relying on the score.")
            except Exception as exc: st.error(f"Groq extraction failed: {exc}")
    criteria_scroller = st.container(height=800, border=False, key="criteria_scroller")
    with criteria_scroller:
        st.subheader("Continued-Stay Criteria Review")
        for domain,desc,questions in D:
            st.markdown(f"#### {domain}");st.caption(desc)
            for qid,cite,label,options in questions:
                current=st.session_state.answers.get(qid); choices=[x[0] for x in options]
                question_col, cite_col = st.columns([5, 1])
                question_col.markdown(f"**{label}**")
                cite_col.caption(f"`{cite}`")
                answer=st.pills(
                    f"Select a response for {label}",
                    options=choices,
                    format_func=lambda option: option,
                    selection_mode="single",
                    default=choices[current] if current is not None else None,
                    key=f"answer_{st.session_state.revision}_{qid}",
                    label_visibility="collapsed",
                )
                if answer is not None:
                    idx=choices.index(answer)
                    if current!=idx:st.session_state.evidence.pop(qid,None)
                    st.session_state.answers[qid]=idx
                if st.session_state.evidence.get(qid):st.caption(f'From note: “{st.session_state.evidence[qid]}”')
with right:
    pct,complete,band,flags,docs=calculate(st.session_state.answers,track,loc,st.session_state.days,st.session_state.benchmark)
    st.markdown("<div class='score'>",unsafe_allow_html=True);st.caption("CONTINUED-STAY SCORE");st.markdown(f"# {round(pct) if complete else '—'} / 100");st.write(f"**{band}**");st.caption(f"{len(st.session_state.answers)} / {len(Q)} answered");st.markdown("</div>",unsafe_allow_html=True)
    st.subheader("Weighted ledger"); weights=W[track]["locs"][loc][2]
    for q in Q:
        if q[0] in st.session_state.answers:st.write(f"{q[1]}: **+{weights[q[0]]*q[3][st.session_state.answers[q[0]]][1]:.1f}**")
    if flags:
        st.subheader("Flags for UR / peer-to-peer")
        for item in flags:st.warning(item)
    if docs:
        st.subheader("Suggested documentation to add")
        for item in docs:st.info(item)
    cadence={"residential":"Every 3–5 days","php":"Every 5–7 days","iop":"Every 7–14 days"}[loc];st.caption(f"Suggested review cadence: {cadence}")
    summary=f"Athon Continued-Stay Summary — {W[track]['label']} / {W[track]['locs'][loc][0]}\nDays at level: {st.session_state.days} (benchmark {st.session_state.benchmark})\nScore: {round(pct) if complete else 'incomplete'} / 100 — {band}"
    