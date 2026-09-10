/**
 * ATBU E-Voting — WebAuthn Client (FIDO2 Device Fingerprint)
 * 
 * Handles browser-side WebAuthn credential registration and authentication
 * using the device's built-in fingerprint sensor or biometric hardware.
 * 
 * The biometric data (fingerprint image) NEVER leaves the device.
 * Only a cryptographic signature is sent to the server.
 */

class WebAuthnClient {
  constructor(options = {}) {
    this.csrfToken = options.csrfToken || this.getCookie('csrftoken');
    this.statusEl = document.getElementById('webauthn-status');
    this.scoreBarEl = document.getElementById('biometric-score-bar');
    this.scoreTextEl = document.getElementById('biometric-score-text');
    this.ensureValidDomain();
  }

  ensureValidDomain() {
    if (window.location.hostname === '127.0.0.1') {
      const port = window.location.port ? `:${window.location.port}` : '';
      const targetUrl = `${window.location.protocol}//localhost${port}${window.location.pathname}${window.location.search}${window.location.hash}`;
      console.warn("WebAuthn requires a domain name (localhost). Redirecting from 127.0.0.1 to " + targetUrl);
      window.location.replace(targetUrl);
      return false;
    }
    return true;
  }

  getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
      const cookies = document.cookie.split(';');
      for (let c of cookies) {
        c = c.trim();
        if (c.startsWith(name + '=')) {
          cookieValue = decodeURIComponent(c.substring(name.length + 1));
          break;
        }
      }
    }
    return cookieValue;
  }

  updateStatus(message, type = 'info') {
    if (!this.statusEl) return;
    this.statusEl.textContent = message;
    this.statusEl.className = `status-badge text-${type} fw-bold mt-3 d-inline-block`;
  }

  // Convert Base64URL string to ArrayBuffer
  base64urlToBuffer(base64url) {
    const padding = '='.repeat((4 - base64url.length % 4) % 4);
    const base64 = base64url.replace(/-/g, '+').replace(/_/g, '/') + padding;
    const binary = atob(base64);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i++) {
      bytes[i] = binary.charCodeAt(i);
    }
    return bytes.buffer;
  }

  // Convert ArrayBuffer to Base64URL string
  bufferToBase64url(buffer) {
    const bytes = new Uint8Array(buffer);
    let binary = '';
    for (let i = 0; i < bytes.length; i++) {
      binary += String.fromCharCode(bytes[i]);
    }
    return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=/g, '');
  }

  /**
   * REGISTRATION: Enroll the device's fingerprint sensor as a WebAuthn credential.
   * Called during voter registration or enrollment.
   */
  async registerDevice(deviceName = 'Personal Device') {
    this.updateStatus('Requesting registration options from server...', 'info');

    try {
      // 1. Get registration options from server
      const optionsResp = await fetch('/accounts/webauthn/register/options/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': this.csrfToken
        },
        body: JSON.stringify({ device_name: deviceName })
      });

      if (!optionsResp.ok) {
        const err = await optionsResp.json();
        throw new Error(err.message || 'Failed to get registration options');
      }

      const options = await optionsResp.json();

      // 2. Convert server options to WebAuthn API format
      const publicKeyOptions = {
        challenge: this.base64urlToBuffer(options.challenge),
        rp: {
          name: options.rp.name,
          id: options.rp.id
        },
        user: {
          id: this.base64urlToBuffer(options.user.id),
          name: options.user.name,
          displayName: options.user.displayName
        },
        pubKeyCredParams: options.pubKeyCredParams.map(p => ({
          type: p.type,
          alg: p.alg
        })),
        timeout: options.timeout || 60000,
        authenticatorSelection: {
          authenticatorAttachment: 'platform',  // Use device built-in sensor
          userVerification: 'required',         // Must verify with biometric
          residentKey: 'preferred'
        },
        attestation: 'none'
      };

      // Exclude already-registered credentials
      if (options.excludeCredentials && options.excludeCredentials.length > 0) {
        publicKeyOptions.excludeCredentials = options.excludeCredentials.map(c => ({
          type: 'public-key',
          id: this.base64urlToBuffer(c.id)
        }));
      }

      this.updateStatus('Touch your fingerprint sensor to register this device...', 'warning');

      // 3. Call browser WebAuthn API — triggers native fingerprint prompt
      const credential = await navigator.credentials.create({
        publicKey: publicKeyOptions
      });

      this.updateStatus('Fingerprint captured. Verifying with server...', 'info');

      // 4. Send attestation to server for verification
      const verifyResp = await fetch('/accounts/webauthn/register/verify/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': this.csrfToken
        },
        body: JSON.stringify({
          credential_id: this.bufferToBase64url(credential.rawId),
          client_data: this.bufferToBase64url(credential.response.clientDataJSON),
          attestation_object: this.bufferToBase64url(credential.response.attestationObject),
          device_name: deviceName
        })
      });

      const result = await verifyResp.json();

      if (verifyResp.ok && result.success) {
        this.updateStatus('Device fingerprint enrolled successfully!', 'success');
        return { success: true, message: result.message };
      } else {
        throw new Error(result.message || 'Registration verification failed');
      }
    } catch (error) {
      if (error.name === 'NotAllowedError') {
        this.updateStatus('Fingerprint scan was cancelled or timed out. Please try again.', 'danger');
      } else if (error.name === 'InvalidStateError') {
        this.updateStatus('This device is already registered.', 'warning');
      } else if (error.name === 'NotSupportedError') {
        this.updateStatus('Your device does not support fingerprint authentication.', 'danger');
      } else if (error.name === 'SecurityError' || (error.message && error.message.toLowerCase().includes('domain'))) {
        this.updateStatus('WebAuthn requires http://localhost:8000. Redirecting...', 'warning');
        this.ensureValidDomain();
      } else {
        this.updateStatus('Error: ' + error.message, 'danger');
      }
      console.error('WebAuthn registration error:', error);
      return { success: false, message: error.message };
    }
  }

  /**
   * AUTHENTICATION: Verify identity using the device's fingerprint sensor.
   * Called during login Step 3.
   */
  async authenticate() {
    this.updateStatus('Requesting authentication challenge from server...', 'info');

    try {
      // 1. Get authentication options from server
      const optionsResp = await fetch('/accounts/webauthn/auth/options/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': this.csrfToken
        }
      });

      if (!optionsResp.ok) {
        const err = await optionsResp.json();
        throw new Error(err.message || 'Failed to get authentication options');
      }

      const options = await optionsResp.json();

      // 2. Convert server options to WebAuthn API format
      const publicKeyOptions = {
        challenge: this.base64urlToBuffer(options.challenge),
        rpId: options.rpId,
        timeout: options.timeout || 60000,
        userVerification: 'required'
      };

      // Include allowed credentials
      if (options.allowCredentials && options.allowCredentials.length > 0) {
        publicKeyOptions.allowCredentials = options.allowCredentials.map(c => ({
          type: 'public-key',
          id: this.base64urlToBuffer(c.id),
          transports: ['internal']  // Platform authenticator
        }));
      }

      this.updateStatus('Touch your fingerprint sensor to verify your identity...', 'warning');

      if (this.scoreBarEl) {
        this.scoreBarEl.style.width = '30%';
        this.scoreBarEl.className = 'progress-bar bg-warning progress-bar-animated';
      }

      // 3. Call browser WebAuthn API — triggers native fingerprint prompt
      const assertion = await navigator.credentials.get({
        publicKey: publicKeyOptions
      });

      this.updateStatus('Fingerprint verified locally. Confirming with server...', 'info');

      if (this.scoreBarEl) {
        this.scoreBarEl.style.width = '65%';
      }

      // 4. Send assertion to server for cryptographic verification
      const verifyResp = await fetch('/accounts/webauthn/auth/verify/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': this.csrfToken
        },
        body: JSON.stringify({
          credential_id: this.bufferToBase64url(assertion.rawId),
          client_data: this.bufferToBase64url(assertion.response.clientDataJSON),
          authenticator_data: this.bufferToBase64url(assertion.response.authenticatorData),
          signature: this.bufferToBase64url(assertion.response.signature)
        })
      });

      const result = await verifyResp.json();

      if (verifyResp.ok && result.success) {
        this.updateStatus('Identity verified! Redirecting to voting dashboard...', 'success');
        if (this.scoreBarEl) {
          this.scoreBarEl.style.width = '100%';
          this.scoreBarEl.className = 'progress-bar bg-success';
        }
        if (this.scoreTextEl) {
          this.scoreTextEl.textContent = 'Verified (FIDO2 Signature Valid)';
        }

        setTimeout(() => {
          window.location.href = result.redirect_url || '/elections/dashboard/';
        }, 1000);

        return { success: true };
      } else {
        throw new Error(result.message || 'Authentication failed');
      }
    } catch (error) {
      if (error.name === 'NotAllowedError') {
        this.updateStatus('Fingerprint scan was cancelled or timed out. Please try again.', 'danger');
      } else if (error.name === 'SecurityError' || (error.message && error.message.toLowerCase().includes('domain'))) {
        this.updateStatus('WebAuthn requires http://localhost:8000. Redirecting...', 'warning');
        this.ensureValidDomain();
      } else {
        this.updateStatus('Verification failed: ' + error.message, 'danger');
      }
      if (this.scoreBarEl) {
        this.scoreBarEl.style.width = '15%';
        this.scoreBarEl.className = 'progress-bar bg-danger';
      }
      if (this.scoreTextEl) {
        this.scoreTextEl.textContent = 'Failed';
      }
      console.error('WebAuthn authentication error:', error);
      return { success: false, message: error.message };
    }
  }

  /**
   * Check if WebAuthn is supported by the current browser and device.
   */
  static isSupported() {
    return window.PublicKeyCredential !== undefined &&
           typeof navigator.credentials !== 'undefined';
  }

  /**
   * Check if the device has a platform authenticator (built-in fingerprint sensor).
   */
  static async isPlatformAuthenticatorAvailable() {
    if (!WebAuthnClient.isSupported()) return false;
    try {
      return await PublicKeyCredential.isUserVerifyingPlatformAuthenticatorAvailable();
    } catch {
      return false;
    }
  }
}

// Export for use in templates
window.WebAuthnClient = WebAuthnClient;
