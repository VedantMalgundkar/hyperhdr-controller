class InvalidWifiRequest(Exception):
    """Raised for known input errors in WiFi ble action requests."""

    def __init__(self, message):
        super().__init__(message)
        self.message = message
