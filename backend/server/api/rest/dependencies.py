from __future__ import annotations

# Compatibility re-export: dependency providers were moved out of `server.*`
# so admin/miniprogram route packages can be decoupled from server package.
from api_common.dependencies import *  # noqa: F401,F403

