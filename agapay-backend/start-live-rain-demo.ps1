param(
    [string]$BrokerHost = '127.0.0.1',
    [int]$BrokerPort = 1884,
    [int]$ApiPort = 8000,
    [switch]$AllowSimulator,
    [switch]$PromptCredential,
    [switch]$CheckOnly
)
$ErrorActionPreference = 'Stop'
$DemoDataPath = Join-Path (Split-Path -Parent $PSScriptRoot) 'data/live_rain'
New-Item -ItemType Directory -Path $DemoDataPath -Force | Out-Null
$DemoApiDatabase = Join-Path $DemoDataPath 'demo-api.sqlite3'
$DemoRainJournal = Join-Path $DemoDataPath 'rain-events.sqlite3'
$DemoPython = Join-Path $PSScriptRoot '.venv-auth/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $DemoPython)) { throw 'Set up the backend Python environment first.' }
$DemoCredentialPath = Join-Path $DemoDataPath 'broker/backend-demo.credential.xml'
if (-not $PromptCredential -and (Test-Path -LiteralPath $DemoCredentialPath)) {
    $DemoCredential = Import-Clixml -LiteralPath $DemoCredentialPath
    if ($DemoCredential -isnot [System.Management.Automation.PSCredential] -or $DemoCredential.UserName -ne 'backend-demo') {
        throw 'The saved local MQTT credential is invalid. Use -PromptCredential to enter the existing backend-demo login.'
    }
    Write-Host 'Using the existing MQTT login encrypted for this Windows account.'
} else {
    $DemoCredential = Get-Credential -UserName 'backend-demo' -Message 'Local MQTT backend account; no credentials are printed or written to project files.'
}
if ($null -eq $DemoCredential) { throw 'MQTT credentials are required for the authenticated broker.' }
$DemoEnvironmentNames = @('ENVIRONMENT','DATABASE_URL','NOTIFICATION_PROVIDER','MQTT_ENABLED','MQTT_HOST','MQTT_PORT','MQTT_TLS','MQTT_USERNAME','MQTT_PASSWORD','MQTT_CLIENT_ID','RAIN_GAUGE_ENABLED','RAIN_GAUGE_STORE_PATH','RAIN_GAUGE_CALIBRATIONS','RAIN_GAUGE_ALLOW_SIMULATOR','TELEMETRY_STALE_AFTER_SECONDS','LOCAL_ADMIN_SETUP_ENABLED')
$DemoSavedEnvironment = @{}
foreach ($DemoName in $DemoEnvironmentNames) {
    $DemoFullName = 'AGAPAY_' + $DemoName
    $DemoSavedEnvironment[$DemoFullName] = [Environment]::GetEnvironmentVariable($DemoFullName, 'Process')
}
$env:AGAPAY_ENVIRONMENT = 'development'
$env:AGAPAY_DATABASE_URL = 'sqlite:///' + $DemoApiDatabase.Replace('\','/')
$env:AGAPAY_NOTIFICATION_PROVIDER = 'disabled'
$env:AGAPAY_MQTT_ENABLED = 'true'
$env:AGAPAY_MQTT_HOST = $BrokerHost
$env:AGAPAY_MQTT_PORT = [string]$BrokerPort
$env:AGAPAY_MQTT_TLS = 'false'
$env:AGAPAY_MQTT_USERNAME = $DemoCredential.UserName
$env:AGAPAY_MQTT_PASSWORD = $DemoCredential.GetNetworkCredential().Password
$env:AGAPAY_MQTT_CLIENT_ID = 'agapay-live-rain-demo'
$env:AGAPAY_RAIN_GAUGE_ENABLED = 'true'
$env:AGAPAY_RAIN_GAUGE_STORE_PATH = $DemoRainJournal
$env:AGAPAY_RAIN_GAUGE_CALIBRATIONS = '{"STATION_001":0.70}'
$env:AGAPAY_RAIN_GAUGE_ALLOW_SIMULATOR = if ($AllowSimulator) { 'true' } else { 'false' }
$env:AGAPAY_TELEMETRY_STALE_AFTER_SECONDS = '30'
$env:AGAPAY_LOCAL_ADMIN_SETUP_ENABLED = 'true'
Push-Location -LiteralPath $PSScriptRoot
try {
    if ($CheckOnly) {
        & $DemoPython -c "from app.config import Settings; from app.services.hybrid_projection import get_engine; s=Settings(); assert s.environment=='development' and s.rain_gauge_enabled and s.hybrid_projection_enabled and s.notification_provider=='disabled'; get_engine(s.hybrid_model_directory,s.hybrid_dataset_path); print('PASS: encrypted login loaded; demo settings and model/dataset provenance verified. No server started.')"
        if ($LASTEXITCODE -ne 0) { throw 'Demo restart configuration check failed.' }
        return
    }
    Write-Host 'Starting isolated live-rain demonstration API. FCM disabled; no existing development database is used.'
    & $DemoPython -m uvicorn app.main:app --host 127.0.0.1 --port $ApiPort
} finally {
    foreach ($DemoFullName in $DemoSavedEnvironment.Keys) {
        [Environment]::SetEnvironmentVariable($DemoFullName, $DemoSavedEnvironment[$DemoFullName], 'Process')
    }
    Pop-Location
}
