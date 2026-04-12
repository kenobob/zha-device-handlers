"""Osram LIGHTIFY A19 RGBW device - Color Command Interceptor."""

import colorsys
from typing import Any

from zigpy.quirks import CustomCluster
from zigpy.quirks.v2 import QuirkBuilder
from zigpy.zcl.clusters.lighting import Color
from zhaquirks.osram import OSRAM, OsramLightCluster


class OsramColorInterceptor(CustomCluster, Color):
    """Intercept XY commands and translate them to HS."""
    cluster_id = Color.cluster_id

    # Gamut B Matrix constants for LED hardware
    RGB_MATRIX = (
        (1.656492, -0.354851, -0.255038),
        (-0.707196, 1.655397, 0.036152),
        (0.051713, -0.121364, 1.011530),
    )

    async def command(
        self, command_id: int, *args: Any, **kwargs: Any
    ) -> Any:  # Added type hints for Mypy
        """Intercept Move to Color (XY) and redirect to Move to Hue and Sat."""

        if command_id != Color.ServerCommandDefs.move_to_color.id:
            return await super().command(command_id, *args, **kwargs)

        # Simplified extraction
        if "color_x" in kwargs:
            x_raw = kwargs["color_x"]
            y_raw = kwargs.get("color_y")
            tr_time = kwargs.get("transition_time", 0)
        elif args and hasattr(args[0], "color_x"):
            x_raw = args[0].color_x
            y_raw = args[0].color_y
            tr_time = getattr(args[0], "transition_time", 0)
        elif len(args) >= 2:
            x_raw, y_raw = args[0], args[1]
            tr_time = args[2] if len(args) > 2 else 0
        else:
            return await super().command(command_id, *args, **kwargs)

        try:
            # Normalize and protect against division by zero
            x = x_raw / 65535.0
            y = max(y_raw / 65535.0, 0.000001)

            h, s = self.xy_to_hs(x, y)

            # Scale to Zigbee 0-254 range
            return await self.move_to_hue_and_saturation(
                hue=max(0, min(254, int(h * 254))),
                saturation=max(0, min(254, int(s * 254))),
                transition_time=tr_time,
            )
        except (TypeError, ZeroDivisionError):
            return await super().command(command_id, *args, **kwargs)

    def xy_to_hs(self, x: float, y: float) -> tuple[float, float]:
        """Translate XY coordinates to Hue and Saturation."""
        z = max(0.0, 1.0 - x - y)
        x_val, y_val, z_val = (1.0 / y) * x, 1.0, (1.0 / y) * z

        # Apply Gamut B Matrix
        r = x_val * self.RGB_MATRIX[0][0] + y_val * self.RGB_MATRIX[0][1] + z_val * self.RGB_MATRIX[0][2]
        g = x_val * self.RGB_MATRIX[1][0] + y_val * self.RGB_MATRIX[1][1] + z_val * self.RGB_MATRIX[1][2]
        b = x_val * self.RGB_MATRIX[2][0] + y_val * self.RGB_MATRIX[2][1] + z_val * self.RGB_MATRIX[2][2]

        h, s, _ = colorsys.rgb_to_hsv(max(0, r), max(0, g), max(0, b))
        return h, s


(
    QuirkBuilder(OSRAM, "LIGHTIFY A19 RGBW")
    .replaces(OsramColorInterceptor, endpoint_id=3)
    .replaces(OsramLightCluster, endpoint_id=3)
    .add_to_registry()
)
