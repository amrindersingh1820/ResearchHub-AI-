import os
import pandas as pd
from app.utils.logging_config import logger

def analyze_csv(file_path: str) -> str:
    """Read a CSV file and output descriptive summary statistics."""
    try:
        df = pd.read_csv(file_path)
        summary = []
        summary.append(f"CSV Filename: {os.path.basename(file_path)}")
        summary.append(f"Total Rows: {len(df)}, Total Columns: {len(df.columns)}")
        summary.append(f"Columns: {', '.join(df.columns)}")
        summary.append("\n--- Data Sample (First 3 Rows) ---")
        summary.append(df.head(3).to_string(index=False))
        summary.append("\n--- Column Types & Missing Values ---")
        null_info = df.isnull().sum()
        for col in df.columns:
            summary.append(f"  {col} ({df[col].dtype}): {len(df) - null_info[col]} non-null items, {null_info[col]} missing")
        
        # Numeric stats if any numeric columns exist
        numeric_cols = df.select_dtypes(include=['number']).columns
        if len(numeric_cols) > 0:
            summary.append("\n--- Numeric Stats Summary ---")
            summary.append(df[numeric_cols].describe().to_string())
            
        return "\n".join(summary)
    except Exception as e:
        logger.error(f"Error analyzing CSV {file_path}: {e}")
        return f"Error analyzing CSV: {e}"
