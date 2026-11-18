<#
.SYNOPSIS
  One-step setup on a fresh Windows PC: find or install Miniforge, then run
  install.py with it.

.DESCRIPTION
  Start it through bootstrap.cmd (double-click, or from a prompt), which runs
  this script past the execution policy that blocks downloaded scripts.

  1. Unblocks the files extracted from the downloaded zip.
  2. Uses an existing Miniforge/conda install if there is one; otherwise
     downloads the latest Miniforge from GitHub, checks its SHA-256 and
     installs it for the current user (no administrator rights needed).
  3. Runs install.py with that installation's python.exe. Every argument
     other than --miniforge-dir is passed to install.py unchanged.

.EXAMPLE
  bootstrap.cmd
  bootstrap.cmd --mpc-host 192.168.0.1 --from-mpc
  bootstrap.cmd --wheels E:\PythonPackages
  bootstrap.cmd --miniforge-dir D:\miniforge3 --skip-autoscript

.NOTES
  Works in Windows PowerShell 5.1 (Windows 10/11 default) and PowerShell 7.
  There is deliberately no param() block: arguments such as --from-mpc must
  reach install.py as they are, not be bound to PowerShell parameters.
#>

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'   # Invoke-WebRequest is far faster without its progress bar
[Net.ServicePointManager]::SecurityProtocol =
    [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
# Behind an authenticating proxy, pass the Windows login on.
if ([Net.WebRequest]::DefaultWebProxy) {
    [Net.WebRequest]::DefaultWebProxy.Credentials = [Net.CredentialCache]::DefaultNetworkCredentials
}

$RepoDir = $PSScriptRoot

function Say([string]$Message)  { Write-Host "[bootstrap] $Message" -ForegroundColor Cyan }
function Warn([string]$Message) { Write-Host "[bootstrap] $Message" -ForegroundColor Yellow }
function Fail([string]$Message) { Write-Host "[bootstrap] $Message" -ForegroundColor Red; exit 1 }

# ---------------------------------------------------------------------------
# Arguments: --miniforge-dir is ours, everything else goes to install.py.
# ---------------------------------------------------------------------------
$MiniforgeDir = $null
$Forward = @()
for ($i = 0; $i -lt $args.Count; $i++) {
    $arg = [string]$args[$i]
    if ($arg -ieq '--miniforge-dir' -or $arg -ieq '-MiniforgeDir') {
        if ($i + 1 -ge $args.Count) { Fail "$arg needs a folder." }
        $i++
        $MiniforgeDir = [string]$args[$i]
    } else {
        $Forward += $arg
    }
}

# ---------------------------------------------------------------------------
# Files from a downloaded zip carry a "came from the internet" mark that makes
# Windows block or warn on them. Remove it from this folder only.
# ---------------------------------------------------------------------------
Get-ChildItem -Path $RepoDir -Recurse -File | Unblock-File -ErrorAction SilentlyContinue

# ---------------------------------------------------------------------------
# Miniforge
# ---------------------------------------------------------------------------
function Test-CondaRoot([string]$Dir) {
    return [bool]$Dir -and
           (Test-Path -LiteralPath (Join-Path $Dir 'python.exe')) -and
           (Test-Path -LiteralPath (Join-Path $Dir 'Scripts\conda.exe'))
}

function Find-CondaRoot {
    $candidates = @()
    # An activated prompt sets CONDA_EXE to <root>\Scripts\conda.exe.
    if ($env:CONDA_EXE) { $candidates += Split-Path (Split-Path $env:CONDA_EXE) }
    # <root>\Scripts\conda.exe or <root>\condabin\conda.bat, if on PATH.
    foreach ($name in 'conda.exe', 'conda.bat') {
        $cmd = Get-Command $name -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($cmd) { $candidates += Split-Path (Split-Path $cmd.Source) }
    }
    # Usual install folders (Miniforge sometimes installs as "Miniconda3").
    $candidates += @(
        "$env:USERPROFILE\miniforge3", "$env:LOCALAPPDATA\miniforge3", "$env:ProgramData\miniforge3",
        "$env:SystemDrive\miniforge3",
        "$env:USERPROFILE\miniconda3", "$env:ProgramData\miniconda3",
        "$env:USERPROFILE\anaconda3", "$env:ProgramData\anaconda3"
    )
    foreach ($dir in $candidates) {
        if (Test-CondaRoot $dir) { return (Resolve-Path -LiteralPath $dir).Path }
    }
    return $null
}

function Install-Miniforge([string]$Dir) {
    try {
        Install-MiniforgeFromGitHub $Dir
    } catch {
        Fail ("Could not download or install Miniforge: $($_.Exception.Message)`n" +
              "  Install it yourself from https://conda-forge.org/download/ and re-run.")
    }
}

function Install-MiniforgeFromGitHub([string]$Dir) {
    Say "Looking up the latest Miniforge release..."
    $release = Invoke-RestMethod -Uri 'https://api.github.com/repos/conda-forge/miniforge/releases/latest' `
                                 -Headers @{ 'User-Agent' = 'install_fibsem-os_win11' }
    # x86_64 also on ARM64 Windows (it runs emulated): fibsemOS's Qt and OpenCV
    # wheels are x86_64-only on Windows. The versioned file is the one that
    # comes with a .sha256.
    $name  = "Miniforge3-$($release.tag_name)-Windows-x86_64.exe"
    $exe   = $release.assets | Where-Object { $_.name -eq $name } | Select-Object -First 1
    $sum   = $release.assets | Where-Object { $_.name -eq "$name.sha256" } | Select-Object -First 1
    if (-not $exe -or -not $sum) { Fail "Release $($release.tag_name) has no $name (+ .sha256)." }

    $installer = Join-Path $env:TEMP $name
    $sumFile   = "$installer.sha256"
    Say "Downloading $name ($([math]::Round($exe.size / 1MB)) MB)..."
    Invoke-WebRequest -Uri $exe.browser_download_url -OutFile $installer -UseBasicParsing
    Invoke-WebRequest -Uri $sum.browser_download_url -OutFile $sumFile -UseBasicParsing

    $expected = ((Get-Content -LiteralPath $sumFile -Raw).Trim() -split '\s+')[0].ToLowerInvariant()
    $actual   = (Get-FileHash -LiteralPath $installer -Algorithm SHA256).Hash.ToLowerInvariant()
    Remove-Item -LiteralPath $sumFile -ErrorAction SilentlyContinue
    if ($actual -ne $expected) {
        Remove-Item -LiteralPath $installer -ErrorAction SilentlyContinue
        Fail "Checksum mismatch for $name (expected $expected, got $actual). Not installing."
    }
    Say "Checksum OK."

    Say "Installing Miniforge $($release.tag_name) to $Dir (current user only; ~2 minutes)..."
    # NSIS options: /D= must come last and must not be quoted.
    $options = "/InstallationType=JustMe /RegisterPython=0 /AddToPath=0 /S /D=$Dir"
    try {
        $proc = Start-Process -FilePath $installer -ArgumentList $options -Wait -PassThru
    } catch {
        Fail ("Windows would not start the installer ($($_.Exception.Message)). " +
              "If this PC blocks downloaded programs, install Miniforge through IT, then re-run.")
    }
    Remove-Item -LiteralPath $installer -ErrorAction SilentlyContinue
    if ($proc.ExitCode -ne 0 -or -not (Test-CondaRoot $Dir)) {
        Fail "The Miniforge installer failed (exit code $($proc.ExitCode))."
    }
    Say "Miniforge installed."
}

if ($MiniforgeDir) {
    $root = $MiniforgeDir
    if (-not (Test-CondaRoot $root)) { Install-Miniforge $root }
} else {
    $root = Find-CondaRoot
    if ($root) {
        Say "Using the existing installation in $root"
    } else {
        $root = "$env:USERPROFILE\miniforge3"
        # conda does not support install paths with spaces.
        if ($root -match ' ') {
            $root = "$env:SystemDrive\miniforge3"
            Warn "Your profile path has a space in it; installing to $root instead."
        }
        Install-Miniforge $root
    }
}
$root = (Resolve-Path -LiteralPath $root).Path

# ---------------------------------------------------------------------------
# Run install.py with this installation, its tools first on PATH (as
# `conda activate base` would set it) so install.py finds conda/mamba.
# ---------------------------------------------------------------------------
$env:Path = (@(
    $root, "$root\Library\mingw-w64\bin", "$root\Library\usr\bin", "$root\Library\bin",
    "$root\Scripts", "$root\bin", "$root\condabin"
) -join ';') + ';' + $env:Path

$python = Join-Path $root 'python.exe'
Say "Running install.py $($Forward -join ' ')"
& $python (Join-Path $RepoDir 'install.py') $Forward
$code = $LASTEXITCODE

if ($code -eq 0) {
    # The env install.py used: --env if given, else config.json's, else the default.
    $envName = 'fibsem-os'
    $config = Join-Path $RepoDir 'config.json'
    if (Test-Path -LiteralPath $config) {
        $fromConfig = (Get-Content -LiteralPath $config -Raw | ConvertFrom-Json).env_name
        if ($fromConfig) { $envName = $fromConfig }
    }
    $at = [array]::IndexOf($Forward, '--env')
    if ($at -ge 0 -and $at + 1 -lt $Forward.Count) { $envName = $Forward[$at + 1] }
    Say "Next time, open the Miniforge Prompt (Start menu) or run:"
    Say "  `"$root\Scripts\activate.bat`" $envName"
}
exit $code
