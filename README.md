# Fill My Paperwork - Cloud Run

This deploys the FastAPI server and the frontend (`index.html`) as a single Cloud Run service, public, request-based, minimal cost.

## Prereqs
- `gcloud` installed and authenticated
- Project: set `$PROJECT` accordingly
- Vertex AI, Gemini, Cloud Run, Cloud Build, Artifact Registry enabled

## Build and deploy

```bash
SERVICE=fill-my-papers
IMAGE=eu.gcr.io/$PROJECT/$SERVICE:latest

Build: `gcloud builds submit --project $PROJECT --tag $IMAGE .`

Deploy (public, minimal): `gcloud run deploy $SERVICE --project $PROJECT --region $REGION --image $IMAGE --platform managed --allow-unauthenticated --min-instances=0 --max-instances=2 --cpu=1 --memory=512Mi --port=8080 --timeout=360s`

Set service env (optional): `gcloud run services update $SERVICE --project $PROJECT --region $REGION --set-env-vars=GCP_PROJECT=$PROJECT,GCP_LOCATION=$REGION`
```

After deploy, Cloud Run will print the service URL. Open it in your browser.

## Redeploy after changes
1. Edit code in `playground/`
2. Rebuild and deploy: `gcloud builds submit --project $PROJECT --tag $IMAGE . && gcloud run deploy $SERVICE --project $PROJECT --region $REGION --image $IMAGE --platform managed --allow-unauthenticated`

## Local run
```bash
pip install -r playground/requirements.txt
uvicorn playground.fastapi_server:app --host 0.0.0.0 --port 8080
# open http://localhost:8080/
```

## Notes
- The server serves `/` -> `playground/index.html` and `/dev-preload.jpg` for the preload asset.
- API: `POST /api/form/detect` with multipart `file`.
- Set `GCP_PROJECT` and `GCP_LOCATION` env vars if different from defaults.
- To reduce costs, Cloud Run is set to `--min-instances=0` and a low `--max-instances`.
