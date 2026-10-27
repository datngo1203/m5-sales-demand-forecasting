$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$compose = @('compose', '-f', 'infra/hdfs/compose.yaml')
$python = Join-Path $PSScriptRoot '.venv/Scripts/python.exe'
if (-not (Test-Path $python)) { throw 'Tao .venv theo README truoc.' }
New-Item -ItemType Directory -Force outputs/analysis_hdfs | Out-Null
& docker @compose up -d --wait namenode datanode
if ($LASTEXITCODE -ne 0) { throw 'HDFS chua san sang. Xem docker compose logs.' }
& docker @compose exec -T namenode bash /m5-scripts/upload.sh 2>&1 | Tee-Object outputs/analysis_hdfs/hdfs_storage.log
if ($LASTEXITCODE -ne 0) { throw 'Nap/doi chieu du lieu HDFS that bai; khong ghi de file cu.' }
& docker @compose run --rm spark 2>&1 | Tee-Object outputs/analysis_hdfs/spark.log
if ($LASTEXITCODE -ne 0) { throw 'Spark doc HDFS that bai.' }
& $python scripts/verify_hdfs.py
if ($LASTEXITCODE -ne 0) { throw 'Ket qua HDFS khong khop local.' }
Write-Output 'HDFS da doi chieu. NameNode: http://127.0.0.1:9870 ; ket qua: outputs/analysis_hdfs'
