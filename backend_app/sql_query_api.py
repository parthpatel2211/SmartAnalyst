from fastapi import APIRouter, UploadFile, Form
from fastapi.responses import JSONResponse
import pandas as pd
import sqlite3
from openai import OpenAI
import logging

router = APIRouter()

# Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# OpenAI client
client = OpenAI(api_key="Enter API key here")  

@router.post("/nl2sql")
async def nl2sql(file: UploadFile, question: str = Form(...)):
    try:
        df = pd.read_csv(file.file)
        conn = sqlite3.connect(":memory:")
        df.to_sql("data", conn, index=False, if_exists="replace")
        logging.info(f"Data loaded with shape {df.shape}")

        prompt = f"Convert this question to an SQL query for a table named 'data': {question}"
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You’re an SQL expert. Only produce SELECT queries."},
                {"role": "user", "content": prompt}
            ]
        )
        sql_query = response.choices[0].message.content.strip().lower()
        logging.info(f"Generated SQL: {sql_query}")

        if not sql_query.startswith("select"):
            conn.close()
            return JSONResponse(status_code=400, content={"error": "Only SELECT queries allowed."})

        try:
            conn.execute(f"EXPLAIN {sql_query}")
        except Exception as e:
            conn.close()
            return JSONResponse(status_code=400, content={"error": f"SQL syntax invalid: {e}"})

        result_df = pd.read_sql_query(sql_query, conn)
        conn.close()
        return {
            "sql_query": sql_query,
            "result": result_df.to_dict(orient="records")
        }

    except Exception as e:
        logging.error(f"SQL error: {str(e)}")
        return JSONResponse(status_code=500, content={"error": str(e)})
