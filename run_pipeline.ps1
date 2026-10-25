param([switch]$SkipInstall)
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$python = Join-Path $PSScriptRoot '.venv/Scripts/python.exe'
if (-not (Test-Path $python)) { throw 'Tao .venv Python 3.11 theo README truoc.' }
if (-not $env:JAVA_HOME) {
    $jdk = Get-ChildItem (Join-Path $PSScriptRoot '.runtime') -Directory -Filter 'jdk-17*' -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $jdk) { throw 'Thiet lap JAVA_HOME cho JDK 17 theo README.' }
    $env:JAVA_HOME = $jdk.FullName
}
$env:PATH = "$env:JAVA_HOME/bin;$env:PATH"
$env:SPARK_LOCAL_IP = '127.0.0.1'
$env:PYSPARK_PYTHON = $python
New-Item -ItemType Directory -Force outputs | Out-Null
if (-not $SkipInstall) {
    & $python -m pip install -r requirements-dashboard.txt
    if ($LASTEXITCODE -ne 0) { throw 'Cai phu thuoc that bai.' }
}
& $python -m pip check 2>&1 | Tee-Object -FilePath outputs/pipeline_dependencies.log
if ($LASTEXITCODE -ne 0) { throw 'Phu thuoc khong tuong thich. Xem outputs/pipeline_dependencies.log.' }
foreach ($script in @('11_inspect_input.py', '12_spark_analysis.py', '13_forecasting.py')) {
    & $python (Join-Path 'code' $script) 2>&1 | Tee-Object -FilePath "outputs/pipeline_$script.log"
    if ($LASTEXITCODE -ne 0) { throw "Buoc $script that bai. Xem log trong outputs." }
}
& $python -m unittest discover -s tests -v 2>&1 | Tee-Object -FilePath outputs/pipeline_tests.log
if ($LASTEXITCODE -ne 0) { throw 'Kiem tra that bai. Xem outputs/pipeline_tests.log.' }
Write-Output 'Thanh cong. Mo demo: .\.venv\Scripts\python.exe -m streamlit run code\14_dashboard.py'
