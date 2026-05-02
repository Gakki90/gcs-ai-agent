from __future__ import annotations

import uvicorn
import sys

from autoglm_phone_controller.runtime import configure_packaged_environment


if __name__ == "__main__":
    configure_packaged_environment()
    if "--check-imports" in sys.argv:
        from autoglm_phone_controller.runner import _load_phone_agent_classes
        from autoglm_phone_controller.web.app import app

        _load_phone_agent_classes()
        print(f"imports ok: {app.title}")
        raise SystemExit(0)

    uvicorn.run(
        "autoglm_phone_controller.web.app:app",
        host="127.0.0.1",
        port=18081,
        reload=False,
        log_level="info",
    )
