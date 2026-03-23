"""
Kognition API Client for sensor updates.

Sends door sensor state changes to the Kognition platform's /api/system/sensorUpdate endpoint.
Authenticates via X-API-Key header using a service API key configured in the Kognition instance.

Configuration (in yolink_data.local.json):
    "kognition": {
        "url": "http://your-instance.kognition.ai",
        "apiKey": "your-service-api-key",
        "deviceMap": {
            "<yolink-deviceId>": {
                "sensorId": "<couchdb-sensor-doc-id>",
                "sensorName": "<human-readable-name>",
                "cameraId": "<associated-camera-id>",
                "locationId": "<location-id>"
            }
        }
    }
"""

import requests
import time

from logger import Logger
log = Logger.getInstance().getLogger()


class KognitionClient:
    """Client for sending sensor updates to the Kognition API."""

    def __init__(self, config: dict):
        """
        Initialize the Kognition client.

        Args:
            config: The 'kognition' section from yolink_data.local.json
        """
        self.url = config.get('url', '').rstrip('/')
        self.api_key = config.get('apiKey', '')
        self.device_map = config.get('deviceMap', {})
        self.timeout = config.get('timeoutSeconds', 10)

        if not self.url:
            log.warning("Kognition URL not configured — sensor updates will be skipped")
        if not self.api_key:
            log.warning("Kognition API key not configured — sensor updates will fail auth")

        log.info("Kognition client initialized: url={}, devices={}".format(
            self.url, len(self.device_map)))

    def is_configured(self) -> bool:
        """Check if the client is properly configured."""
        return bool(self.url and self.api_key)

    def get_device_mapping(self, device_id: str) -> dict:
        """Get the Kognition mapping for a YoLink device ID."""
        return self.device_map.get(device_id)

    def send_sensor_update(self, device_id: str, state: str, alert_type: str = None) -> int:
        """
        Send a sensor state update to the Kognition API.

        Args:
            device_id: The YoLink device ID
            state: Door state ('open', 'closed', 'ajar')
            alert_type: YoLink alert type (e.g. 'openRemind' for ajar)

        Returns:
            0 on success, -1 on failure
        """
        if not self.is_configured():
            log.debug("Kognition client not configured, skipping sensor update")
            return -1

        mapping = self.get_device_mapping(device_id)
        if not mapping:
            log.warning("No Kognition mapping for device {}".format(device_id))
            return -1

        # Handle 'ajar' state from openRemind alerts
        if alert_type == 'openRemind':
            state = 'ajar'

        payload = {
            'deviceId': device_id,
            'locationId': mapping['locationId'],
            'cameraId': mapping['cameraId'],
            'state': state,
            'timestamp': int(time.time() * 1000),
            'attachImageIfMissing': True,
        }

        endpoint = '{}/api/system/sensorUpdate'.format(self.url)
        headers = {
            'Content-Type': 'application/json',
            'X-API-Key': self.api_key,
        }

        try:
            log.debug("Sending sensor update: {} -> {} ({})".format(
                mapping.get('sensorName', device_id), state, endpoint))

            r = requests.post(endpoint, json=payload, headers=headers, timeout=self.timeout)

            if r.status_code == 200:
                log.info("Sensor update sent: {} = {}".format(
                    mapping.get('sensorName', device_id), state))
                return 0
            elif r.status_code == 401:
                log.error("Sensor update auth failed (401) — check apiKey in config")
                return -1
            else:
                log.error("Sensor update failed: HTTP {} — {}".format(
                    r.status_code, r.text[:200]))
                return -1

        except requests.exceptions.Timeout:
            log.error("Sensor update timed out: {}".format(endpoint))
            return -1
        except requests.exceptions.ConnectionError as e:
            log.error("Sensor update connection failed: {}".format(str(e)[:200]))
            return -1
        except Exception as e:
            log.error("Sensor update error: {}".format(str(e)))
            return -1
