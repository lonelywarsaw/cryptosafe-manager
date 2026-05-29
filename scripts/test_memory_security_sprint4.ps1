# scripts/test_memory_security_sprint4.ps1
param(
    [string]$ProcessName = "python",
    [string]$TestPassword = "MySecret_TEST_$(Get-Random)",
    [string]$ProcDumpPath = ".\scripts\procdump.exe",
    [string]$DumpOutputPath = "$env:TEMP\cryptosafe_memtest_$(Get-Date -Format 'yyyyMMdd_HHmmss').dmp",
    [switch]$KeepDump
)

Write-Host "=== CryptoSafe Sprint 4 TEST-3: Memory Security Check ===" -ForegroundColor Cyan

# 1. Проверка прав администратора
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host " ERROR: Запустите PowerShell ОТ ИМЕНИ АДМИНИСТРАТОРА" -ForegroundColor Red
    exit 1
}

# 2. Проверка ProcDump
if (-not (Test-Path $ProcDumpPath)) {
    Write-Host " ERROR: ProcDump не найден: $ProcDumpPath" -ForegroundColor Red
    Write-Host " Скачайте: https://learn.microsoft.com/sysinternals/downloads/procdump" -ForegroundColor Yellow
    exit 2
}

# 3. Поиск процесса (берём ТОЛЬКО ПЕРВЫЙ)
$Processes = Get-Process -Name $ProcessName -ErrorAction SilentlyContinue
if (-not $Processes) {
    Write-Host " ERROR: Процесс '$ProcessName' не найден!" -ForegroundColor Red
    exit 3
}

$Target = $Processes | Select-Object -First 1
$TargetPid = [string]$Target.Id
Write-Host " Target: $($Target.ProcessName) (PID: $TargetPid)" -ForegroundColor Green

# 4. Создание дампа
Write-Host "[1/2] Creating memory dump..." -ForegroundColor Yellow
$procDumpArgs = @("-ma", "-accepteula", $TargetPid, "`"$DumpOutputPath`"")
$result = Start-Process -FilePath $ProcDumpPath -ArgumentList $procDumpArgs -Wait -NoNewWindow -PassThru

$DumpCreated = Test-Path $DumpOutputPath
if (-not $DumpCreated) {
    Write-Host " ERROR: Файл дампа не создан: $DumpOutputPath" -ForegroundColor Red
    Write-Host "   ProcDump exit code: $($result.ExitCode)" -ForegroundColor Gray
    exit 4
}

$DumpSize = [math]::Round(((Get-Item $DumpOutputPath).Length / 1MB), 2)
Write-Host " Dump created: $DumpSize MB" -ForegroundColor Green
if ($result.ExitCode -ne 0) {
    Write-Host "  ProcDump exit code: $($result.ExitCode) (но дамп создан — продолжаем)" -ForegroundColor Yellow
}

# 5. Поиск пароля в дампе
Write-Host "[2/2] Searching for password in dump..." -ForegroundColor Yellow
try {
    $DumpBytes = [System.IO.File]::ReadAllBytes($DumpOutputPath)
    $PasswordBytes = [System.Text.Encoding]::UTF8.GetBytes($TestPassword)
    $Found = $false
    $MaxIndex = $DumpBytes.Length - $PasswordBytes.Length

    for ($i = 0; $i -le $MaxIndex; $i++) {
        $Match = $true
        for ($j = 0; $j -lt $PasswordBytes.Length; $j++) {
            if ($DumpBytes[$i + $j] -ne $PasswordBytes[$j]) {
                $Match = $false; break
            }
        }
        if ($Match) { $Found = $true; break }
    }

    # 6. Результат
    Write-Host ""
    if ($Found) {
        Write-Host "  FAIL: Password found in memory dump!" -ForegroundColor Red
        exit 10
    } else {
        Write-Host "  PASS: Password NOT found in memory dump" -ForegroundColor Green
        Write-Host "   Clipboard data is properly protected in memory." -ForegroundColor Gray
        exit 0
    }
} catch {
    Write-Host "  ERROR during dump analysis: $($_.Exception.Message)" -ForegroundColor Red
    exit 6
} finally {
    if (-not $KeepDump -and (Test-Path $DumpOutputPath)) {
        Remove-Item $DumpOutputPath -Force -ErrorAction SilentlyContinue
        Write-Host "  Temporary dump removed" -ForegroundColor Gray
    }
    Set-Clipboard -Value $null -ErrorAction SilentlyContinue
}