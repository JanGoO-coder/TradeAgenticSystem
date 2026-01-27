import sys
import os
from pathlib import Path

# Add project root to sys.path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from agent.src.llm import get_llm_service

def test_llm():
    print("Initializing LLM Service...")
    llm = get_llm_service()
    
    if llm.llm is None:
        print("WARNING: LLM not initialized (missing API key?). using mock.")
    else:
        print(f"LLM Initialized: {llm.model_name}")

    print("\nTesting ask_llm...")
    system_prompt = "You are a trading assistant. Answer briefly."
    user_prompt = "What is the capital of France?"
    
    response = llm.ask_llm(system_prompt, user_prompt)
    print(f"Response: {response}")

if __name__ == "__main__":
    test_llm()
