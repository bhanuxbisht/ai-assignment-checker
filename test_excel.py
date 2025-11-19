import pandas as pd
import os

try:
    df = pd.DataFrame({'A': [1, 2, 3], 'B': [4, 5, 6]})
    os.makedirs('results', exist_ok=True)
    df.to_excel('results/test.xlsx', index=False, engine='openpyxl')
    print("Excel generation successful")
except Exception as e:
    print(f"Excel generation failed: {e}")
