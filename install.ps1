Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RepoOwner = "evidentloop"
$RepoName = "sopify"
$AssetName = "install.ps1"
$SourceChannel = "dev"
$SourceRef = "main"

function Show-Usage {
  @"
Usage: install.ps1 [--target <host[:lang]>] [--with-evidentloop] [--ref <tag-or-branch>]

Install Sopify for a supported AI host.

Use `--target copilot` to bootstrap the current workspace and write Copilot
instruction files. For Codex / Claude, this installs the host prompt and
Sopify protocol kernel only. Project files are initialized later when you run `~go`
inside a workspace.

Options:
  --target <host[:lang]> Host and language to install, for example codex:zh-CN
                         or copilot.
  --workspace <path>     For copilot: target project directory (defaults to
                         current directory). For cursor: project-rule target
                         only; does not create `.sopify`. For other hosts:
                         advanced prewarm.
  --language <lang>      Copilot only: bootstrap output language (en-US/zh-CN).
  --no-copilot           Copilot only: skip Copilot instruction file
                         distribution.
  --with-evidentloop     Install the current EvidentLoop CLI and Skill from
                         official sources, or reuse healthy existing components.
                         Disabled by default.
  --verbose              Show full diagnostic install details.
  --ref <tag-or-branch>  Advanced: override the source ref.
  -h, --help             Show this help.
"@
}

function Fail-Install {
  param(
    [string]$Phase,
    [string]$ReasonCode,
    [string]$Detail,
    [string]$NextStep
  )

  [Console]::Error.WriteLine("Sopify install failed: $Detail")
  [Console]::Error.WriteLine("")
  [Console]::Error.WriteLine("Fix:")
  [Console]::Error.WriteLine("  $NextStep")
  [Console]::Error.WriteLine("")
  [Console]::Error.WriteLine("Diagnostics:")
  [Console]::Error.WriteLine("  reason_code: $ReasonCode")
  [Console]::Error.WriteLine("  phase: $Phase")
  exit 1
}

function Write-InstallStep {
  param([string]$Message)
  [Console]::Error.WriteLine("Sopify: $Message")
}

function Resolve-PythonCommand {
  $foundPythonCommand = $false
  $detectedPython = $null
  $pythonProbe = 'import sys; print(".".join(map(str, sys.version_info[:3]))); raise SystemExit(0 if sys.version_info >= (3, 11) else 1)'

  foreach ($candidateName in @("python3", "python", "py")) {
    $command = Get-Command $candidateName -ErrorAction SilentlyContinue
    if ($null -eq $command) {
      continue
    }
    $foundPythonCommand = $true
    $prefixArgs = if ($candidateName -eq "py") { @("-3") } else { @() }
    $probeArgs = @()
    $probeArgs += $prefixArgs
    $probeArgs += @("-c", $pythonProbe)
    $probeOutput = & $command.Path @probeArgs 2>$null
    $probeExitCode = $LASTEXITCODE
    $versionText = (($probeOutput | ForEach-Object { "$_" }) -join "").Trim()
    if ($null -eq $detectedPython -and -not [string]::IsNullOrWhiteSpace($versionText)) {
      $detectedPython = "$candidateName $versionText"
    }
    if ($probeExitCode -eq 0) {
      return @{
        executable = $command.Path
        prefixArgs = $prefixArgs
      }
    }
  }

  if (-not $foundPythonCommand) {
    $reasonCode = "MISSING_PYTHON"
    $detail = "Sopify needs Python 3.11 or newer, but no Python command was found. Nothing was downloaded or installed."
  } elseif (-not [string]::IsNullOrWhiteSpace($detectedPython)) {
    $reasonCode = "UNSUPPORTED_PYTHON"
    $detail = "Sopify needs Python 3.11 or newer. Found: $detectedPython. Nothing was downloaded or installed."
  } else {
    $reasonCode = "UNSUPPORTED_PYTHON"
    $detail = "A Python command was found, but it could not run Python 3.11 or newer. Nothing was downloaded or installed."
  }
  Fail-Install -Phase "preflight" -ReasonCode $reasonCode -Detail $detail -NextStep "Install Python 3.11 or newer, then rerun the same command."
}

$forwardedArgs = New-Object System.Collections.Generic.List[string]
$refOverride = $null
for ($i = 0; $i -lt $args.Count; $i++) {
  $arg = $args[$i]
  switch -Regex ($arg) {
    '^(-h|--help)$' {
      Show-Usage
      exit 0
    }
    '^--ref=(.+)$' {
      $refOverride = $Matches[1]
      $forwardedArgs.Add($arg)
      continue
    }
    '^--ref$' {
      if ($i + 1 -ge $args.Count) {
        Fail-Install -Phase "input" -ReasonCode "MISSING_REF_VALUE" -Detail "`--ref` requires a value." -NextStep "Pass --ref <tag-or-branch>, or omit the flag."
      }
      $refOverride = $args[$i + 1]
      $forwardedArgs.Add($arg)
      $forwardedArgs.Add($args[$i + 1])
      $i++
      continue
    }
    default {
      $forwardedArgs.Add($arg)
    }
  }
}

$resolvedRef = if ([string]::IsNullOrWhiteSpace($refOverride)) { $SourceRef } else { $refOverride }
if ([string]::IsNullOrWhiteSpace($resolvedRef)) {
  Fail-Install -Phase "input" -ReasonCode "MISSING_SOURCE_REF" -Detail "No source ref was resolved for the installer." -NextStep "Retry with --ref <tag-or-branch>, or inspect the release asset rendering."
}

Write-InstallStep -Message "Checking requirements..."
$pythonCommand = Resolve-PythonCommand
$tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("sopify-install-" + [System.Guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $tempRoot | Out-Null

try {
  $archiveUrl = "https://codeload.github.com/$RepoOwner/$RepoName/zip/$resolvedRef"
  $archivePath = Join-Path $tempRoot "source.zip"

  Write-InstallStep -Message "Downloading Sopify source ($resolvedRef)..."
  try {
    Invoke-WebRequest -Uri $archiveUrl -OutFile $archivePath | Out-Null
  } catch {
    Fail-Install -Phase "download" -ReasonCode "SOURCE_FETCH_FAILED" -Detail "Failed to download source archive: $archiveUrl" -NextStep "Check network access, verify the ref exists, or use the inspect-first path."
  }

  Write-InstallStep -Message "Unpacking installer..."
  try {
    Expand-Archive -Path $archivePath -DestinationPath $tempRoot -Force
  } catch {
    Fail-Install -Phase "unpack" -ReasonCode "SOURCE_EXTRACT_FAILED" -Detail "Failed to extract source archive: $archivePath" -NextStep "Retry the installer or inspect the downloaded archive locally."
  }

  $sourceDir = Get-ChildItem -Path $tempRoot -Directory | Where-Object { $_.FullName -ne $tempRoot } | Select-Object -First 1
  if ($null -eq $sourceDir) {
    Fail-Install -Phase "unpack" -ReasonCode "SOURCE_ROOT_MISSING" -Detail "The extracted source archive did not contain a repository root directory." -NextStep "Retry the installer or inspect the downloaded archive locally."
  }

  $entrypoint = Join-Path $sourceDir.FullName "scripts/install_sopify.py"
  if (-not (Test-Path -LiteralPath $entrypoint)) {
    Fail-Install -Phase "unpack" -ReasonCode "INSTALL_ENTRYPOINT_MISSING" -Detail "Missing install entrypoint inside source archive: $entrypoint" -NextStep "Retry the installer or inspect the downloaded archive locally."
  }

  $pythonArgs = @()
  $pythonArgs += $pythonCommand.prefixArgs
  Write-InstallStep -Message "Running installer..."
  $pythonArgs += @(
    $entrypoint,
    "--source-channel",
    $SourceChannel,
    "--source-resolved-ref",
    $resolvedRef,
    "--source-asset-name",
    $AssetName
  )
  $pythonArgs += $forwardedArgs.ToArray()

  & $pythonCommand.executable @pythonArgs
  exit $LASTEXITCODE
} finally {
  if (Test-Path -LiteralPath $tempRoot) {
    Remove-Item -LiteralPath $tempRoot -Recurse -Force
  }
}
