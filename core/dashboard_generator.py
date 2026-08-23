import os
import pandas as pd

def generate_dashboard(cases_path: str = "cases.csv", output_path: str = "dashboard/dashboard_summary.xlsx"):
    os.path.dirname(output_path)
    if not os.path.exists(cases_path):
        print(f"[Warning] {cases_path} not found. Dashboard generation skipped.")
        return

    df = pd.read_csv(cases_path)

    # Compute summary statistics
    total_cases = len(df)
    osi_breakdown = df['osi_layer'].value_counts().reset_index()
    osi_breakdown.columns = ['OSI Layer', 'Case Count']

    severity_breakdown = df['severity'].value_counts().reset_index()
    severity_breakdown.columns = ['Severity Level', 'Count']

    concept_breakdown = df['concept'].value_counts().reset_index()
    concept_breakdown.columns = ['Concept Tag', 'Count']

    # Write out to an Excel workbook with multiple sheets
    with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='All Cases', index=False)
        osi_breakdown.to_excel(writer, sheet_name='OSI Summary', index=False)
        severity_breakdown.to_excel(writer, sheet_name='Severity Breakdown', index=False)
        concept_breakdown.to_excel(writer, sheet_name='Concepts Breakdown', index=False)

    print(f"[+] Summary dashboard successfully generated at {output_path}")

if __name__ == "__main__":
    generate_dashboard()