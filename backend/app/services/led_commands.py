import requests

base_url = "http://localhost:8090"

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
    return effects

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

def check_input_signal():
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

    current_input = {}
    valid_effects = [effect["name"] for effect in get_hyperhdr_effects()]
    
    for priority in priorities:
        usb_owner = "usb" in priority.get("owner","").lower()
        is_valid_effect = priority.get("owner","") in valid_effects
        
        if priority["visible"] and not usb_owner:
            current_input = { **priority, "value": priority.get("owner","") } if is_valid_effect else priority
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