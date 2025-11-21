from fastapi import APIRouter
from fastapi.responses import JSONResponse
import pandas as pd
import numpy as np
import logging  # ✅ Added logging

router = APIRouter()

# ✅ Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# Reference to global DataFrame
from smart_analyst import uploaded_df

@router.get("/profile")
async def profile_data():
    global uploaded_df
    if uploaded_df is None:
        logging.warning("No data uploaded yet for /profile.")
        return JSONResponse(status_code=400, content={"error": "No data uploaded yet."})

    try:
        # ✅ Basic profiling
        profile = {
            "shape": [int(dim) for dim in uploaded_df.shape],
            "columns": list(uploaded_df.columns),
            "dtypes": {col: str(dtype) for col, dtype in uploaded_df.dtypes.items()},
            "missing_values": uploaded_df.isnull().sum().replace({np.nan: None}).to_dict(),
            "numeric_summary": uploaded_df.describe(include=[np.number]).replace({np.nan: None}).to_dict(),
            "unique_counts": {
                col: int(uploaded_df[col].nunique()) for col in uploaded_df.select_dtypes(include=["object"]).columns
            }
        }

        logging.info(f"Generated profile for dataset with shape {uploaded_df.shape}.")
        return profile

    except Exception as e:
        logging.error(f"Error generating profile: {str(e)}")
        return JSONResponse(status_code=500, content={"error": f"Profile generation error: {str(e)}"})
