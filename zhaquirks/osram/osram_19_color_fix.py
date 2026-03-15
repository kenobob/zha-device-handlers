"""Osram LIGHTIFY A19 RGBW device - Color Command Interceptor Version."""

import colorsys
from zigpy.profiles import zha
from zigpy.quirks import CustomCluster, CustomDevice
import zigpy.zcl.clusters.lighting as lighting
from zigpy.zcl.clusters.general import (
    Basic, 
    Groups, 
    Identify, 
    LevelControl, 
    OnOff, 
    Ota, 
    Scenes,
)

from zhaquirks.osram import OSRAM, OsramLightCluster
from zhaquirks.const import (
    DEVICE_TYPE, 
    ENDPOINTS, 
    INPUT_CLUSTERS, 
    MODELS_INFO, 
    OUTPUT_CLUSTERS, 
    PROFILE_ID,
)

class OsramColorInterceptor(CustomCluster, lighting.Color):
    """Intercept XY commands and translate them to HS."""

    async def command(self, command_id, *args, **kwargs):
        """Intercept Move to Color (XY) and redirect to Move to Hue and Sat."""
        
        # 0x0007 is the 'Move to Color' (XY) command
        if command_id == 0x0007:
            x_raw = None
            y_raw = None
            tr_time = 0

            # 1. Check kwargs (Common for service calls)
            if "color_x" in kwargs:
                x_raw = kwargs["color_x"]
                y_raw = kwargs.get("color_y")
                tr_time = kwargs.get("transition_time", 0)
            
            # 2. Check if args[0] is a command object (Common in newer zigpy)
            elif args and hasattr(args[0], "color_x"):
                x_raw = args[0].color_x
                y_raw = args[0].color_y
                tr_time = getattr(args[0], "transition_time", 0)

            # 3. Check positional args (Fallback for manual CLI commands)
            elif len(args) >= 2:
                x_raw = args[0]
                y_raw = args[1]
                tr_time = args[2] if len(args) > 2 else 0

            # If we successfully caught the values, perform the translation
            if x_raw is not None and y_raw is not None:
                try:
                    # Normalize raw uint16 to 0.0 - 1.0
                    x = x_raw / 65535.0
                    y = y_raw / 65535.0
                    
                    # Prevent division by zero
                    y = max(y, 0.000001)
                                        
                    # XY to Hue/Saturation
                    h, s, _ = self.xy_to_hs(x, y)

                    # Saturation Limiter (Tweak this to fix 'over-saturation')
                    # SATURATION_LIMITER = 1 
                    # s = min(1.0, s * SATURATION_LIMITER)
                    
                    # Scale for Zigbee (0-254 range)
                    # Zigbee Hue 0xFE = 254
                    zigbee_hue = max(0, min(254, int(h * 254)))
                    zigbee_sat = max(0, min(254, int(s * 254)))
                    
                    # Send command 0x0006 (Move to Hue and Saturation)
                    # We call move_to_hue_and_saturation directly as it handles formatting
                    return await self.move_to_hue_and_saturation(
                        hue=zigbee_hue,
                        saturation=zigbee_sat,
                        transition_time=tr_time
                    )
                except Exception:
                    # Fallback to default XY if math goes sideways
                    pass

        # Fallback to standard behavior for all other commands (or if translation failed)
        return await super().command(command_id, *args, **kwargs)

    # Do the math to get from XY to Hue and Saturation. Assuming bulb supports Gamut B Matrix color space   
    def xy_to_hs(self, x, y):
        # XY to RGB Math
        z = max(0.0, 1.0 - x - y)
        Y_val = 1.0 
        X_val = (Y_val / y) * x
        Z_val = (Y_val / y) * z
        
        #sRGB Matrix (tuned for monitors)
        #r = X_val * 3.2406 - Y_val * 1.5372 - Z_val * 0.4986
        #g = -X_val * 0.9689 + Y_val * 1.8758 + Z_val * 0.0415
        #b = X_val * 0.0557 - Y_val * 0.2040 + Z_val * 1.0570

        # Gamut B Matrix
        # These values are tuned for LED hardware (rather than monitors)
        r = X_val * 1.656492 - Y_val * 0.354851 - Z_val * 0.255038
        g = -X_val * 0.707196 + Y_val * 1.655397 + Z_val * 0.036152
        b = X_val * 0.051713 - Y_val * 0.121364 + Z_val * 1.011530
        
        # RGB to Hue/Saturation
        h, s, v = colorsys.rgb_to_hsv(max(0, r), max(0, g), max(0, b))

        return h, s, v


class LIGHTIFYA19RGBW(CustomDevice):
    """Osram LIGHTIFY A19 RGBW device."""

    signature = {
        MODELS_INFO: [(OSRAM, "LIGHTIFY A19 RGBW")],
        ENDPOINTS: {
            3: {
                PROFILE_ID: zha.PROFILE_ID,
                DEVICE_TYPE: zha.DeviceType.COLOR_DIMMABLE_LIGHT,
                INPUT_CLUSTERS: [
                    Basic.cluster_id, Identify.cluster_id, Groups.cluster_id,
                    Scenes.cluster_id, OnOff.cluster_id, LevelControl.cluster_id,
                    lighting.Color.cluster_id, OsramLightCluster.cluster_id,
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
                    Basic.cluster_id, Identify.cluster_id, Groups.cluster_id,
                    Scenes.cluster_id, OnOff.cluster_id, LevelControl.cluster_id,
                    OsramColorInterceptor, # The interceptor
                    OsramLightCluster,
                ],
                OUTPUT_CLUSTERS: [Ota.cluster_id],
            }
        }
    }
