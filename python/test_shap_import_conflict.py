import sys
sys.path.insert(0, '/home/svakal/Projects/Edeon/python')

def test_import(module_name):
    print(f"Importing {module_name}...")
    try:
        __import__(module_name)
        print("Success")
    except Exception as e:
        print(f"Failed: {e}")

# Import other engine components
test_import("edeon_engine.standardize")
test_import("edeon_engine.properties")
test_import("edeon_engine.tice_rules")
test_import("edeon_engine.selectivity")
test_import("edeon_engine.resistance")
test_import("edeon_engine.toxicity")
test_import("edeon_engine.scoring")
test_import("edeon_engine.depict")
test_import("edeon_engine.mcs")
test_import("edeon_engine.knowledge")

print("\nNow attempting to import shap...")
import shap
print("SUCCESS: imported shap without segfault!")
