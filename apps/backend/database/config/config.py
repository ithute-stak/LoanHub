from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL, make_url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
        case_sensitive=True,
        extra='ignore',
    )

    ENVIRONMENT: str = 'development'
    EXPOSE_ERROR_DETAILS: bool = False
    APP_TIMEZONE: str = 'Africa/Maseru'
    PUBLIC_APP_URL: str = 'http://localhost:3000'

    # Public sandbox controls. These settings are inert unless SANDBOX_MODE is
    # explicitly enabled on the isolated sandbox backend service.
    SANDBOX_MODE: bool = False
    SANDBOX_ROLE_SWITCH_ENABLED: bool = False
    SANDBOX_LOGIN_PHONE: str = '12345678'
    SANDBOX_LOGIN_PASSWORD: str = '1234567890'

    DATABASE_URL: Optional[str] = None
    DB_HOST: str = 'localhost'
    DB_PORT: int = 5432
    DB_USER: str = 'postgres'
    DB_PASSWORD: str = 'postgres'
    DB_NAME: str = 'loan_db'

    CORS_ORIGINS: str = 'http://localhost:3000'

    JWT_PRIVATE_KEY: Optional[str] = None
    JWT_PUBLIC_KEY: Optional[str] = None
    JWT_PRIVATE_KEY_PATH: Optional[str] = None
    JWT_PUBLIC_KEY_PATH: Optional[str] = None

    SECRET_KEY: str
    FERNET_SECRET_KEY: str
    CHAT_ENCRYPTION_KEY: Optional[str] = None
    FILE_ENCRYPTION_KEY: Optional[str] = None
    FILE_ENCRYPTION_ENABLED: bool = True
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    RATE_LIMIT: str = '100/minute'
    AUTH_RATE_LIMIT: str = '10/minute'
    AUTH_LOCKOUT_MAX_ATTEMPTS: int = 5
    AUTH_LOCKOUT_MINUTES: int = 15
    RATE_LIMIT_ENABLED: bool = True
    ALGORITHM: str = 'RS256'

    ENABLE_ROLE_IMPERSONATION: bool = False
    IMPERSONATION_MAX_MINUTES: int = 30

    MARKETPLACE_DEFAULT_UNLOCK_FEE: float = 25.0

    # Compatibility cache only. LelefaPayGate operational configuration is
    # loaded from PostgreSQL for each request and environment values are reset
    # immediately after Settings is constructed.
    LELEFAPAYGATE_ENABLED: bool = False
    LELEFAPAYGATE_BASE_URL: str = 'http://169.255.58.185:8081/api/v1'
    LELEFAPAYGATE_API_KEY: Optional[str] = None
    LELEFAPAYGATE_WEBHOOK_SECRET: Optional[str] = None
    LELEFAPAYGATE_REQUEST_SIGNING_ENABLED: bool = True
    LELEFAPAYGATE_TIMEOUT_SECONDS: float = 15.0
    LELEFAPAYGATE_WEBHOOK_TOLERANCE_SECONDS: int = 300
    LELEFAPAYGATE_COLLECTION_PROVIDER: str = 'mpesa'
    LELEFAPAYGATE_PAYOUT_PROVIDER: str = 'mpesa'

    WEBHOOK_DELIVERY_TIMEOUT_SECONDS: float = 10.0
    WEBHOOK_DELIVERY_MAX_ATTEMPTS: int = 8
    WEBHOOK_DELIVERY_BATCH_SIZE: int = 50

    MAINTENANCE_INTERVAL_SECONDS: int = 300
    MIDNIGHT_REPORTS_ENABLED: bool = True
    MIDNIGHT_REPORT_FORMATS: str = 'pdf,csv'

    # Collections report generated at/after 00:30 in APP_TIMEZONE.
    COLLECTION_DAILY_REPORT_ENABLED: bool = True
    COLLECTION_DAILY_REPORT_HOUR: int = 0
    COLLECTION_DAILY_REPORT_MINUTE: int = 30

    TREASURY_AUTO_SUBMIT_ENABLED: bool = True
    TREASURY_AUTO_SUBMIT_INTERVAL_SECONDS: int = 60

    REDIS_URL: Optional[str] = None
    REDIS_REALTIME_CHANNEL: str = 'loanhub:realtime'
    HTTP_CACHE_ENABLED: bool = True
    HTTP_CACHE_NAMESPACE: str = 'loanhub:http-cache:v1'
    HTTP_CACHE_DEFAULT_TTL_SECONDS: int = 30
    HTTP_CACHE_MAX_BODY_BYTES: int = 2 * 1024 * 1024

    FILE_STORAGE_PATH: str = 'storage/uploads'
    FILE_STORAGE_BACKEND: str = 'local'
    S3_ENDPOINT_URL: Optional[str] = None
    S3_BUCKET: Optional[str] = None
    S3_REGION: str = 'us-east-1'
    S3_ACCESS_KEY_ID: Optional[str] = None
    S3_SECRET_ACCESS_KEY: Optional[str] = None
    S3_PREFIX: str = 'loanhub'
    S3_ADDRESSING_STYLE: str = 'path'
    MALWARE_SCAN_ENABLED: bool = False
    MALWARE_SCAN_FAIL_CLOSED: bool = True
    CLAMAV_HOST: str = 'clamav'
    CLAMAV_PORT: int = 3310
    CLAMAV_TIMEOUT_SECONDS: float = 5.0
    FILE_MAX_UPLOAD_MB: int = 25
    FILE_AUDIO_MAX_UPLOAD_MB: int = 20
    FILE_RETENTION_DAYS: int = 3650

    # Controlled company calling. Keep disabled until a LiveKit/WebRTC/SIP
    # deployment has been provisioned. Secrets are supplied only at runtime.
    CALL_MEDIA_PROVIDER: str = 'disabled'
    LIVEKIT_URL: Optional[str] = None
    LIVEKIT_API_KEY: Optional[str] = None
    LIVEKIT_API_SECRET: Optional[str] = None
    CALL_TOKEN_TTL_SECONDS: int = 300

    METRICS_ENABLED: bool = True
    SENTRY_DSN: Optional[str] = None
    SENTRY_TRACES_SAMPLE_RATE: float = 0.0

    PRODUCT_NAME: str = 'LoanHub'
    DEVELOPER_NAME: str = 'Ithute Solutions'
    LOANHUB_LOGO_PATH: str = 'assets/loanhub-horizontal-logo.png'
    LOANHUB_APP_ICON_PATH: str = 'assets/loanhub-app-icon.png'
    DEVELOPER_LOGO_PATH: str = 'assets/ithute-solutions-developer-logo.png'
    # Backward-compatible alias used by older report code.
    BRAND_NAME: str = 'Ithute Solutions'
    BRAND_LOGO_PATH: str = 'assets/ithute-solutions-developer-logo.png'

    @property
    def database_url(self) -> str:
        if self.DATABASE_URL:
            url = make_url(self.DATABASE_URL)
            if url.drivername in {'postgres', 'postgresql'}:
                url = url.set(drivername='postgresql+psycopg2')
            return url.render_as_string(hide_password=False)

        url = URL.create(
            drivername='postgresql+psycopg2',
            username=self.DB_USER,
            password=self.DB_PASSWORD,
            host=self.DB_HOST,
            port=self.DB_PORT,
            database=self.DB_NAME,
        )
        return url.render_as_string(hide_password=False)

    @property
    def cors_origins(self) -> list[str]:
        return [
            origin.strip()
            for origin in self.CORS_ORIGINS.split(',')
            if origin.strip()
        ]

    @property
    def midnight_report_formats(self) -> tuple[str, ...]:
        allowed = {'pdf', 'csv'}
        values = tuple(
            value.strip().lower()
            for value in self.MIDNIGHT_REPORT_FORMATS.split(',')
            if value.strip().lower() in allowed
        )
        return values or ('pdf',)


settings = Settings()

# LelefaPayGate is intentionally database-owned. Ignore any legacy environment
# values that may still exist on a server until the first database sync runs.
settings.LELEFAPAYGATE_ENABLED = False
settings.LELEFAPAYGATE_BASE_URL = 'http://169.255.58.185:8081/api/v1'
settings.LELEFAPAYGATE_API_KEY = None
settings.LELEFAPAYGATE_WEBHOOK_SECRET = None
settings.LELEFAPAYGATE_REQUEST_SIGNING_ENABLED = True
settings.LELEFAPAYGATE_TIMEOUT_SECONDS = 15.0
settings.LELEFAPAYGATE_WEBHOOK_TOLERANCE_SECONDS = 300
settings.LELEFAPAYGATE_COLLECTION_PROVIDER = 'mpesa'
settings.LELEFAPAYGATE_PAYOUT_PROVIDER = 'mpesa'
