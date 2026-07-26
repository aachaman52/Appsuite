import os
import ast
import re
from pathlib import Path

def run_audits():
    appsuite_dir = Path("appsuite")
    code_audit_issues = []
    security_issues = []
    
    # Check for shell=True, SQL injection risks, bare excepts, hardcoded secrets
    for root, dirs, files in os.walk(appsuite_dir):
        for file in files:
            if not file.endswith(".py"): continue
            filepath = Path(root) / file
            
            try:
                content = filepath.read_text(encoding="utf-8")
                
                # Bare except
                if re.search(r'except\s*:', content):
                    code_audit_issues.append(f"Bare except found in {filepath.name}")
                    
                # Hardcoded paths
                if re.search(r'C:\\Users\\', content, re.IGNORECASE):
                    code_audit_issues.append(f"Hardcoded absolute path found in {filepath.name}")
                    
                # Shell Injection
                if 'shell=True' in content:
                    security_issues.append(f"Shell injection risk (shell=True) in {filepath.name}")
                    
                # SQL Injection (string formatting in SQL)
                if re.search(r'execute\([^,]*%\s*[a-zA-Z_]', content) or re.search(r'execute\(f"', content):
                    security_issues.append(f"Potential SQL injection (string formatting in execute) in {filepath.name}")
                    
                # Zip Slip
                if 'extractall' in content:
                    security_issues.append(f"Potential Zip Slip vulnerability (extractall) in {filepath.name}")
                    
            except Exception as e:
                pass
                
    # Write Code Audit
    code_audit = [
        "# Code Audit Report",
        "## Issues Found",
    ]
    if not code_audit_issues:
        code_audit.append("✅ No critical code quality issues found (bare excepts, hardcoded Windows paths).")
    else:
        for issue in code_audit_issues:
            code_audit.append(f"- {issue}")
    
    Path("code_audit.md").write_text("\n".join(code_audit), encoding="utf-8")
    
    # Write Security Audit
    sec_audit = [
        "# Security Audit Report",
        "## Vulnerabilities Found",
    ]
    if not security_issues:
        sec_audit.append("✅ No obvious SQL injections, shell injections, or Zip Slip vulnerabilities found.")
    else:
        for issue in security_issues:
            sec_audit.append(f"- ⚠️ {issue}")
            
    Path("security_audit.md").write_text("\n".join(sec_audit), encoding="utf-8")
    print("Audits complete.")

if __name__ == "__main__":
    run_audits()
