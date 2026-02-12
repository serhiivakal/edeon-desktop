import sys
from pathlib import Path

# Add python path
sys.path.append(str(Path(__file__).parent.parent / "python"))

from edeon_knowledge.qa.ollama_manager import OllamaManager

app_data = "/home/svakal/.local/share/com.edeon.desktop"
manager = OllamaManager(app_data)

print("Checking initial status...")
print(manager.get_status())

print("\nRunning sequence synchronously...")
try:
    # Run sequence synchronously
    manager._run_sequence("qwen2.5:3b")
    print("\nSequence completed!")
    print("Final status:")
    print(manager.get_status())
except Exception as e:
    print(f"\nSequence failed: {e}")
    import traceback
    traceback.print_exc()
