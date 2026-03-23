# Kognition AI Integration Guide — YoLink IoT Open/Close Door Sensor

Kognition AI can display the status of YoLink sensors directly within the Kognition user interface. Follow these instructions to set up your instance of Kognition to receive real-time sensor updates.

## Supported Hardware

**Door Sensor:** Model #YS7704-UC  
https://shop.yosmart.com/products/yolink-smart-window-door-sensor-works-with-alexa-and-ifttt-yolink-hub-required

**YoLink Hub** (required — must be installed at the location and paired with the sensor):  
https://shop.yosmart.com/products/yolink-hub

## Installation

### 1. Clone the repository

Install on the Kognition SPS server in the `/home/kognition/YoLinkAPI_V2` folder:

```bash
cd /home/kognition
git clone https://github.com/KognitionAI/YoLinkAPI_V2.git
```

### 2. Install Python dependencies

```bash
cd /home/kognition/YoLinkAPI_V2/
pip3 install -r requirements.txt
```

### 3. Create the systemd service

Add `yolink.service` to `/etc/systemd/system/yolink.service`:

```ini
[Unit]
Description=YoLink MQTT Service
After=network.service

[Service]
ExecStart=/home/kognition/YoLinkAPI_V2/start_yolinkv2homeassistant.sh
WorkingDirectory=/home/kognition/YoLinkAPI_V2/
StandardOutput=inherit
StandardError=inherit
Restart=always
User=kognition

[Install]
WantedBy=multi-user.target
```

After creating the service file, reload systemd:

```bash
sudo systemctl daemon-reload
```

### 4. Service commands

```bash
sudo systemctl start yolink
sudo systemctl stop yolink
sudo systemctl restart yolink
sudo systemctl status yolink
```

The service runs:

```bash
python3 /home/kognition/YoLinkAPI_V2/src/yolinkv2homeassistant.py \
  --config /home/kognition/YoLinkAPI_V2/src/yolink_data.local.json \
  --debug
```

This starts an MQTT subscriber that connects to the YoLink cloud with the specified IDs from `yolink_data.local.json` to receive sensor status updates.

## Configuration

### Obtain Device Info and Home ID

This is a one-time step (repeat when adding new devices):

```bash
cd /home/kognition/YoLinkAPI_V2/src/utils
PYTHONPATH=/home/kognition/YoLinkAPI_V2/src python3 yolink_utils.py \
  --config /home/kognition/YoLinkAPI_V2/src/utils/yolink_data.json \
  --devices
```

Copy the list of JSON objects with all device data into your config file.

### Config file: `yolink_data.local.json`

Create `src/yolink_data.local.json` with your YoLink credentials and device list. See `src/yolink_config.json` for a complete template.

**Key sections:**

```json
{
  "features": {
    "localMQTT": false,
    "influxDB": false
  },
  "yoLink": {
    "apiv2": {
      "apiUrl": "https://api.yosmart.com/open/yolink/v2/api",
      "tokenUrl": "https://api.yosmart.com/open/yolink/token",
      "uaId": "your-ua-id",
      "secId": "your-sec-id",
      "mqtt": {
        "url": "api.yosmart.com",
        "port": 8003,
        "topic": "yl-home/{}/+/report"
      }
    },
    "yolinkHomeId": "your-home-id",
    "deviceInfo": [
      {
        "deviceId": "d88b4c020002b852",
        "deviceUDID": "da6467DD49c94e8ea82ce5979f2b3efe",
        "name": "Event Hall 1",
        "token": "YOUR_DEVICE_TOKEN",
        "type": "DoorSensor",
        "parentDeviceId": null
      }
    ]
  }
}
```

### Kognition API Integration (Authentication Required)

To send sensor updates to the Kognition platform, add a `kognition` section to your `yolink_data.local.json`:

```json
{
  "kognition": {
    "url": "http://your-instance.kognition.ai",
    "apiKey": "your-service-api-key",
    "timeoutSeconds": 10,
    "deviceMap": {
      "d88b4c020002b852": {
        "sensorId": "couchdb-sensor-doc-id",
        "sensorName": "Event Hall 1",
        "cameraId": "associated-camera-doc-id",
        "locationId": "location-doc-id"
      }
    }
  }
}
```

**Fields:**

| Field | Description |
|-------|-------------|
| `url` | Kognition instance URL. **Use `http` (not `https`) if behind Cloudflare tunnel.** |
| `apiKey` | Service API key configured on the Kognition instance (see below) |
| `timeoutSeconds` | HTTP request timeout (default: 10) |
| `deviceMap` | Maps YoLink `deviceId` → Kognition sensor/camera/location IDs |

#### Generating the API Key

The Kognition `/api/system/sensorUpdate` endpoint requires authentication. For IoT services like YoLink, use a **service API key** instead of a user session token.

**Option A — Set via environment variable** (on the Kognition server):

```bash
# Add to the frontend pod's environment
export KOGNITION_SERVICE_API_KEY="your-strong-random-key"
```

**Option B — Set via config.json** (in the Kognition instance):

Add to your `config.json`:

```json
{
  "system": {
    "serviceApiKey": "your-strong-random-key"
  }
}
```

Generate a strong key:

```bash
openssl rand -base64 32
```

Use the same key value in both the Kognition instance config and the `apiKey` field in `yolink_data.local.json`.

#### How It Works

When a door sensor event is received from YoLink, the service sends an authenticated POST to:

```
POST http://your-instance.kognition.ai/api/system/sensorUpdate
X-API-Key: your-service-api-key
Content-Type: application/json

{
  "deviceId": "d88b4c020002b852",
  "locationId": "location-doc-id",
  "cameraId": "camera-doc-id",
  "state": "open",
  "timestamp": 1679500000000,
  "attachImageIfMissing": true
}
```

The `state` field will be one of: `open`, `closed`, or `ajar` (when the door has been left open — triggered by YoLink's `openRemind` alert type).

> **Note:** Previous versions used an unauthenticated `requests.post()` with a hardcoded URL and device mapping in the Python code. The new approach reads everything from config and authenticates via `X-API-Key`. No code changes are needed per-customer — just update the config file.

## Kognition Database Setup

### Sensor Records in CouchDB

For the system to work properly, you must map your YoLink `deviceId` to sensor records in the `kognition` database of your Kognition SPS instance.

Example sensor document:

```json
{
  "_id": "9599e3f0624bd5ca4bd35383ac002cdb",
  "type": "doorSensor",
  "name": "Event Hall 1",
  "manufacturer": "YoLink",
  "model": "YS7704-UC",
  "description": "Open / Closed Door Sensor - 3V DC (2 AAA Battery)",
  "deviceId": "d88b4c024002b852",
  "deviceUDID": "da64678c49c9434ea82ce5979f2b3efe",
  "token": "DD234FBB52A7944CEDC09A65782CF37F",
  "state": "closed",
  "lastUpdated": "2023-02-07 06:40:33",
  "locationId": "1675aabbc45d1f4e0b4781bec1000d78",
  "xpos": "750",
  "ypos": "140"
}
```

### CouchDB View

CouchDB must have the `sensorsByDeviceId` view installed:

**URL:** `http://couchdb-ip:5984/_utils/#database/kognition/_design/Manual/_view/sensorsByDeviceId`

**Map function:**

```javascript
function(doc) {
  if (doc.type == 'doorSensor') emit(doc.name, doc.deviceId)
}
```

## Kognition Helm Configuration

The Kognition `alert-service` must be running with the `hostPort` exposed in `values.yaml`:

```yaml
alert-service:
  enabled: true
  hostPort:
    enabled: true
    port: 8084
```

## Troubleshooting

### Sensor updates failing with 401

The Kognition API now requires authentication. Ensure:
1. The `apiKey` in `yolink_data.local.json` matches the key configured on the Kognition instance
2. The key is set via either `KOGNITION_SERVICE_API_KEY` env var or `config.json` → `system.serviceApiKey`

### Sensor updates not reaching Kognition

Check the service logs:

```bash
sudo journalctl -u yolink -f
```

Look for:
- `Kognition client initialized` — confirms the integration is configured
- `Sensor update sent: Event Hall 1 = open` — successful update
- `Sensor update auth failed (401)` — API key mismatch
- `Sensor update connection failed` — network/URL issue

### Device not found in mapping

If you see `No Kognition mapping for device <id>`, add the device to the `deviceMap` in your config file. The `deviceId` must match exactly.
