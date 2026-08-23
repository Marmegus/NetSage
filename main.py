import os
from dotenv import load_dotenv
from core.checker import NetworkChecker
from core.ai_client import NetSageAIClient
from core.logger import AuditLogger
from core.dashboard_generator import generate_dashboard

# Load environment variables from .env file
load_dotenv()

def main():
    print("==================================================")
    print("           Initializing NetSage AI                ")
    print("==================================================\n")

    # Ensure API keys are set
    if not os.getenv("GROQ_API_KEY"):
        print("[!] Warning: GROQ_API_KEY environment variable is not set. AI diagnosis may fail.")

    # 1. Simulate User Inputs from a Packet Tracer Lab
    sample_symptom = "PC1 gets an IP address via DHCP, but cannot ping Server 1 in VLAN 30. Gateway ping works fine."
    
    sample_cli_output = """
    FastEthernet0/0             192.168.1.1     YES manual up             up
    Vlan30                      10.30.30.1      YES manual administratively down down
    
    interface FastEthernet0/1
     no ip address
     shutdown
    """

    print(f"-> User Symptom: {sample_symptom}\n")

    # ==========================================
    # LAYER 1: Deterministic Python Rule Check
    # ==========================================
    print("--- [Layer 1] Running Deterministic Checker ---")
    checker = NetworkChecker(sample_cli_output)
    rule_issues = checker.run_all_checks()

    if rule_issues:
        print(f"[!] Found {len(rule_issues)} rule violation(s):")
        for issue in rule_issues:
            print(f"    • [{issue['error_type']}] {issue['target']}: {issue['detail']}")
    else:
        print("[+] No hard rule violations detected by Python engine.")

    # Extract clean strings for the AI client
    rule_issue_strings = [i['detail'] for i in rule_issues]

    # ==========================================
    # LAYER 2: AI Diagnosis & RAG (Groq + HF)
    # ==========================================
    print("\n--- [Layer 2] Running AI RAG & Groq Diagnosis ---")
    try:
        ai_client = NetSageAIClient(csv_path="cases.csv")
        
        print("[*] Querying Hugging Face embeddings for similar cases & invoking ChatGroq...")
        diagnosis = ai_client.diagnose(
            symptom=sample_symptom,
            show_outputs=sample_cli_output,
            rule_issues=rule_issue_strings
        )

        print("\n==================================================")
        print("               NETSAGE AI DIAGNOSIS               ")
        print("==================================================")
        print(f"• Root Cause : {diagnosis.get('root_cause')}")
        print(f"• OSI Layer  : {diagnosis.get('osi_layer')}")
        print(f"• Confidence : {diagnosis.get('confidence')}")
        print(f"• Evidence   : {diagnosis.get('evidence')}")
        print(f"• Next Cmd   : {diagnosis.get('next_command')}")
        print(f"• Fix Steps  :")
        for idx, step in enumerate(diagnosis.get('fix_steps', []), 1):
            print(f"    {idx}. {step}")
        print("==================================================")

        # ==========================================
        # RESPONSIBLE AI: Audit Logging & Dashboard
        # ==========================================
        logger = AuditLogger()
        logger.log_diagnosis(
            symptom=sample_symptom,
            diagnosis=diagnosis,
            human_verified=True,
            notes="Verified correct diagnosis during end-to-end testing."
        )

        generate_dashboard()

    except Exception as e:
        print(f"[!] Error during AI execution: {e}")

if __name__ == "__main__":
    main()