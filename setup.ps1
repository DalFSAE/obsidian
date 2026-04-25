# DalFSAE Setup Script
# Sets up C:\DalFSAE\ with all team repos and configures Obsidian.
# Run this once after cloning docs for the first time.
#
# Usage (from PowerShell as your normal user - no admin needed):
#   cd C:\DalFSAE\docs
#   .\setup.ps1

$BASE = "C:\DalFSAE"

# Repo list - add any which should be cloned to the base directory here. 
# The script will skip any that are already cloned, so it's safe to add more later and re-run.
# Each entry: Name (display), Url (HTTPS), Path (where to clone)
# vehicles MUST stay at $BASE\vehicles - SolidWorks uses absolute paths internally
$repos = @(
    [pscustomobject]@{ Name = "docs"; Url = "https://github.com/DalFSAE/docs.git"; Path = "$BASE\docs" },
    [pscustomobject]@{ Name = "vehicles"; Url = "https://github.com/DalFSAE/vehicles.git"; Path = "$BASE\vehicles" },
    [pscustomobject]@{ Name = "project-management"; Url = "https://github.com/DalFSAE/project-management.git"; Path = "$BASE\project-management" }
)

Write-Host "DalFSAE Setup"
Write-Host ""

# Find git
# GitHub Desktop ships a bundled git that may not be on PATH.
$git = Get-Command git -ErrorAction SilentlyContinue

if (-not $git) {
    $bundled = Get-Item "$env:LOCALAPPDATA\GitHubDesktop\app-*\resources\app\git\cmd\git.exe" `
               -ErrorAction SilentlyContinue | Sort-Object Name | Select-Object -Last 2
    if ($bundled) {
        $env:PATH = "$($bundled.DirectoryName);$env:PATH"
        $git = Get-Command git -ErrorAction SilentlyContinue
    }
}

if (-not $git) {
    Exit-WithError "Git not found. Install GitHub Desktop (https://desktop.github.com) or Git for Windows (https://git-scm.com) and re-run this script."
}

# Create base directory
if (-not (Test-Path $BASE)) {
    New-Item -ItemType Directory -Path $BASE | Out-Null
    Write-Host "Created $BASE"
}

# Clone repos
$cloneErrors = 0

foreach ($repo in $repos) {
    if (Test-Path (Join-Path $repo.Path ".git")) {
        Write-Host "$($repo.Name) already cloned, skipping"
    } else {
        Write-Host "Cloning $($repo.Name)..."
        git clone $repo.Url $repo.Path 2>&1
        if ($LASTEXITCODE -ne 0) {
            Write-Error "Failed to clone $($repo.Name). Check your GitHub access and try again."
            $cloneErrors++
        }
    }
}

if ($cloneErrors -gt 0) {
    Exit-WithError "$cloneErrors repo(s) failed to clone. Fix the errors above before continuing."
}

# Obsidian symlink
# The vault lives at C:\DalFSAE\ but .obsidian config is tracked inside docs\
$link = "$BASE\.obsidian"
$target = "$BASE\docs\.obsidian"

if (Test-Path $link) {
    Write-Host ".obsidian link already exists, skipping"
} else {
    if (-not (Test-Path $target)) {
        Exit-WithError ".obsidian config not found at $target. Is the docs repo cloned correctly?"
    }
    New-Item -ItemType Junction -Path $link -Target $target | Out-Null
    Write-Host "Linked .obsidian"
}

# Done
Write-Host ""
Write-Host "Setup complete."
Write-Host ""
Write-Host "Next steps:"
Write-Host "  1. Install Obsidian: https://obsidian.md/download"
Write-Host "  2. Open Obsidian -> 'Open folder as vault' -> select C:\DalFSAE"
Write-Host "  3. To work on vehicles CAD, open SolidWorks from $BASE\vehicles\"
Write-Host ""

function Exit-WithError {
    param([string]$Message, [int]$Code = 1)
    Write-Error $Message
    Write-Host ""
    Write-Host "Press any key to close..."
    $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
    exit $Code
}

