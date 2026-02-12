import pandas as pd

print("--- SUBSTANCE CHARACTERISATION ---")
df_sub = pd.read_excel("SubstanceCharacterisation_KJ_2023.xlsx")
print(df_sub.columns.tolist())
print(df_sub.head(3).to_string())

print("\n--- REFERENCE POINTS ---")
df_ref = pd.read_excel("ReferencePoints_KJ_2023.xlsx")
print(df_ref.columns.tolist())
print(df_ref.head(3).to_string())
