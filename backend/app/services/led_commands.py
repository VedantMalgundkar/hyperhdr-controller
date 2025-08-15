import math
import json
import asyncio
import requests
import websockets

HOST = "localhost"
PORT = 8090
TAN = 1

base_url = f"http://{HOST}:{PORT}"
ws_url = f"ws://{HOST}:{PORT}"

async def get_led_stream():
    uri = f"ws://{HOST}:{PORT}"
    led_data = None
    async with websockets.connect(uri) as ws:

        # 1. Start LED colors stream
        start_msg = {
            "command": "ledcolors",
            "subcommand": "ledstream-start",
            "tan": TAN
        }

        await ws.send(json.dumps(start_msg))

        try:
            for _ in range(10):
                msg = await ws.recv()
                try:
                    data = json.loads(msg)
                    if data.get('command', '') == "ledcolors-ledstream-update":
                        led_data = data  
                        break
                except json.JSONDecodeError:
                    print("[Binary frame received]", type(msg), len(msg))

        finally:
            # 3. Stop LED colors stream
            stop_msg = {
                "command": "ledcolors",
                "subcommand": "ledstream-stop",
                "tan": TAN
            }
            await ws.send(json.dumps(stop_msg))

            # 4. Close connection
            await ws.close()
        
        return led_data

def set_hyperhdr_brightness(brightness: int):
    """
    Adjust the brightness of HyperHDR.

    Args:
        ip (str): IP address of the HyperHDR instance (e.g., "192.168.1.100").
        brightness (int): Brightness level (0-255).
    
    Returns:
        dict: JSON response from HyperHDR.
    """
    url = f"{base_url}/json-rpc"
    payload = {
        "command": "adjustment",
        "adjustment": {
            "brightness": max(0, min(brightness, 100))
        }
    }

    response = requests.post(url, json=payload)
    response.raise_for_status()
    return response.json()

def get_current_brightness():
    """
    Get the current brightness level (0–100) from HyperHDR.

    Returns:
        int | None: Brightness level if found, else None.
    """
    url = f"{base_url}/json-rpc"
    payload = {
        "command": "serverinfo"
    }

    response = requests.post(url, json=payload)
    response.raise_for_status()
    data = response.json()

    adjustments = data.get("info", {}).get("adjustment", [])
    if adjustments:
        return {"brightness" : adjustments[0].get("brightness")}

    return None


def get_hyperhdr_effects():
    """
    Fetch the list of available effects from HyperHDR.

    Returns:
        list: List of effect names.
    """
    url = f"{base_url}/json-rpc"
    payload = {
        "command": "serverinfo"
    }

    response = requests.post(url, json=payload)
    response.raise_for_status()
    data = response.json()

    effects = data.get("info", {}).get("effects", [])

    filtered_effects = [effect for effect in effects if not effect['name'].lower().startswith("music")]

    return filtered_effects

def clear_hyperhdr_effect(priority: int = 100):
    """
    Clear any currently running effect at the given priority.
    """
    url = f"{base_url}/json-rpc"
    payload = {
        "command": "clear",
        "priority": priority
    }

    response = requests.post(url, json=payload)
    response.raise_for_status()
    return response.json()


def apply_hyperhdr_effect(effect_name: str, duration_ms: int = 0):
    """
    Apply an effect to HyperHDR after clearing any running effect at the same priority.

    Args:
        effect_name (str): Name of the effect to apply (e.g., "Rainbow swirl fast").
        duration_ms (int): Duration in milliseconds to run the effect. 0 means infinite.

    Returns:
        dict: JSON response from HyperHDR.
    """
    priority = 100
    clear_hyperhdr_effect(priority)

    url = f"{base_url}/json-rpc"
    payload = {
        "command": "effect",
        "effect": {
            "name": effect_name
        },
        "priority": priority,
        "duration": duration_ms
    }

    response = requests.post(url, json=payload)
    response.raise_for_status()
    return response.json()

async def check_input_signal():
    url = f"{base_url}/json-rpc"
    payload = {
        "command": "serverinfo"
    }
    response = requests.post(url, json=payload)
    response.raise_for_status()
    data = response.json()

    priorities = data.get('info', {}).get('priorities')
    if not priorities:
        return {"status": "failed", error: "priorities are missing in serverinfo"}
    
    is_it_fallback = True
    
    any_other_active_source = any(["usb" not in priority.get("owner","").lower() and priority["visible"] for priority in priorities])

    if not any_other_active_source:
        led_position = get_led_postion_data()
        led_color = await get_led_stream()    
        led_color = led_color.get("result",{}).get("leds",[])
        led_color = transform_flat_led_colors_for_each_led(led_color)
        led_position = add_color_to_led_position_data(led_position, led_color)
        TOP_THRESHOLD = 0.05
        BOTTOM_THRESHOLD = 0.95
        result = get_leds_by_direction(led_position,TOP_THRESHOLD=TOP_THRESHOLD, BOTTOM_THRESHOLD = BOTTOM_THRESHOLD)
        is_it_fallback = check_top_bottom_led_for_fallback(result["top"], result["bottom"])


    current_input = {}
    valid_effects = [effect["name"] for effect in get_hyperhdr_effects()]
    
    for priority in priorities:
        usb_owner = "usb" in priority.get("owner","").lower()
        is_valid_effect = priority.get("owner","") in valid_effects

        if priority["visible"]:
            current_input = { **priority, "value": priority.get("owner","") } if is_valid_effect else priority
            current_input = { **priority, "is_it_fallback": is_it_fallback } if usb_owner else priority
            break

    return current_input

def check_capture_card_signal():
    url = f"{base_url}/json-rpc"
    payload = {
        "command": "serverinfo"
    }

    response = requests.post(url, json=payload)
    response.raise_for_status()
    data = response.json()

    priorities = data.get('info', {}).get('priorities')
    if not priorities:
        return {"status": "failed", error: "priorities are missing in serverinfo"}

    capture_card = {}

    for priority in priorities:
        if "usb" in priority.get("owner","").lower():
            capture_card = priority
            break
    
    return capture_card

def set_signal_detection(enabled: bool):
    url = f"{base_url}/json-rpc"

    grabber_on = {
        "command": "componentstate",
        "componentstate": {
            "component": "VIDEOGRABBER",
            "state": enabled
        }
    }
    res = requests.post(url, json = grabber_on)
    print(f"{'Enabled' if enabled else 'Disabled'} signal detection:", res.json())
    return res.json()

def apply_hyperhdr_color(rgb: list[int], duration_ms: int = 0):
    """
    Apply a static color to HyperHDR.

    Args:
        rgb (list[int]): List with RGB values (e.g., [255, 0, 0] for red).
        duration_ms (int): Duration in milliseconds. 0 means infinite.

    Returns:
        dict: JSON response from HyperHDR.
    """
    url = f"{base_url}/json-rpc"
    payload = {
        "command": "color",
        "color": rgb,
        "priority": 100,
        "duration": duration_ms
    }

    response = requests.post(url, json=payload)
    response.raise_for_status()
    return response.json()


def get_led_postion_data():
    url = f"{base_url}/json-rpc"
    payload = {
        "command": "serverinfo"
    }

    response = requests.post(url, json=payload)
    response.raise_for_status()
    data = response.json()

    leds = data.get('info', {}).get('leds')
    
    return leds

def check_top_bottom_led_for_fallback(top_leds, bottom_leds):
    no_of_top_leds = len(top_leds)
    no_of_bottom_leds = len(bottom_leds)

    # print({
    #     "top": top_leds,
    #     "bottom": bottom_leds
    # })
    
    top_fallback_colors = {
        (255, 255, 6): 0,   # Bright yellow (slightly greenish)
        (255, 0, 255): 0,   # Pure magenta
        (0, 10, 255): 0,    # Deep blue (slightly purplish)
        (0, 255, 0): 0,     # Pure green
        (6, 255, 255): 0,   # Cyan / aqua
        (255, 11, 0): 0     # Bright red (slightly orange)
    }
    
    bottom_fallback_colors = {
        (255, 255, 6): 0,   # Bright yellow (slightly greenish)
        (255, 0, 255): 0,   # Pure magenta
        (0, 10, 255): 0,    # Deep blue (slightly purplish)
        (0, 255, 0): 0,     # Pure green
        (6, 255, 255): 0,   # Cyan / aqua
        (255, 11, 0): 0     # Bright red (slightly orange)
    }

    loop_til = max(len(top_leds),len(bottom_leds))

    for led_ind in range(loop_til):
        if led_ind < len(top_leds):
            curr_top_color = tuple(top_leds[led_ind]['color'])
            if curr_top_color in top_fallback_colors:
                top_fallback_colors[curr_top_color] += 1 
        
        if led_ind < len(bottom_leds):
            curr_bottom_color = tuple(bottom_leds[led_ind]['color'])
            if curr_bottom_color in bottom_fallback_colors:
                bottom_fallback_colors[curr_bottom_color] += 1

    min_top_colors_freq = math.floor(no_of_top_leds * 0.09)
    min_bottom_colors_freq = math.floor(no_of_bottom_leds * 0.09)

    are_these_top_colors_fallback = all([ freq >= min_top_colors_freq for _,freq in top_fallback_colors.items()])
    are_these_bottom_colors_fallback = all([ freq >= min_bottom_colors_freq for _,freq in bottom_fallback_colors.items()])

    # print(top_fallback_colors)
    # print(f"{min_top_colors_freq}/{no_of_top_leds}")
    # print(are_these_top_colors_fallback)
    
    # print(bottom_fallback_colors)
    # print(f"{min_bottom_colors_freq}/{no_of_bottom_leds}")
    # print(are_these_bottom_colors_fallback)
    return are_these_bottom_colors_fallback and are_these_top_colors_fallback

def transform_flat_led_colors_for_each_led(led_color):
    return [led_color[i:i+3] for i in range(0, len(led_color), 3)]

def add_color_to_led_position_data(led_position,led_color):
    return [{**each_position ,"color": led_color[index],"led_ind": index} for index,each_position in enumerate(led_position)]

def get_leds_by_direction(
    led_position,
    TOP_THRESHOLD=0.05,
    BOTTOM_THRESHOLD=0.95,
    LEFT_THRESHOLD=0.05,
    RIGHT_THRESHOLD=0.95
):
    top_leds = []
    bottom_leds = []
    left_leds = []
    right_leds = []

    for led in led_position:
        # Top
        if 0.05 < led["hmin"] < 0.95 and led["vmin"] <= TOP_THRESHOLD:
            top_leds.append(led)

        # Bottom
        if 0.05 < led["hmin"] < 0.95 and led["vmax"] >= BOTTOM_THRESHOLD:
            bottom_leds.append(led)

        # Left
        if 0.05 < led["vmin"] < 0.95 and led["hmin"] <= LEFT_THRESHOLD:
            left_leds.append(led)

        # Right
        if 0.05 < led["vmin"] < 0.95 and led["hmax"] >= RIGHT_THRESHOLD:
            right_leds.append(led)

    mapping = {
        "top": top_leds,
        "bottom": bottom_leds,
        "left": left_leds,
        "right": right_leds
    }

    return mapping

async def get_led_stream():
    uri = f"ws://{HOST}:{PORT}"
    led_data = None
    async with websockets.connect(uri) as ws:

        # 1. Start LED colors stream
        start_msg = {
            "command": "ledcolors",
            "subcommand": "ledstream-start",
            "tan": TAN
        }

        await ws.send(json.dumps(start_msg))

        try:
            for _ in range(10):
                msg = await ws.recv()
                try:
                    data = json.loads(msg)
                    if data.get('command', '') == "ledcolors-ledstream-update":
                        led_data = data  
                        break
                except json.JSONDecodeError:
                    print("[Binary frame received]", type(msg), len(msg))

        finally:
            # 3. Stop LED colors stream
            stop_msg = {
                "command": "ledcolors",
                "subcommand": "ledstream-stop",
                "tan": TAN
            }
            await ws.send(json.dumps(stop_msg))

            # 4. Close connection
            await ws.close()
        
        return led_data