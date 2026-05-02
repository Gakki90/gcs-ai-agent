from __future__ import annotations

import uvicorn

from autoglm_phone_controller.runtime import configure_packaged_environment


if __name__ == "__main__":
    configure_packaged_environment()
    uvicorn.run(
        "autoglm_phone_controller.web.app:app",
        host="127.0.0.1",
        port=18081,
        reload=False,
        log_level="info",
    )
