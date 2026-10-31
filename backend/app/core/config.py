from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import model_validator

class Settings(BaseSettings):
    app_name: str = "Unique Solutions and Setu Kendra API"
    app_env: str = "development"
    api_v1_prefix: str = "/api/v1"
    mongodb_uri: str = ""
    mongodb_database: str = "unique_solutions_db"
    frontend_origins: str = "http://localhost:5173"
    jwt_secret_key: str = ""
    access_token_expire_minutes: int = 20
    refresh_token_expire_days: int = 7
    cookie_secure: bool = False
    cookie_samesite: str = "lax"
    login_attempts_per_minute: int = 5
    storage_provider: str = "local"
    storage_bucket: str = ""
    storage_region: str = ""
    storage_endpoint: str = ""
    storage_access_key_id: str = ""
    storage_secret_access_key: str = ""
    local_storage_dir: str = "./private_uploads"
    cloudinary_cloud_name: str = ""
    cloudinary_api_key: str = ""
    cloudinary_api_secret: str = ""
    max_upload_size_mb: int = 10
    log_level: str = "INFO"
    rate_limit_per_minute: int = 60
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    @property
    def cors_origins(self) -> list[str]:
        return [x.strip() for x in self.frontend_origins.split(",") if x.strip()]

    @model_validator(mode="after")
    def validate_security_settings(self):
        provider = self.storage_provider.lower()
        if provider not in ("local", "s3", "cloudinary"):
            raise ValueError("STORAGE_PROVIDER must be 'local', 's3', or 'cloudinary'")
        if len(self.jwt_secret_key.strip()) < 32 or self.jwt_secret_key.strip().lower().startswith(("replace-", "change-me", "your-secret")):
            raise ValueError("JWT_SECRET_KEY must be at least 32 characters")
        if self.cookie_samesite.lower() not in ("lax", "strict", "none"):
            raise ValueError("COOKIE_SAMESITE must be Lax, Strict, or None")
        if self.cookie_samesite.lower() == "none" and not self.cookie_secure:
            raise ValueError("COOKIE_SECURE must be true when COOKIE_SAMESITE is None")
        if provider == "cloudinary" and not all((
            self.cloudinary_cloud_name.strip(),
            self.cloudinary_api_key.strip(),
            self.cloudinary_api_secret.strip(),
        )):
            raise ValueError(
                "CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, and CLOUDINARY_API_SECRET "
                "are required when STORAGE_PROVIDER=cloudinary"
            )
        if self.app_env.lower() == "production":
            if not self.mongodb_uri:
                raise RuntimeError("MONGODB_URI is required in production")
            if not self.cookie_secure:
                raise RuntimeError("COOKIE_SECURE must be true in production")
            if not self.cors_origins or "*" in self.cors_origins:
                raise RuntimeError("Production CORS_ORIGINS must list exact frontend origins")
            if provider == "s3" and not self.storage_bucket:
                raise RuntimeError("Production S3 storage requires STORAGE_BUCKET")
            if provider == "local":
                raise RuntimeError("Production requires private S3-compatible or Cloudinary storage")
            if provider == "s3" and bool(self.storage_access_key_id) != bool(self.storage_secret_access_key):
                raise RuntimeError("Configure both storage credentials or use the host's IAM role")
        return self

@lru_cache
def get_settings() -> Settings:
    return Settings()

settings = get_settings()
