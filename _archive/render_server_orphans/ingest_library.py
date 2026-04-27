import os
import sys

# Ensure we can find the tools module
sys.path.append(os.path.dirname(__file__))
from tools.vector_store import FamilyKnowledgeBase

# --- CONFIGURATION ---
# Change this to your actual library path!
# Example: r"C:\ProgramData\Autodesk\RVT 2024\Libraries\English"
LIBRARY_PATH = r"X:\ARCH\JR Libraries\Revit RFA"

def scan_folder(root_path):
    print(f"Scanning {root_path}...")
    family_list = []
    
    for root, dirs, files in os.walk(root_path):
        for file in files:
            if file.lower().endswith(".rfa"):
                full_path = os.path.join(root, file)
                name = os.path.splitext(file)[0]
                
                # Heuristic to guess category from folder name
                # e.g. "...\Doors\..." -> "Doors"
                category = os.path.basename(root)
                
                family_list.append({
                    "name": name,
                    "path": full_path,
                    "category": category
                })
    
    return family_list

if __name__ == "__main__":
    if not os.path.exists(LIBRARY_PATH):
        print(f"❌ Path not found: {LIBRARY_PATH}")
        print("Please edit 'LIBRARY_PATH' in this script to point to your .rfa folder.")
        sys.exit(1)

    # 1. Scan
    families = scan_folder(LIBRARY_PATH)
    print(f"Found {len(families)} families.")
    
    if len(families) == 0:
        sys.exit()

    # 2. Ingest
    kb = FamilyKnowledgeBase()
    kb.add_families(families)
    
    # 3. Test
    print("\n--- TEST SEARCH ---")
    results = kb.search("I need a seat for a desk")
    for r in results:
        print(f"[{r['score']:.2f}] {r['name']} ({r['category']})")
