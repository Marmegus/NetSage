import re

class NetworkChecker:
    def __init__(self, config_text: str):
        self.config_text = config_text
        self.issues = []

    def check_interfaces_down(self):
        """Scans 'show ip interface brief' outputs for down ports or VLANs."""
        pattern = r"([A-Za-z0-9\/\.-]+)\s+([\d\.]+|unassigned)\s+\w+\s+\w+\s+(administratively down|down)\s+(down)"
        matches = re.findall(pattern, self.config_text)
        
        for match in matches:
            iface, ip_addr, admin_status, line_status = match
            self.issues.append({
                "error_type": "Interface Down",
                "target": iface,
                "detail": f"Interface {iface} (IP: {ip_addr}) is down. Admin: {admin_status}, Line: {line_status}."
            })

    def check_shutdown_ports(self):
        """Scans running-config interface blocks for explicit 'shutdown' states."""
        interfaces = re.split(r'\n(?=interface)', self.config_text)
        for section in interfaces:
            if "shutdown" in section and "no shutdown" not in section:
                match = re.search(r'interface\s+([A-Za-z0-9\/\.-]+)', section)
                if match:
                    iface_name = match.group(1)
                    msg = f"Interface {iface_name} is explicitly configured in `shutdown` state."
                    if not any(msg in i['detail'] for i in self.issues):
                        self.issues.append({
                            "error_type": "Shutdown State",
                            "target": iface_name,
                            "detail": msg
                        })

    def check_missing_gateway(self):
        """Checks if a device configuration lacks a default gateway or default route."""
        has_gateway = "ip default-gateway" in self.config_text
        has_default_route = "ip route 0.0.0.0 0.0.0.0" in self.config_text
        
        if not has_gateway and not has_default_route:
            self.issues.append({
                "error_type": "Missing Gateway",
                "target": "Global Config",
                "detail": "Missing default gateway (`ip default-gateway`) or default static route (`ip route 0.0.0.0 0.0.0.0`)."
            })

    def check_unassigned_ips(self):
        """Catches active interfaces left with 'no ip address' where routing is expected."""
        interfaces = re.split(r'\n(?=interface)', self.config_text)
        for section in interfaces:
            match = re.search(r'interface\s+(Vlan\d+|FastEthernet[0-9\/\.-]+|GigabitEthernet[0-9\/\.-]+)', section)
            if match:
                iface_name = match.group(1)
                if "no ip address" in section and "shutdown" not in section and "switchport" not in section:
                    self.issues.append({
                        "error_type": "Unassigned IP",
                        "target": iface_name,
                        "detail": f"Active layer interface {iface_name} has 'no ip address' configured."
                    })

    def check_switchport_mode(self):
        """Validates switchports missing proper trunk or access mode declarations."""
        interfaces = re.split(r'\n(?=interface)', self.config_text)
        for section in interfaces:
            if "switchport" in section:
                match = re.search(r'interface\s+([A-Za-z0-9\/\.-]+)', section)
                if match:
                    iface_name = match.group(1)
                    if "switchport mode" not in section:
                        self.issues.append({
                            "error_type": "Misconfigured Switchport",
                            "target": iface_name,
                            "detail": f"Switch port {iface_name} references switchport commands but lacks an explicit `switchport mode` (access/trunk)."
                        })

    def run_all_checks(self):
        """Executes all deterministic validation checks and returns findings."""
        self.check_interfaces_down()
        self.check_shutdown_ports()
        self.check_missing_gateway()
        self.check_unassigned_ips()
        self.check_switchport_mode()
        return self.issues

# --- Test Execution ---
if __name__ == "__main__":
    sample_config = """
    !
    interface FastEthernet0/1
     switchport access vlan 10
     no shutdown
    !
    interface Vlan30
     no ip address
    !
    FastEthernet0/2             unassigned      YES unset  down          down
    """

    print("Running Advanced Deterministic Checker Engine...")
    checker = NetworkChecker(sample_config)
    detected_issues = checker.run_all_checks()

    if detected_issues:
        print(f"\n[!] Flagged {len(detected_issues)} Configuration Issue(s):")
        for idx, issue in enumerate(detected_issues, 1):
            print(f" {idx}. [{issue['error_type']}] Target: {issue['target']}")
            print(f"    -> {issue['detail']}")
    else:
        print("\n[+] No deterministic errors found.")