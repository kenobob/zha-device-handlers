"""Osram LIGHTIFY A19 RGBW device."""

import math

from zigpy.profiles import zha
from zigpy.quirks import CustomDevice
from zigpy.zcl.clusters.general import (
    Basic,
    Groups,
    Identify,
    LevelControl,
    OnOff,
    Ota,
    Scenes,
)
from zigpy.zcl.clusters.lighting import Color

from zhaquirks.const import (
    DEVICE_TYPE,
    ENDPOINTS,
    INPUT_CLUSTERS,
    MODELS_INFO,
    OUTPUT_CLUSTERS,
    PROFILE_ID,
)
from zhaquirks.osram import OSRAM, OsramLightCluster


class OsramHSColorCluster(Color):
    """Custom color cluster that converts XY commands to Hue/Sat."""

    async def command(
        self,
        command_id,
        *args,
        manufacturer=None,
        expect_reply=True,
        tsn=None,
        **kwargs,
    ):
        """Intercept MoveToColor and convert to Hue/Sat."""

        if command_id == 0x07:  # MoveToColor (XY)

            if "color_x" in kwargs and "color_y" in kwargs:
                x = kwargs["color_x"] / 65535
                y = kwargs["color_y"] / 65535
                transition = kwargs.get("transition_time", 0)

            else:
                x = args[0] / 65535
                y = args[1] / 65535
                transition = args[2] if len(args) > 2 else 0

            hue, sat = self.xy_to_hs(x, y)

            # convert to zigbee scale
            hue = int(hue * 254 / 360)
            sat = int(sat * 254 / 100)

            return await super().command(
                0x06,  # MoveToHueAndSaturation
                hue,
                sat,
                transition,
                manufacturer=manufacturer,
                expect_reply=expect_reply,
                tsn=tsn,
            )

        return await super().command(
            command_id,
            *args,
            manufacturer=manufacturer,
            expect_reply=expect_reply,
            tsn=tsn,
            **kwargs,
        )

    def xy_to_hs(self, x, y):
        """Convert XY color to Hue/Saturation."""

        if y == 0:
            return 0, 0

        z = 1.0 - x - y

        Y = 1.0
        X = (Y / y) * x
        Z = (Y / y) * z

        r = X * 1.656492 - Y * 0.354851 - Z * 0.255038
        g = -X * 0.707196 + Y * 1.655397 + Z * 0.036152
        b = X * 0.051713 - Y * 0.121364 + Z * 1.011530

        r = max(r, 0)
        g = max(g, 0)
        b = max(b, 0)

        max_rgb = max(r, g, b)

        if max_rgb == 0:
            return 0, 0

        r /= max_rgb
        g /= max_rgb
        b /= max_rgb

        max_c = max(r, g, b)
        min_c = min(r, g, b)
        delta = max_c - min_c

        if delta == 0:
            hue = 0
        elif max_c == r:
            hue = 60 * (((g - b) / delta) % 6)
        elif max_c == g:
            hue = 60 * (((b - r) / delta) + 2)
        else:
            hue = 60 * (((r - g) / delta) + 4)

        sat = 0 if max_c == 0 else delta / max_c

        return hue, sat * 100


class LIGHTIFYA19RGBW(CustomDevice):
    """Osram LIGHTIFY A19 RGBW device."""

    signature = {
        MODELS_INFO: [(OSRAM, "LIGHTIFY A19 RGBW")],
        ENDPOINTS: {
            3: {
                PROFILE_ID: zha.PROFILE_ID,
                DEVICE_TYPE: zha.DeviceType.COLOR_DIMMABLE_LIGHT,
                INPUT_CLUSTERS: [
                    Basic.cluster_id,
                    Identify.cluster_id,
                    Groups.cluster_id,
                    Scenes.cluster_id,
                    OnOff.cluster_id,
                    LevelControl.cluster_id,
                    Color.cluster_id,
                    OsramLightCluster.cluster_id,
                ],
                OUTPUT_CLUSTERS: [Ota.cluster_id],
            }
        },
    }

    replacement = {
        ENDPOINTS: {
            3: {
                PROFILE_ID: zha.PROFILE_ID,
                DEVICE_TYPE: zha.DeviceType.COLOR_DIMMABLE_LIGHT,
                INPUT_CLUSTERS: [
                    Basic,
                    Identify,
                    Groups,
                    Scenes,
                    OnOff,
                    LevelControl,
                    OsramHSColorCluster,
                    OsramLightCluster,
                ],
                OUTPUT_CLUSTERS: [Ota],
            }
        }
    }
