# NetSage

# NetSage AI 🌐🤖

> An intelligent, hybrid network troubleshooting assistant designed for Cisco Packet Tracer environments. It combines deterministic rule-based checks with LLM-powered RAG analysis (via Groq) to diagnose network issues, log audit trails, and export comprehensive Excel performance reports.

---

## 🚀 Key Features

* **Hybrid Diagnostic Engine:** Fast deterministic checks for common physical/layer issues combined with advanced LLM reasoning (`openai/gpt-oss-20b` via Groq) for deep root-cause analysis.
* **Human-in-the-Loop Review:** Interactive web interface allowing engineers to review, accept, edit, or reject AI-generated diagnoses before logging.
* **Robust Audit Logging:** Safely serializes and logs review feedback into a structured CSV file using Pandas with bulletproof tokenization and quoting (`csv.QUOTE_MINIMAL`) to handle complex text fields, commas, and line breaks.
* **Automated Analytics & Excel Reports:** Instantly aggregates audit data into multi-sheet Excel workbooks (`openpyxl`) featuring performance summaries, OSI layer breakdowns, and full audit logs.
* **Modern Web UI:** Clean, responsive HTML/CSS/JS interface built to seamlessly interact with the FastAPI backend.

---

## 🛠️ Tech Stack

* **Backend:** FastAPI, Python, Uvicorn
* **AI / LLM:** Groq API (`openai/gpt-oss-20b`)
* **Data Processing:** Pandas, OpenPyXL
* **Frontend:** HTML5, CSS3, JavaScript
* **Deployment Ready:** Configured for cloud platforms like Render

---

## 📁 Project Structure

```text
NetSage-AI/
│
├── app.py                  # Main FastAPI application and routing logic
├── index.html              # Frontend user interface
├── requirements.txt        # Python package dependencies
├── .gitignore              # Excludes virtual environments, logs, and sensitive data
└── logs/                   # Directory for audit logs (git-ignored)
    └── ai_review_log.csv   # Runtime audit and feedback trail
