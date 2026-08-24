import os
import io
import json
import traceback
from datetime import datetime
from typing import List, Optional

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd
import mysql.connector

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel
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
# MYSQL CONFIGURATION
# ============================================================

MYSQL_HOST = os.environ.get("MYSQL_HOST")
MYSQL_PORT = int(os.environ.get("MYSQL_PORT", "3306"))
MYSQL_DATABASE = os.environ.get("MYSQL_DATABASE")
MYSQL_USER = os.environ.get("MYSQL_USER")
MYSQL_PASSWORD = os.environ.get("MYSQL_PASSWORD")


def get_db_connection():
    """
    Create a new MySQL connection.

    A new connection is created for each request instead of
    keeping one global connection alive. This is safer for
    cloud deployments where connections can expire.
    """

    try:

        connection = mysql.connector.connect(
            host=MYSQL_HOST,
            port=MYSQL_PORT,
            database=MYSQL_DATABASE,
            user=MYSQL_USER,
            password=MYSQL_PASSWORD,
            connection_timeout=10
        )

        return connection

    except mysql.connector.Error as e:

        print("MYSQL CONNECTION ERROR:")
        traceback.print_exc()

        raise HTTPException(
            status_code=500,
            detail=f"MySQL connection failed: {str(e)}"
        )


# ============================================================
# INITIALIZE DATABASE
# ============================================================

def initialize_database():

    connection = None
    cursor = None

    try:

        connection = mysql.connector.connect(
            host=MYSQL_HOST,
            port=MYSQL_PORT,
            database=MYSQL_DATABASE,
            user=MYSQL_USER,
            password=MYSQL_PASSWORD,
            connection_timeout=10
        )

        cursor = connection.cursor()

        create_table_query = """
        CREATE TABLE IF NOT EXISTS ai_reviews (

            id INT AUTO_INCREMENT PRIMARY KEY,

            timestamp DATETIME NOT NULL,

            symptom TEXT,

            root_cause TEXT,

            osi_layer VARCHAR(100),

            confidence VARCHAR(100),

            evidence TEXT,

            next_command TEXT,

            fix_steps TEXT,

            status VARCHAR(50),

            notes TEXT

        )
        """

        cursor.execute(create_table_query)

        connection.commit()

        print("MySQL database initialized successfully.")

    except Exception:

        print("DATABASE INITIALIZATION ERROR:")
        traceback.print_exc()

    finally:

        if cursor:
            cursor.close()

        if connection:
            connection.close()


# ============================================================
# INITIALIZE DATABASE ON STARTUP
# ============================================================

initialize_database()


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


    return {

        "rule_issues":
            rule_issues,

        "diagnosis":
            diagnosis_json
    }


# ============================================================
# LOG FEEDBACK INTO MYSQL
# ============================================================

@app.post("/api/log-feedback")
def log_feedback(req: FeedbackRequest):

    connection = None
    cursor = None

    try:

        connection = get_db_connection()

        cursor = connection.cursor()


        insert_query = """
        INSERT INTO ai_reviews (

            timestamp,
            symptom,
            root_cause,
            osi_layer,
            confidence,
            evidence,
            next_command,
            fix_steps,
            status,
            notes

        )

        VALUES (

            %s,
            %s,
            %s,
            %s,
            %s,
            %s,
            %s,
            %s,
            %s,
            %s

        )
        """


        values = (

            datetime.now(),

            req.symptom,

            req.diagnosis.root_cause,

            req.diagnosis.osi_layer,

            req.diagnosis.confidence,

            req.diagnosis.evidence,

            req.diagnosis.next_command,

            " | ".join(
                req.diagnosis.fix_steps
            ),

            req.status,

            req.notes or ""

        )


        cursor.execute(
            insert_query,
            values
        )


        connection.commit()


        return {

            "status":
                "success",

            "message":
                "Feedback successfully logged to MySQL."

        }


    except mysql.connector.Error as e:

        if connection:
            connection.rollback()

        traceback.print_exc()

        raise HTTPException(

            status_code=500,

            detail=
                f"MySQL logging error: {str(e)}"

        )


    except Exception as e:

        if connection:
            connection.rollback()

        traceback.print_exc()

        raise HTTPException(

            status_code=500,

            detail=
                f"Failed to log feedback: {str(e)}"

        )


    finally:

        if cursor:
            cursor.close()

        if connection:
            connection.close()


# ============================================================
# ANALYTICS PAGE
# ============================================================

@app.get(
    "/analytics",
    response_class=HTMLResponse
)
def analytics_page():

    return """
<!DOCTYPE html>

<html lang="en">

<head>

<meta charset="UTF-8">

<meta
    name="viewport"
    content="width=device-width, initial-scale=1.0"
>

<title>NetSage AI - Analytics</title>

<style>

:root {
    --bg: #0f172a;
    --card: #1e293b;
    --accent: #38bdf8;
    --text: #f8fafc;
    --muted: #94a3b8;
    --border: #334155;
}

* {
    box-sizing: border-box;
}

body {

    margin: 0;
    padding: 30px;

    background: var(--bg);

    color: var(--text);

    font-family:
        'Segoe UI',
        Tahoma,
        Geneva,
        Verdana,
        sans-serif;
}

.container {

    max-width: 1200px;
    margin: 0 auto;
}

header {

    text-align: center;
    margin-bottom: 35px;
}

header h1 {

    color: var(--accent);
    margin-bottom: 5px;
}

.subtitle {

    color: var(--muted);
}

.stats-grid {

    display: grid;

    grid-template-columns:
        repeat(4, 1fr);

    gap: 20px;

    margin-bottom: 30px;
}

.stat-card {

    background: var(--card);

    border:
        1px solid var(--border);

    border-radius: 12px;

    padding: 25px;

    text-align: center;
}

.stat-card h3 {

    color: var(--muted);

    margin-bottom: 10px;
}

.stat-value {

    font-size: 2rem;

    font-weight: bold;

    color: var(--accent);
}

.chart-card {

    background: var(--card);

    border:
        1px solid var(--border);

    border-radius: 12px;

    padding: 20px;

    margin-bottom: 25px;

    text-align: center;
}

.chart-card h2 {

    margin-top: 0;

    color: var(--accent);
}

.chart-card img {

    max-width: 100%;

    border-radius: 8px;
}

.actions {

    display: flex;

    gap: 15px;

    margin-top: 30px;
}

button {

    flex: 1;

    padding: 14px;

    border: none;

    border-radius: 8px;

    font-weight: bold;

    cursor: pointer;
}

.back {

    background: #334155;

    color: white;
}

.download {

    background: var(--accent);

    color: #0f172a;
}

@media(max-width: 800px) {

    .stats-grid {

        grid-template-columns:
            repeat(2, 1fr);
    }
}

@media(max-width: 500px) {

    .stats-grid {

        grid-template-columns: 1fr;
    }

    .actions {

        flex-direction: column;
    }
}

</style>

</head>

<body>

<div class="container">

<header>

<h1>
    NetSage AI Analytics
</h1>

<p class="subtitle">
    AI Diagnosis Performance & Human Oversight
</p>

</header>


<div class="stats-grid">

<div class="stat-card">

<h3>
    Total Diagnoses
</h3>

<div
    id="total"
    class="stat-value"
>
    ...
</div>

</div>


<div class="stat-card">

<h3>
    Acceptance Rate
</h3>

<div
    id="acceptance"
    class="stat-value"
>
    ...
</div>

</div>


<div class="stat-card">

<h3>
    Edit Rate
</h3>

<div
    id="edit"
    class="stat-value"
>
    ...
</div>

</div>


<div class="stat-card">

<h3>
    Rejection Rate
</h3>

<div
    id="rejection"
    class="stat-value"
>
    ...
</div>

</div>

</div>


<div class="chart-card">

<h2>
    Review Status Distribution
</h2>

<img
    src="/api/analytics/chart/status"
    alt="Review Status Distribution"
>

</div>


<div class="chart-card">

<h2>
    OSI Layer Distribution
</h2>

<img
    src="/api/analytics/chart/osi"
    alt="OSI Layer Distribution"
>

</div>


<div class="actions">

<button
    class="back"
    onclick="window.location.href='/'"
>
    ← Back to Dashboard
</button>


<button
    class="download"
    onclick="downloadExcel()"
>
    📥 Download Excel Report
</button>

</div>

</div>


<script>

async function loadStats() {

    try {

        const response =
            await fetch(
                '/api/analytics/stats'
            );

        const data =
            await response.json();

        if (!response.ok) {

            throw new Error(
                data.detail ||
                'Failed to load statistics'
            );
        }

        document.getElementById(
            'total'
        ).textContent =
            data.total_reviews;

        document.getElementById(
            'acceptance'
        ).textContent =
            data.acceptance_rate + '%';

        document.getElementById(
            'edit'
        ).textContent =
            data.edit_rate + '%';

        document.getElementById(
            'rejection'
        ).textContent =
            data.rejection_rate + '%';

    }

    catch (error) {

        console.error(
            'Analytics error:',
            error
        );

    }
}


function downloadExcel() {

    window.location.href =
        '/api/analytics/export';

}


loadStats();

</script>

</body>

</html>
"""


# ============================================================
# READ ALL REVIEWS FROM MYSQL
# ============================================================

def read_reviews_from_mysql():

    connection = None
    cursor = None

    try:

        connection = get_db_connection()

        cursor = connection.cursor(
            dictionary=True
        )


        query = """
        SELECT
            id,
            timestamp,
            symptom,
            root_cause,
            osi_layer,
            confidence,
            evidence,
            next_command,
            fix_steps,
            status,
            notes
        FROM ai_reviews
        ORDER BY timestamp ASC
        """


        cursor.execute(query)


        rows = cursor.fetchall()


        df = pd.DataFrame(rows)


        if df.empty:

            df = pd.DataFrame(
                columns=[
                    "id",
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
            )


        return df


    finally:

        if cursor:
            cursor.close()

        if connection:
            connection.close()


# ============================================================
# ANALYTICS STATISTICS
# ============================================================

@app.get(
    "/api/analytics/stats"
)
def analytics_stats():

    try:

        df = read_reviews_from_mysql()


        total = len(df)


        if total == 0:

            return {

                "total_reviews": 0,

                "accepted": 0,

                "edited": 0,

                "rejected": 0,

                "acceptance_rate": 0,

                "edit_rate": 0,

                "rejection_rate": 0
            }


        status_counts = (

            df["status"]

            .astype(str)

            .str.strip()

            .str.lower()

            .value_counts()

        )


        accepted = int(
            status_counts.get(
                "accepted",
                0
            )
        )


        edited = int(
            status_counts.get(
                "edited",
                0
            )
        )


        rejected = int(
            status_counts.get(
                "rejected",
                0
            )
        )


        return {

            "total_reviews":
                total,

            "accepted":
                accepted,

            "edited":
                edited,

            "rejected":
                rejected,

            "acceptance_rate":
                round(
                    accepted / total * 100,
                    2
                ),

            "edit_rate":
                round(
                    edited / total * 100,
                    2
                ),

            "rejection_rate":
                round(
                    rejected / total * 100,
                    2
                )
        }


    except Exception as e:

        traceback.print_exc()

        raise HTTPException(

            status_code=500,

            detail=
                f"Analytics Error: {str(e)}"
        )


# ============================================================
# MATPLOTLIB - STATUS CHART
# ============================================================

@app.get(
    "/api/analytics/chart/status"
)
def status_chart():

    try:

        df = read_reviews_from_mysql()


        statuses = [
            "Accepted",
            "Edited",
            "Rejected"
        ]


        if df.empty:

            counts = [
                0,
                0,
                0
            ]

        else:

            status_counts = (

                df["status"]

                .astype(str)

                .str.strip()

                .str.title()

                .value_counts()

            )


            counts = [

                int(
                    status_counts.get(
                        status,
                        0
                    )
                )

                for status in statuses

            ]


        fig, ax = plt.subplots(
            figsize=(9, 5)
        )


        ax.bar(
            statuses,
            counts
        )


        ax.set_title(
            "AI Diagnosis Review Status"
        )


        ax.set_xlabel(
            "Review Status"
        )


        ax.set_ylabel(
            "Number of Reviews"
        )


        ax.grid(
            axis="y",
            alpha=0.25
        )


        plt.tight_layout()


        buffer = io.BytesIO()


        fig.savefig(
            buffer,
            format="png",
            dpi=150,
            bbox_inches="tight"
        )


        plt.close(fig)


        buffer.seek(0)


        return StreamingResponse(

            buffer,

            media_type="image/png"
        )


    except Exception as e:

        traceback.print_exc()

        raise HTTPException(

            status_code=500,

            detail=
                f"Chart Error: {str(e)}"
        )


# ============================================================
# MATPLOTLIB - OSI LAYER CHART
# ============================================================

@app.get(
    "/api/analytics/chart/osi"
)
def osi_chart():

    try:

        df = read_reviews_from_mysql()


        if (
            df.empty
            or "osi_layer" not in df.columns
        ):

            layers = [
                "No Data"
            ]

            counts = [
                0
            ]

        else:

            layer_counts = (

                df["osi_layer"]

                .astype(str)

                .str.strip()

                .value_counts()

            )


            layers = (
                layer_counts
                .index
                .tolist()
            )


            counts = (
                layer_counts
                .values
                .tolist()
            )


        fig, ax = plt.subplots(
            figsize=(9, 5)
        )


        ax.bar(
            layers,
            counts
        )


        ax.set_title(
            "Diagnoses by OSI Layer"
        )


        ax.set_xlabel(
            "OSI Layer"
        )


        ax.set_ylabel(
            "Number of Diagnoses"
        )


        ax.grid(
            axis="y",
            alpha=0.25
        )


        plt.xticks(
            rotation=20
        )


        plt.tight_layout()


        buffer = io.BytesIO()


        fig.savefig(
            buffer,
            format="png",
            dpi=150,
            bbox_inches="tight"
        )


        plt.close(fig)


        buffer.seek(0)


        return StreamingResponse(

            buffer,

            media_type="image/png"
        )


    except Exception as e:

        traceback.print_exc()

        raise HTTPException(

            status_code=500,

            detail=
                f"Chart Error: {str(e)}"
        )


# ============================================================
# EXPORT MYSQL DATA TO EXCEL
# ============================================================

# ============================================================
# EXPORT MYSQL DATA TO EXCEL
# ============================================================

# ============================================================
# EXPORT MYSQL DATA TO EXCEL
# ============================================================

# ============================================================
# EXPORT LOGS TO EXCEL
# ============================================================

@app.get("/api/analytics/export")
def export_analytics_report():

    try:

        # Read logs from MySQL
        df = read_reviews_from_mysql()

        # ----------------------------------------------------
        # CREATE ONLY THE REQUIRED LOGS COLUMNS
        # ----------------------------------------------------

        logs_df = pd.DataFrame({

            "timestamp":
                df["timestamp"],

            "symptom":
                df["symptom"],

            "osi_layer":
                df["osi_layer"],

            "root_cause":
                df["root_cause"],

            "confidence":
                df["confidence"],

            "human_verified":
                df["status"].apply(
                    lambda status:
                        True
                        if str(status).strip().lower() == "accepted"
                        else (
                            "Edited"
                            if str(status).strip().lower() == "edited"
                            else False
                        )
                ),

            "review_notes":
                df["notes"]

        })

        # ----------------------------------------------------
        # CREATE EXCEL
        # ----------------------------------------------------

        output = io.BytesIO()

        with pd.ExcelWriter(
            output,
            engine="openpyxl"
        ) as writer:

            # ONLY ONE SHEET
            logs_df.to_excel(
                writer,
                sheet_name="Logs",
                index=False
            )

        output.seek(0)

        # ----------------------------------------------------
        # RETURN EXCEL
        # ----------------------------------------------------

        return StreamingResponse(

            output,

            media_type=(
                "application/vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet"
            ),

            headers={
                "Content-Disposition":
                    "attachment; "
                    "filename=NetSage_Logs.xlsx"
            }
        )

    except Exception as e:

        traceback.print_exc()

        raise HTTPException(
            status_code=500,
            detail=f"Export Error: {str(e)}"
        )