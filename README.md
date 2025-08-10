# Fill My Paperwork

This deploys the `fastapi_server.py` and the  `index.html` frontend as a single Cloud Run service.

## Requirements
- Vertex AI, Gemini, Cloud Run, Cloud Build, Artifact Registry enabled

## Deploy

```bash
cd $WORKDIR
SERVICE=fill-my-papers
PROJECT=$(gcloud config get-value project) 
REGION=europe-west9
IMAGE=eu.gcr.io/$PROJECT/$SERVICE:latest
gcloud builds submit --project $PROJECT --tag $IMAGE . 
&& gcloud run deploy $SERVICE --project $PROJECT --region $REGION --image $IMAGE --platform managed --allow-unauthenticated --min-instances=0 --max-instances=2 --cpu=1 --memory=512Mi --port=8080 --timeout=360s 
```

## Run tests
```bash
cd $WORKDIR
pytest -n auto -q # backend
npx playwright test --config playground/playwright.config.ts # frontend
```

## Local run
~~python3 -m http.server 8000~~ # frontend is served already by the backend
```bash
cd $WORKDIR
uvicorn fastapi_server:app --host 0.0.0.0 --port 8080 --reload # open http://localhost:8080/
```