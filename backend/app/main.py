from pickle import GET

from fastapi import FastAPI
app=FastAPI()
@app.get("/hello")
def test():
    return {"message": "FastAPI工程正在启动"}