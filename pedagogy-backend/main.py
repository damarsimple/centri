"""Centri Pedagogy Backend — FastAPI entrypoint.

Run:  uvicorn main:app --host 0.0.0.0 --port 8090
"""
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import db
# Importing the routers pulls in student_model + inquiry_store, which register their
# schemas with `db`. Do this before init_all() so every table is created.
from app.inquiry.router import router as inquiry_router
from app.questions import router as questions_router
from app.students import router as students_router

db.init_all()

app = FastAPI(title="Centri Pedagogy Backend", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok", "service": "pedagogy-backend"}


app.include_router(inquiry_router)
app.include_router(questions_router)
app.include_router(students_router)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8090)
