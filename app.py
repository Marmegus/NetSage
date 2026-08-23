import os
import json
import traceback
from datetime import datetime
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel

import pandas as pd
from dotenv import load_dotenv
from groq import Groq


# ============================================================
# ENVIRONMENT
# ============================================================

load_dotenv()


# ============================================================
# FASTAPI APP
# ============================================================

app = FastAPI(
    title="NetSage AI - Troubleshooting Assistant"
)


# ============================================================
# GROQ CLIENT
# ============================================================

groq_api_key = os.environ.get("GROQ_API_KEY")

if not groq_api_key:
    print("WARNING: GROQ_API_KEY is not set.")

client = Groq(
    api_key=groq_api_key
)


# ============================================================
# FILE CONFIGURATION
# ============================================================

os.makedirs("logs", exist_ok=True)

# Your main Excel log file
EXCEL_FILE = "logs/ai_review_log.xlsx"

# Columns stored in the Excel file
LOG_COLUMNS = [
    "timestamp",
    "symptom",
    "root_cause",
    "osi_layer",
    "confidence",
    "evidence",
    "next_command",
    "fix_steps",
    "status",
    "notes"
]


# ============================================================
# INITIALIZE EXCEL FILE
# ============================================================

if not os.path.exists(EXCEL_FILE):

    df_init = pd.DataFrame(
        columns=LOG_COLUMNS
    )

    df_init.to_excel(
        EXCEL_FILE,
        index=False,
        engine="openpyxl"
    )


# ============================================================
# PYDANTIC MODELS
# ============================================================

class DiagnosisRequest(BaseModel):
    symptom: str
    show_outputs: str


class DiagnosisData(BaseModel):
    root_cause: str
    osi_layer: str
    confidence: str
    evidence: str
    next_command: str
    fix_steps: List[str]


class FeedbackRequest(BaseModel):
    symptom: str
    diagnosis: DiagnosisData
    status: str
    notes: Optional[str] = ""


# ============================================================
# FRONTEND
# ============================================================

@app.get("/", response_class=HTMLResponse)
def serve_frontend():

    try:

        with open(
            "index.html",
            "r",
            encoding="utf-8"
        ) as f:

            return f.read()

    except FileNotFoundError:

        raise HTTPException(
            status_code=404,
            detail="index.html not found."
        )


# ============================================================
# TRACKER ENDPOINT
# ============================================================

@app.api_route(
    "/hybridaction/zybTrackerStatisticsAction",
    methods=["GET", "POST"]
)
def tracker_statistics():

    return {
        "status": "success",
        "message": "Tracker statistics received."
    }


# ============================================================
# AI DIAGNOSIS
# ============================================================

@app.post("/api/diagnose")
def diagnose_network(req: DiagnosisRequest):

    rule_issues = []

    show_lower = req.show_outputs.lower()


    # --------------------------------------------------------
    # RULE-BASED DETECTION
    # --------------------------------------------------------

    if (
        "down" in show_lower
        and "line protocol is down" in show_lower
    ):

        rule_issues.append({

            "error_type":
                "Layer 1 Physical/Line Down",

            "target":
                "Interface",

            "detail":
                "Detected 'line protocol is down'. "
                "Check physical cabling or transceiver."
        })


    if "native vlan mismatch" in show_lower:

        rule_issues.append({

            "error_type":
                "Layer 2 VLAN Mismatch",

            "target":
                "Trunk Port",

            "detail":
                "CDP/LLDP reports native VLAN mismatch warning."
        })


    # --------------------------------------------------------
    # LLM PROMPT
    # --------------------------------------------------------

    prompt = f"""
You are an expert network engineer analyzing
Cisco Packet Tracer troubleshooting logs.

User Symptom:
{req.symptom}

CLI Show Outputs:
{req.show_outputs}

Provide a structured diagnosis containing:

1. root_cause (string)
2. osi_layer (string, e.g., Layer 1, Layer 2)
3. confidence (string, e.g., High, Medium, Low)
4. evidence (string)
5. next_command (string)
6. fix_steps (list of strings)

Return valid JSON only matching this schema:

{{
    "root_cause": "...",
    "osi_layer": "...",
    "confidence": "...",
    "evidence": "...",
    "next_command": "...",
    "fix_steps": [
        "...",
        "..."
    ]
}}
"""


    # --------------------------------------------------------
    # CALL GROQ
    # --------------------------------------------------------

    try:

        completion = client.chat.completions.create(

            model="openai/gpt-oss-20b",

            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ],

            response_format={
                "type": "json_object"
            }
        )


        raw_content = (
            completion
            .choices[0]
            .message
            .content
        )


        diagnosis_json = json.loads(
            raw_content
        )


    except json.JSONDecodeError as e:

        traceback.print_exc()

        raise HTTPException(
            status_code=500,
            detail=f"Invalid JSON returned by LLM: {str(e)}"
        )


    except Exception as e:

        traceback.print_exc()

        raise HTTPException(
            status_code=500,
            detail=f"LLM Error: {str(e)}"
        )


    # --------------------------------------------------------
    # RETURN DIAGNOSIS
    # --------------------------------------------------------

    return {

        "rule_issues":
            rule_issues,

        "diagnosis":
            diagnosis_json
    }


# ============================================================
# LOG AI FEEDBACK INTO XLSX
# ============================================================

@app.post("/api/log-feedback")
def log_feedback(req: FeedbackRequest):

    try:

        # ----------------------------------------------------
        # READ EXISTING EXCEL FILE
        # ----------------------------------------------------

        if os.path.exists(EXCEL_FILE):

            try:

                df = pd.read_excel(
                    EXCEL_FILE,
                    engine="openpyxl"
                )

            except Exception:

                traceback.print_exc()

                df = pd.DataFrame(
                    columns=LOG_COLUMNS
                )

        else:

            df = pd.DataFrame(
                columns=LOG_COLUMNS
            )


        # ----------------------------------------------------
        # CREATE NEW ROW
        # ----------------------------------------------------

        new_row = {

            "timestamp":
                datetime.now().strftime(
                    "%Y-%m-%d %H:%M:%S"
                ),

            "symptom":
                req.symptom,

            "root_cause":
                req.diagnosis.root_cause,

            "osi_layer":
                req.diagnosis.osi_layer,

            "confidence":
                req.diagnosis.confidence,

            "evidence":
                req.diagnosis.evidence,

            "next_command":
                req.diagnosis.next_command,

            "fix_steps":
                " | ".join(
                    req.diagnosis.fix_steps
                ),

            "status":
                req.status,

            "notes":
                req.notes or ""
        }


        # ----------------------------------------------------
        # APPEND NEW ROW
        # ----------------------------------------------------

        df = pd.concat(
            [
                df,
                pd.DataFrame([new_row])
            ],
            ignore_index=True
        )


        # ----------------------------------------------------
        # SAVE BACK TO XLSX
        # ----------------------------------------------------

        df.to_excel(
            EXCEL_FILE,
            index=False,
            engine="openpyxl"
        )


        return {

            "status":
                "success",

            "message":
                "Feedback successfully logged."
        }


    except Exception as e:

        traceback.print_exc()

        raise HTTPException(

            status_code=500,

            detail=
                f"Failed to log feedback: {str(e)}"
        )


# ============================================================
# DOWNLOAD EXISTING EXCEL FILE
# ============================================================

@app.get("/api/analytics/export")
def export_analytics_report():

    try:

        # ----------------------------------------------------
        # CHECK FILE EXISTS
        # ----------------------------------------------------

        if not os.path.exists(EXCEL_FILE):

            raise HTTPException(

                status_code=404,

                detail=
                    "Excel log file does not exist."
            )


        # ----------------------------------------------------
        # DOWNLOAD THE EXISTING FILE
        # ----------------------------------------------------

        return FileResponse(

            path=EXCEL_FILE,

            media_type=(
                "application/vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet"
            ),

            filename=
                "NetSage_Model_Performance_Report.xlsx"
        )


    except HTTPException:

        raise


    except Exception as e:

        traceback.print_exc()

        raise HTTPException(

            status_code=500,

            detail=
                f"Export Error: {str(e)}"
        )