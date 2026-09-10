Build a web-based university election system in Python (Django) that enforces 
three-factor authentication — password, then OTP, then fingerprint biometric — 
before any voter can cast a ballot. Voting happens at a supervised polling 
terminal, not remotely.

TECHNICAL REQUIREMENTS / LANGUAGE STACK:
- Language: Python 3
- Web framework: Django (main app) + Flask (lightweight local capture agent)
- Frontend: HTML5, CSS3, JavaScript, Bootstrap
- Database: PostgreSQL or MySQL (production); SQLite (local dev only — not 
  production, due to single-writer concurrency limits)
- Password hashing: Django's built-in auth (PBKDF2) or bcrypt
- OTP: pyotp (RFC 6238 time-based one-time password)
- Biometric matching: SourceAFIS (software-only fingerprint minutiae 
  extraction/matching — no vendor SDK dependency)
- Image preprocessing: OpenCV (opencv-python)
- Encryption: pycryptodome (AES, for fingerprint templates at rest — 
  reversible, unlike password hashing, since matching requires decryption)
- Transport/session security: TLS/HTTPS, Django CSRF protection, session 
  management
- Testing: PyTest / Django test framework; Postman for manual API checks; 
  Locust (or a simple concurrent script) for throughput/load testing
- Diagramming (design stage): draw.io
- Version control: Git & GitHub

ROLES (RBAC): System Administrator, Electoral Officer, Candidate, Voter.

AUTHENTICATION (sequential, session-guarded — each stage must pass before the 
next unlocks; any failure or an already-voted check routes to a shared 
access-denied path with retry limits):
1. Password — Django's built-in hashed auth.
2. OTP — pyotp, RFC 6238 time-based one-time password.
3. Biometric — SourceAFIS. Since browsers can't access USB scanners directly, 
   build a small local Flask "capture agent" on the polling terminal that 
   captures the fingerprint, extracts the template, and talks to the Django 
   backend over HTTPS. Never send raw fingerprint images to the server — only 
   the extracted template. Encrypt stored templates with AES (pycryptodome); 
   passwords are hashed, templates are encrypted.

ARCHITECTURE: three-tier — (1) presentation: HTML5/CSS3/JS/Bootstrap at the 
terminal; (2) application: Django, organized into apps for accounts/roles, 
elections, biometrics, and audit logging; (3) data: PostgreSQL/MySQL.

DATA MODEL (minimum): User/Role, Voter, FingerprintTemplate (encrypted), 
OTPSecret, Election, Position, Candidate, Ballot, HasVoted, AuditLog 
(hash-chained: each entry hashes the previous one, append-only, tamper-evident).

BUILD ORDER (iterative, one increment at a time — test each before adding 
the next):
1. User/role models + election/position/candidate/ballot data models
2. Password auth stage
3. Hash-chained audit log (wire in from this point forward)
4. OTP stage (only runs after password succeeds in-session)
5. Standalone fingerprint capture agent + SourceAFIS matching (build/test 
   in isolation first)
6. Wire biometric stage into the auth flow
7. Ballot casting + one-vote enforcement + tallying + results (only 
   reachable after all three factors pass)

EVALUATE: False Acceptance Rate / False Rejection Rate at several similarity 
thresholds, per-stage and total authentication latency, throughput under 
concurrent load, and resistance to double-voting/impersonation — benchmarked 
against a password-only baseline.

DELIVERABLES: full Django project with migrations, seed data, the capture 
agent as a separate runnable service, a test suite (unit + integration + 
security, including deliberate stage-skipping and double-vote attempts), 
and a README covering setup, environment variables (DB, encryption keys, 
OTP config), and how to run the agent alongside Django.