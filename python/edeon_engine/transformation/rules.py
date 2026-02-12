import os
import sygma

# Path to rules.txt relative to this file
RULES_TXT_PATH = os.path.join(os.path.dirname(__file__), "rules.txt")

def get_custom_rules():
    """Load and return the curated custom transformation rules."""
    if os.path.exists(RULES_TXT_PATH):
        return sygma.read_reaction_rules(RULES_TXT_PATH)
    return []

def get_metabolic_rules(phase=1):
    """Load and return SyGMa's default metabolic rules."""
    if phase == 1:
        return sygma.read_reaction_rules(sygma.ruleset['phase1'])
    elif phase == 2:
        return sygma.read_reaction_rules(sygma.ruleset['phase2'])
    return []
