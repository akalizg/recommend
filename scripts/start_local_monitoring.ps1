param(
    [string]$GrafanaHome = "D:\grafana\grafana-13.0.1+security-01",
    [string]$PrometheusExe = ""
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$RuntimeRoot = Join-Path $ProjectRoot ".monitor"
$PrometheusData = Join-Path $RuntimeRoot "prometheus-data"
$GrafanaData = Join-Path $RuntimeRoot "grafana-data"
$GrafanaLogs = Join-Path $RuntimeRoot "grafana-logs"
$GrafanaPlugins = Join-Path $RuntimeRoot "grafana-plugins"
$GrafanaConfig = Join-Path $RuntimeRoot "grafana.local.ini"
$LocalProvisioning = Join-Path $RuntimeRoot "grafana-provisioning"
$LocalDatasourceProvisioning = Join-Path $LocalProvisioning "datasources"
$LocalDashboardProvisioning = Join-Path $LocalProvisioning "dashboards"

New-Item -ItemType Directory -Force -Path $PrometheusData, $GrafanaData, $GrafanaLogs, $GrafanaPlugins, $LocalDatasourceProvisioning, $LocalDashboardProvisioning | Out-Null

$GrafanaExe = Join-Path $GrafanaHome "bin\grafana.exe"
if (-not (Test-Path -LiteralPath $GrafanaExe)) {
    throw "Grafana executable not found: $GrafanaExe"
}

Write-Host "[1/3] Checking FastAPI metrics endpoint..."
try {
    Invoke-WebRequest -Uri "http://127.0.0.1:8000/metrics" -UseBasicParsing -TimeoutSec 3 | Out-Null
    Write-Host "      FastAPI metrics OK: http://127.0.0.1:8000/metrics"
} catch {
    Write-Host "      [WARN] FastAPI metrics is not reachable yet. Start the backend first."
}

Write-Host "[2/3] Starting Prometheus if prometheus.exe is available..."
if (-not $PrometheusExe) {
    $cmd = Get-Command prometheus.exe -ErrorAction SilentlyContinue
    if ($cmd) {
        $PrometheusExe = $cmd.Source
    }
}

if ($PrometheusExe -and (Test-Path -LiteralPath $PrometheusExe)) {
    $prometheusConfig = Join-Path $ProjectRoot "config\prometheus.local.yml"
    $prometheusArgs = @(
        "--config.file=$prometheusConfig",
        "--storage.tsdb.path=$PrometheusData",
        "--web.listen-address=127.0.0.1:9090"
    )
    Start-Process -FilePath $PrometheusExe -ArgumentList $prometheusArgs -WorkingDirectory $ProjectRoot -WindowStyle Hidden
    Write-Host "      Prometheus: http://localhost:9090"
} else {
    Write-Host "      [WARN] prometheus.exe not found. Install Prometheus or pass -PrometheusExe <path>."
    Write-Host "      Grafana will start, but dashboards will have no data until Prometheus is running."
}

Write-Host "[3/3] Starting local Grafana..."
$env:PROMETHEUS_URL = "http://localhost:9090"
$dashboardPath = (Join-Path $ProjectRoot "config\grafana\dashboards").Replace("\", "/")
$provisioningPath = $LocalProvisioning.Replace("\", "/")
$dataPath = $GrafanaData.Replace("\", "/")
$logsPath = $GrafanaLogs.Replace("\", "/")
$pluginsPath = $GrafanaPlugins.Replace("\", "/")

@"
apiVersion: 1

datasources:
  - name: Prometheus
    uid: Prometheus
    type: prometheus
    access: proxy
    url: http://localhost:9090
    isDefault: true
    editable: true
"@ | Set-Content -LiteralPath (Join-Path $LocalDatasourceProvisioning "prometheus.yml") -Encoding UTF8

@"
apiVersion: 1

providers:
  - name: RecipeRec
    orgId: 1
    folder: RecipeRec
    type: file
    disableDeletion: false
    updateIntervalSeconds: 30
    allowUiUpdates: true
    options:
      path: $dashboardPath
"@ | Set-Content -LiteralPath (Join-Path $LocalDashboardProvisioning "dashboards.yml") -Encoding UTF8

@"
[paths]
data = $dataPath
logs = $logsPath
plugins = $pluginsPath
provisioning = $provisioningPath

[server]
http_addr = 127.0.0.1
http_port = 3001

[security]
admin_user = admin
admin_password = admin

[users]
allow_sign_up = false

[analytics]
reporting_enabled = false
check_for_updates = false
"@ | Set-Content -LiteralPath $GrafanaConfig -Encoding UTF8

Start-Process -FilePath $GrafanaExe -ArgumentList @("server", "--homepath=$GrafanaHome", "--config=$GrafanaConfig") -WorkingDirectory $GrafanaHome -WindowStyle Hidden

Write-Host ""
Write-Host "Local monitoring startup requested."
Write-Host "Grafana:    http://localhost:3001"
Write-Host "Prometheus: http://localhost:9090"
Write-Host "Login:      admin / admin"
