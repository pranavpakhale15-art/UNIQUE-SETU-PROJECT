import os
os.environ.setdefault("APP_ENV","test")
os.environ.setdefault("JWT_SECRET_KEY","test-secret-key-that-is-long-enough-for-tests")
os.environ.setdefault("MONGODB_URI","mongodb://localhost:27017")
