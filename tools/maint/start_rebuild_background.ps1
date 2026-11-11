[CmdletBinding()]
param(
    [ValidateSet("full", "cohort", "classifier", "semantic", "profiles", "emotes")]
    [string]$Mode = "full",
    [switch]$NoPrompt
)

$ErrorActionPreference = "Stop"

$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
Set-Location $Root

if (-not $NoPrompt) {
    Write-Host "NoLifeChatter artifact rebuild ($Mode mode)"
    Write-Host ""
    Write-Host "full       = classifier, style profiles, semantic vectors, message index, claims, smoke"
    Write-Host "cohort     = full shared-cohort rebuild, including user-claim profiles"
    Write-Host "classifier = classifier + style profiles only"
    Write-Host "semantic   = semantic vectors + message index only"
    Write-Host "profiles   = user-claim profiles for the top 40 active authors"
    Write-Host "emotes     = top-up 2,000 emotes toward 160 usage contexts"
    Write-Host ""
    Write-Host "This starts in the background and writes logs to data\unsynced."
    $answer = Read-Host "Type YES to start, or anything else to cancel"
    if ($answer -cne "YES") {
        Write-Host "Cancelled."
        exit 0
    }
}

$Py = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Py)) {
    $Py = "python"
}

$LogDir = Join-Path $Root "data\unsynced"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

$Stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$Stdout = Join-Path $LogDir "rebuild_persona_artifacts_${Mode}_${Stamp}.log"
$Stderr = Join-Path $LogDir "rebuild_persona_artifacts_${Mode}_${Stamp}.err.log"
$PidFile = Join-Path $LogDir "rebuild_persona_artifacts_${Mode}_${Stamp}.pid"
$Runner = Join-Path $LogDir "rebuild_persona_artifacts_${Mode}_${Stamp}.cmd"

$ScriptArgs = switch ($Mode) {
    "cohort" {
        @(
            "tools\build\rebuild_persona_artifacts.py",
            "--semantic-unit", "utterance", "--continue-on-error",
            "--no-message-index-force",
            "--profile-roster", "40", "--profile-cap", "12",
            "--profile-batch-size", "12"
        )
    }
    "profiles" {
        @(
            "tools\build\build_user_profiles.py", "--roster", "40",
            "--cap", "12", "--batch-size", "12"
        )
    }
    "emotes" {
        @(
            "tools\build\build_emote_semantics.py", "--top", "2000",
            "--contexts", "160"
        )
    }
    default {
        $ArgsForPipeline = @(
            "tools\build\rebuild_persona_artifacts.py",
            "--semantic-unit", "utterance",
            "--continue-on-error"
        )
        if ($Mode -eq "classifier") {
            $ArgsForPipeline += @(
                "--skip-embeddings", "--skip-fact-bank",
                "--skip-trait-smoke"
            )
        } elseif ($Mode -eq "semantic") {
            $ArgsForPipeline += @(
                "--skip-classifier", "--skip-style-profiles",
                "--skip-fact-bank"
            )
        }
        $ArgsForPipeline
    }
}

$Header = @(
    "@echo off",
    "cd /d ""$Root""",
    "echo NoLifeChatter artifact rebuild > ""$Stdout""",
    "echo mode=$Mode >> ""$Stdout""",
    "echo started=$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') >> ""$Stdout""",
    "echo cwd=$Root >> ""$Stdout""",
    "echo python=$Py >> ""$Stdout""",
    "echo args=$($ScriptArgs -join ' ') >> ""$Stdout""",
    "echo. >> ""$Stdout""",
    """$Py"" $($ScriptArgs -join ' ') >> ""$Stdout"" 2>> ""$Stderr""",
    "set ""REBUILD_EXIT=%ERRORLEVEL%""",
    "echo. >> ""$Stdout""",
    "echo exit_code=%REBUILD_EXIT% >> ""$Stdout""",
    "exit /b %REBUILD_EXIT%"
)
Set-Content -Path $Runner -Value $Header -Encoding ASCII

$Proc = Start-Process `
    -FilePath "cmd.exe" `
    -ArgumentList @("/c", "`"$Runner`"") `
    -WorkingDirectory $Root `
    -WindowStyle Hidden `
    -PassThru

Set-Content -Path $PidFile -Value $Proc.Id -Encoding ASCII

Write-Host "Started rebuild process $($Proc.Id)."
Write-Host "stdout: $Stdout"
Write-Host "stderr: $Stderr"
Write-Host "pid:    $PidFile"
Write-Host "runner: $Runner"
