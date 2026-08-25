# Start Mehengaai Mitra from this folder in Windows PowerShell.
$projectPath = $PSScriptRoot
$pythonLauncher = Get-Command py -ErrorAction SilentlyContinue
$bundledPython = "C:\Users\Tanishka Jha\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"

if (Test-Path -LiteralPath $bundledPython) {
    $pythonCommand = $bundledPython
} elseif ($null -ne $pythonLauncher) {
    $pythonCommand = "py"
} else {
    Write-Host "Python was not found. Install Python 3.11+ from python.org, then run this script again." -ForegroundColor Yellow
    exit 1
}

Set-Location -LiteralPath $projectPath
& $pythonCommand -m pip install -r requirements.txt --user
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $pythonCommand -m streamlit run app.py
