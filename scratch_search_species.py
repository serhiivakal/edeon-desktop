import pandas as pd
import re

def clean_escapes(text):
    if not isinstance(text, str):
        return text
    return re.sub(r'_x([0-9a-fA-F]{4})_', lambda m: chr(int(m.group(1), 16)), text)

df_ref = pd.read_excel("ReferencePoints_KJ_2023.xlsx")
df_ref["Species_clean"] = df_ref["Species"].apply(clean_escapes)

print("Unique species containing bird, quail, duck, pheasant, sparrow, or colinus (case-insensitive):")
birds = df_ref[df_ref["Species_clean"].astype(str).str.contains("bird|quail|duck|pheasant|sparrow|colinus|anas|coturnix|phasianus|passer|mallard|bobwhite", case=False, na=False)]
print(birds["Species_clean"].value_counts())

print("\nUnique endpoints for birds:")
print(birds["Endpoint"].apply(clean_escapes).value_counts())

print("\nSample bird records:")
birds["Substance_clean"] = birds["Substance"].apply(clean_escapes)
birds["Endpoint_clean"] = birds["Endpoint"].apply(clean_escapes)
print(birds[["Substance_clean", "Species_clean", "Endpoint_clean", "value", "unit"]].head(15).to_string())
