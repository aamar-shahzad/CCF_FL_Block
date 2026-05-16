# CCF Certificate Setup Guide

## Overview

The CCF Federated Learning application now uses **automatic certificate loading** from the `workspace/sandbox_common/` folder instead of requiring manual uploads through the frontend.

## Certificate Structure

### Expected Certificate Files

The application expects certificates to be located in `./workspace/sandbox_common/` with the following naming convention:

#### User Certificates (for participant operations)
- `user0_cert.pem` - User 0 certificate
- `user0_privk.pem` - User 0 private key
- `user1_cert.pem` - User 1 certificate
- `user1_privk.pem` - User 1 private key
- ... (and so on for additional users)

#### Member Certificates (for aggregation operations)
- `member0_cert.pem` - Member 0 certificate
- `member0_privk.pem` - Member 0 private key
- `member1_cert.pem` - Member 1 certificate
- `member1_privk.pem` - Member 1 private key
- ... (and so on for additional members)

## How It Works

### 1. Automatic Loading
- The application automatically scans the `workspace/sandbox_common/` folder on startup
- It looks for certificate files following the naming convention above
- Certificates are loaded automatically without any manual intervention

### 2. Certificate Service
- A `CertificateService` class manages all certificate operations
- It provides methods to get user and member certificates by ID
- It validates certificate availability before API calls

### 3. Frontend Integration
- The React frontend uses the certificate service instead of localStorage
- Users can select which certificate to use for operations
- No manual upload required - certificates are automatically available

## Usage

### Starting the Application

1. **Ensure certificates are in place:**
   ```bash
   # Check if certificates exist
   ls -la workspace/sandbox_common/
   
   # Should show files like:
   # user0_cert.pem
   # user0_privk.pem
   # member0_cert.pem
   # member0_privk.pem
   ```

2. **Start the frontend:**
   ```bash
   cd frontend
   npm start
   ```

3. **Access the certificate manager:**
   - Navigate to `http://localhost:3000/certificate-manager.html`
   - Or use the "CCF Auth" tab in the main application

### Certificate Manager Interface

The certificate manager shows:
- **User Certificates**: Number of available user certificates
- **Member Certificates**: Number of available member certificates
- **Status**: Green checkmarks for available certificates, red X for missing
- **Reload Button**: Manually reload certificates if needed

### Using Certificates in Operations

#### Upload Weights (User Certificate Required)
1. Navigate to "Upload Weights" tab
2. Select the user ID from the dropdown (corresponds to certificate ID)
3. Enter model ID, round number, and weights data
4. Submit - the system automatically uses the selected user's certificate

#### Trigger Aggregation (Member Certificate Required)
1. Navigate to "Aggregate" tab
2. Select the member ID from the dropdown (corresponds to certificate ID)
3. Enter model ID and round number
4. Submit - the system automatically uses the selected member's certificate

#### View Models (User Certificate Required)
1. Navigate to "View Models" tab
2. Select the user ID from the dropdown
3. Enter model ID and choose operation
4. Submit - the system automatically uses the selected user's certificate

## Troubleshooting

### No Certificates Found
If the application shows "No certificates found":

1. **Check certificate location:**
   ```bash
   ls -la workspace/sandbox_common/
   ```

2. **Verify naming convention:**
   - Certificates must be named exactly: `user0_cert.pem`, `user0_privk.pem`, etc.
   - File extensions must be `.pem`

3. **Check file permissions:**
   ```bash
   chmod 644 workspace/sandbox_common/*.pem
   ```

### Certificate Loading Errors
If certificates fail to load:

1. **Check browser console** for specific error messages
2. **Verify file format** - certificates should be in PEM format
3. **Try reloading** using the "Reload Certificates" button

### API Authentication Errors
If API calls fail with authentication errors:

1. **Ensure certificates exist** for the selected user/member ID
2. **Check certificate validity** - certificates should be valid PEM files
3. **Verify CCF backend** is running and accessible

## Development

### Adding New Certificates

To add new user or member certificates:

1. **Place certificate files** in `workspace/sandbox_common/`
2. **Follow naming convention**: `userX_cert.pem` and `userX_privk.pem`
3. **Restart the application** or use the reload button

### Certificate Service API

The certificate service provides these methods:

```javascript
import certificateService from './services/certificateService';

// Get certificate status
const status = certificateService.getCertificateStatus();

// Get user certificate
const userCert = certificateService.getUserCertificate(0); // user0

// Get member certificate
const memberCert = certificateService.getMemberCertificate(0); // member0

// Check availability
const hasUsers = certificateService.hasUserCertificates();
const hasMembers = certificateService.hasMemberCertificates();

// Reload certificates
await certificateService.reloadCertificates();
```

## Security Notes

- **Certificate files** should have appropriate permissions (644)
- **Private keys** should be kept secure and not shared
- **Certificate validation** happens automatically before API calls
- **No certificate data** is stored in browser localStorage anymore

## Migration from Manual Upload

If you were previously using manual certificate uploads:

1. **Remove old certificates** from localStorage (if any)
2. **Place certificates** in `workspace/sandbox_common/` folder
3. **Restart the application** - certificates will be loaded automatically
4. **Use the new interface** - no more manual uploads required

The new system is more secure and user-friendly, eliminating the need for manual certificate management through the frontend. 