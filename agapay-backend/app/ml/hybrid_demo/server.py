"""Optional local FastAPI demo service. Operational API and databases untouched."""
import argparse
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from .engine import DemoEngine
from .hydrology import Basin
from .rainfall import DEFAULT_DATASET


def create_app(directory: Path, bundle: Path, dataset: Path = DEFAULT_DATASET) -> FastAPI:
    engine = DemoEngine(directory, dataset)
    app = FastAPI(title="AGAPAY experimental controlled-basin demo", version="0.1")

    @app.get("/")
    def index():
        return FileResponse(bundle)

    @app.get("/api/evaluation")
    def evaluation():
        import json
        return json.loads((directory / "evaluation.json").read_text())

    @app.post("/api/project")
    def projection(payload: dict):
        try:
            if payload.get("sensor") is not None:
                raise ValueError("Use the authenticated dashboard monitoring path for ESP32 initialization; this standalone API accepts manual initial depth only")
            return engine.run(mode=payload["mode"], initial_cm=float(payload["initial_cm"]),
                              basin=Basin(**payload.get("basin", {})), as_of=payload["as_of"],
                              current_history=payload.get("current_history"))
        except (ValueError, TypeError, KeyError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    return app


def main():
    import uvicorn
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("model_directory", type=Path)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--port", type=int, default=8011)
    args = parser.parse_args()
    uvicorn.run(create_app(args.model_directory, args.bundle, args.dataset), host="127.0.0.1", port=args.port)


if __name__ == "__main__":
    main()
