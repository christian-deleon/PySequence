import uvicorn

from pysequence_api.config import get_server_config

if __name__ == "__main__":
    config = get_server_config()

    uvicorn.run(
        "pysequence_api.app:create_app",
        host=config.host,
        port=config.port,
        factory=True,
    )
