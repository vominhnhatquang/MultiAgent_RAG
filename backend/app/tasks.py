from app.celery_app import celery_app

@celery_app.task(bind=True, name="app.tasks.health_check")
def health_check(self):
    return {"status": "ok"}
