import os
import glob
import json

repo_root = r"c:\Users\Aachman_the_great\.gemini\antigravity\scratch\Appsuite\PyFlare"

def audit_repo():
    print("--- 1. Repository Audit ---")
    total_files = 0
    total_dirs = 0
    empty_dirs = []
    py_files = []
    md_files = []
    other_files = []
    placeholder_candidates = []
    
    for root, dirs, files in os.walk(repo_root):
        # Ignore some dirs
        if ".git" in root or "__pycache__" in root:
            continue
            
        total_dirs += 1
        if not dirs and not files:
            empty_dirs.append(root)
            
        for f in files:
            total_files += 1
            fpath = os.path.join(root, f)
            if f.endswith('.py'):
                py_files.append(fpath)
                with open(fpath, 'r', encoding='utf-8', errors='ignore') as fp:
                    content = fp.read()
                    if 'TODO' in content or 'pass' in content or 'NotImplementedError' in content:
                        placeholder_candidates.append(fpath)
            elif f.endswith('.md'):
                md_files.append(fpath)
            else:
                other_files.append(fpath)
                
    print(f"Total Directories: {total_dirs}")
    print(f"Total Files: {total_files}")
    print(f"Empty Directories: {len(empty_dirs)}")
    for ed in empty_dirs[:5]:
        print(f"  - {ed}")
        
    print(f"Python Files: {len(py_files)}")
    print(f"Markdown Files: {len(md_files)}")
    print(f"Placeholder Code Candidates: {len(placeholder_candidates)}")
    for pc in placeholder_candidates[:5]:
        print(f"  - {pc}")

    # Return stats for next steps
    return py_files, md_files

if __name__ == "__main__":
    audit_repo()
