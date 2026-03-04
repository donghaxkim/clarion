# GCS upload/download helpers
def upload_file(local_path: str, gcs_key: str) -> str:
    # TODO: Google Cloud Storage
    return f"gs://bucket/{gcs_key}"

def download_file(gcs_uri: str, local_path: str) -> None:
    # TODO
    pass
