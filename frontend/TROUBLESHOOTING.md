# 🔧 CCF API Troubleshooting Guide

## Problem: API Calls Show "Pending" Status

If your API calls are hanging and showing "pending" status, follow these steps to identify and fix the issue.

## 🚀 Quick Start

1. **Use the startup script** (recommended):
   ```bash
   cd frontend
   ./start_servers.sh
   ```

2. **Or start manually**:
   ```bash
   # Terminal 1: Start proxy server
   cd frontend
   python3 proxy_server.py
   
   # Terminal 2: Start frontend server
   cd frontend
   python3 -m http.server 8080
   ```

3. **Test connectivity**:
   - Open: `http://localhost:8080/debug_test.html`
   - Run all tests to identify issues

## 🔍 Step-by-Step Debugging

### Step 1: Check Server Status

**Check if CCF backend is running:**
```bash
curl http://localhost:8000/user/add
```

**Expected response:** JSON data or metrics
**If error:** CCF backend is not running

**Check if proxy server is running:**
```bash
curl http://localhost:5000/api/health
```

**Expected response:** `{"status": "healthy", "message": "CCF Proxy Server is running"}`
**If error:** Proxy server is not running

### Step 2: Check Port Availability

**Check what's using the ports:**
```bash
# Check port 8000 (CCF backend)
lsof -i :8000

# Check port 5000 (proxy server)
lsof -i :5000

# Check port 8080 (frontend)
lsof -i :8080
```

### Step 3: Check Network Connectivity

**Test direct connection to CCF:**
```bash
curl -v http://localhost:8000/user/add
```

**Test proxy connection:**
```bash
curl -v http://localhost:5000/api/health
```

## 🐛 Common Issues & Solutions

### Issue 1: CCF Backend Not Running

**Symptoms:**
- All API calls show "pending"
- Direct curl to CCF fails
- Error: "Connection refused"

**Solution:**
```bash
# Build and start CCF backend
cd /workspaces/CCF_FL_Block
make
./build/app
```

### Issue 2: Proxy Server Not Running

**Symptoms:**
- Frontend loads but API calls hang
- `/api/health` returns error
- Browser console shows network errors

**Solution:**
```bash
cd frontend
python3 proxy_server.py
```

### Issue 3: Python Dependencies Missing

**Symptoms:**
- Proxy server fails to start
- Import errors for Flask or requests

**Solution:**
```bash
cd frontend
pip3 install -r requirements.txt
```

### Issue 4: Certificate Issues

**Symptoms:**
- API calls work for non-authenticated endpoints
- Authenticated calls fail with certificate errors

**Solution:**
1. Check certificate files exist:
   ```bash
   ls -la workspace/sandbox_common/
   ```

2. Verify certificate format:
   ```bash
   openssl x509 -in workspace/sandbox_common/service_cert.pem -text -noout
   ```

### Issue 5: CORS Issues

**Symptoms:**
- Browser console shows CORS errors
- API calls fail in browser but work with curl

**Solution:**
The proxy server includes CORS headers. If issues persist:
```python
# In proxy_server.py, ensure CORS is enabled:
from flask_cors import CORS
app = Flask(__name__)
CORS(app)
```

### Issue 6: Wrong URLs

**Symptoms:**
- 404 errors
- API calls go to wrong endpoints

**Solution:**
Check the URLs in your CCF backend:
- CCF endpoints: `http://localhost:8000/app/...`
- Proxy endpoints: `http://localhost:5000/api/...`

## 🔧 Manual Testing

### Test 1: Simple User Add (No Auth Required)
```bash
curl -X POST http://localhost:8000/user/add \
  -H "Content-Type: application/json" \
  -d '{"msg": "test user"}'
```

### Test 2: Model Upload (No Auth Required)
```bash
curl -X POST http://localhost:8000/model/intial_model \
  -H "Content-Type: application/json" \
  -d '{"global_model": {"model_name": "test", "model_data": {"test": "data"}}}'
```

### Test 3: Proxy Server Health
```bash
curl http://localhost:5000/api/health
```

## 📊 Debug Information

### Check Browser Console
1. Open browser developer tools (F12)
2. Go to Console tab
3. Look for JavaScript errors
4. Check Network tab for failed requests

### Check Server Logs
**Proxy server logs:**
```bash
# Look for errors in proxy server output
python3 proxy_server.py
```

**CCF backend logs:**
```bash
# Check CCF application logs
./build/app
```

## 🚨 Emergency Fixes

### If Nothing Works:

1. **Restart everything:**
   ```bash
   # Kill all processes
   pkill -f "python3"
   pkill -f "ccf"
   
   # Restart CCF backend
   cd /workspaces/CCF_FL_Block
   make clean && make
   ./build/app &
   
   # Restart proxy server
   cd frontend
   python3 proxy_server.py &
   
   # Restart frontend
   python3 -m http.server 8080 &
   ```

2. **Check firewall/network:**
   ```bash
   # Test localhost connectivity
   ping localhost
   
   # Test port connectivity
   telnet localhost 8000
   telnet localhost 5000
   telnet localhost 8080
   ```

3. **Use different ports:**
   ```bash
   # Edit proxy_server.py
   app.run(host='0.0.0.0', port=5001, debug=True)
   
   # Edit script.js
   this.baseURL = 'http://localhost:8001';
   ```

## 📞 Getting Help

If you're still having issues:

1. **Run the debug test page:** `http://localhost:8080/debug_test.html`
2. **Check all server logs** for error messages
3. **Verify all services are running** on correct ports
4. **Test with simple curl commands** first
5. **Check browser console** for JavaScript errors

## ✅ Success Checklist

- [ ] CCF backend running on port 8000
- [ ] Proxy server running on port 5000
- [ ] Frontend server running on port 8080
- [ ] Debug test page shows all green checkmarks
- [ ] Simple API calls work (user add, model upload)
- [ ] Certificates configured (for authenticated calls)
- [ ] No JavaScript errors in browser console 