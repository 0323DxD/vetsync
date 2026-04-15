import time
import os
import sys

# Mock the directory
CWD = r"c:\Users\Denmhar\OneDrive\Desktop\vet V2"
sys.path.append(CWD)

try:
    from chatbot_ml import AstridHybridML
    print("Starting ML Diagnostic...")
    start_time = time.time()
    
    # Initialize
    ml = AstridHybridML(os.path.join(CWD, "dataset"))
    
    end_time = time.time()
    print(f"SUCCESS: Initialization took {end_time - start_time:.2f} seconds.")
    print(f"Knowledge base size: {len(ml.knowledge_base)}")
    
except Exception as e:
    print(f"FAILED: {e}")
    import traceback
    traceback.print_exc()
