import os
import csv
from datetime import datetime

class AuditLogger:
    def __init__(self, log_path: str = "logs/ai_review_log.csv"):
        self.log_path = log_path
        self._ensure_log_exists()

    def _ensure_log_exists(self):
        """Ensures the log file and directory exist with proper headers."""
        os.makedirs(os.path.dirname(self.log_path), exist_ok=True)
        if not os.path.exists(self.log_path):
            with open(self.log_path, mode="w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow([
                    "timestamp", 
                    "symptom", 
                    "osi_layer", 
                    "root_cause", 
                    "confidence", 
                    "human_verified", 
                    "review_notes"
                ])

    def log_diagnosis(self, symptom: str, diagnosis: dict, human_verified: bool = False, notes: str = "Pending review"):
        """Appends a new diagnostic record to the audit log."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(self.log_path, mode="a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                timestamp,
                symptom,
                diagnosis.get("osi_layer", "Unknown"),
                diagnosis.get("root_cause", "Unknown"),
                diagnosis.get("confidence", "Unknown"),
                human_verified,
                notes
            ])
        print(f"[+] Audit log updated successfully at {self.log_path}")