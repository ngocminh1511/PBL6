"""Run the unified backend from the repository root."""
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.backend.app.main:app", host="127.0.0.1", port=8000, reload=True)
