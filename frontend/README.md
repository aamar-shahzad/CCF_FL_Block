# CCF Federated Learning Platform Frontend

This frontend provides a comprehensive interface for interacting with the CCF Federated Learning backend. It supports all the endpoints defined in your `app.cpp` file with proper certificate-based authentication.

## Features

### 🔐 Certificate-Based Authentication
- **User Certificates**: Required for uploading local weights and downloading models/weights
- **Member Certificates**: Required for triggering federated aggregation
- **Service Certificate**: Used for verifying CCF server connections
- Certificate files are handled securely through a Python proxy server
- Visual status indicators for certificate configuration

### 👥 User Management
- Add users to the federated learning system
- Uses `/user/add` endpoint (no authentication required)

### 📦 Model Management
- Upload initial models to the system
- Uses `/model/intial_model` endpoint (no authentication required)
- Support for JSON file uploads
- Automatic model ID assignment

### ⚖️ Weight Upload
- Upload local model weights for federated learning
- Uses `/model/upload/local_model_weights` endpoint (user authentication required)
- Support for JSON file uploads
- Round-based weight tracking

### 🔄 Federated Aggregation
- Trigger federated learning aggregation
- Uses `/model/aggregate_weights_local` endpoint (member authentication required)
- Model ID and round number specification
- Real-time aggregation results display

### 📥 Download Operations
- **Model Details**: Download model information using `/model/download/global` endpoint
- **Global Weights**: Download aggregated weights using `/model/download_gloabl_weights` endpoint
- Both operations require user authentication
- JSON result display with file download capability

## API Endpoints Used

| Endpoint | Method | Auth Required | Purpose |
|----------|--------|---------------|---------|
| `/user/add` | POST | No | Add users to the system |
| `/model/intial_model` | POST | No | Upload initial models |
| `/model/upload/local_model_weights` | POST | User Cert | Upload local weights |
| `/model/aggregate_weights_local` | PUT | Member Cert | Trigger aggregation |
| `/model/download/global` | GET | User Cert | Download model details |
| `/model/download_gloabl_weights` | GET | User Cert | Download global weights |

## Setup Instructions

### 1. Install Proxy Server Dependencies
```bash
cd frontend
pip install -r requirements.txt
```

### 2. Start the Proxy Server
```bash
python proxy_server.py
```
The proxy server will run on `http://localhost:5000`

### 3. Start the Frontend Server
```bash
python3 -m http.server 8080
```
The frontend will be available at `http://localhost:8080`

### 4. Ensure CCF Backend is Running
Make sure your CCF backend is running on `http://localhost:8000`

## Getting Started

1. **Start all servers** (proxy, frontend, and CCF backend)

2. **Open the frontend** in your browser:
   ```
   http://localhost:8080
   ```

3. **Configure Authentication** (Auth tab):
   - Upload User Certificate and Private Key for participant operations
   - Upload Member Certificate and Private Key for aggregation operations
   - Certificates should be PEM files (.pem, .crt, .key)

4. **Use the system**:
   - Add users (Users tab)
   - Upload initial models (Models tab)
   - Upload local weights (Weights tab)
   - Trigger aggregation (Aggregate tab)
   - Download results (Download tab)

## Certificate Requirements

### File Formats
- **User Certificates**: PEM files (.pem, .crt, .key)
- **Member Certificates**: PEM files (.pem, .crt, .key)
- **Service Certificate**: Located at `./workspace/sandbox_common/service_cert.pem`

### Certificate Types
- **User Certificates**: Required for participant operations (upload weights, download models/weights)
- **Member Certificates**: Required for aggregation operations
- **Service Certificate**: Used to verify CCF server connections

## Usage Examples

### Adding a User
1. Go to the "Users" tab
2. Enter a user message in the text area
3. Click "Add User"

### Uploading a Model
1. Go to the "Models" tab
2. Enter a model name
3. Enter model data as JSON or upload a JSON file
4. Click "Upload Model"
5. Note the returned Model ID for future use

### Uploading Weights
1. Configure User certificates in the "Auth" tab
2. Go to the "Weights" tab
3. Enter the Model ID and Round Number
4. Enter weights data as JSON array or upload a JSON file
5. Click "Upload Weights"

### Triggering Aggregation
1. Configure Member certificates in the "Auth" tab
2. Go to the "Aggregate" tab
3. Enter the Model ID and Round Number
4. Click "Start Aggregation"
5. View the aggregation results

### Downloading Results
1. Configure User certificates in the "Auth" tab
2. Go to the "Download" tab
3. Enter a Model ID
4. Click "Download Model" or "Download Weights"
5. View results and optionally save to file

## File Formats

### Model Data JSON
```json
{
  "layers": [
    {
      "weights": [0.1, 0.2, 0.3]
    }
  ]
}
```

### Weights Data JSON
```json
[0.1, 0.2, 0.3, 0.4, 0.5]
```

### Certificate Files
- **Format**: PEM files (.pem, .crt, .key)
- **User Certificates**: Required for participant operations
- **Member Certificates**: Required for aggregation operations
- **Service Certificate**: Used for server verification

## Architecture

The frontend uses a three-tier architecture:

1. **Frontend (Browser)**: HTML/CSS/JavaScript interface
2. **Proxy Server (Python)**: Handles certificate-based requests
3. **CCF Backend (C++)**: Federated learning operations

```
Browser → Proxy Server → CCF Backend
```

## Error Handling

The frontend includes comprehensive error handling:
- Network error detection
- JSON validation
- Certificate requirement warnings
- User-friendly error messages
- Loading states for all operations

## Browser Compatibility

- Modern browsers with ES6+ support
- File API support for certificate uploads
- Fetch API for HTTP requests
- FormData support for file uploads

## Security Notes

- Certificates are handled securely through the Python proxy server
- Temporary certificate files are created and cleaned up automatically
- All sensitive operations require proper CCF authentication
- The frontend is designed for development/testing purposes

## Customization

To change the backend URL, modify the `CCF_SERVER` variable in `proxy_server.py`:

```python
CCF_SERVER = "http://your-ccf-server:port"
```

To change the service certificate path, modify the `serviceCertPath` in `script.js`:

```javascript
this.serviceCertPath = './path/to/your/service_cert.pem';
``` 