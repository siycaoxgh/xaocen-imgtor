$ErrorActionPreference = 'Stop'

$project = Split-Path -Parent $PSScriptRoot
$version = '5.3.2'
$exeName = "XAOCEN-ImgTor-v$version.exe"
$release = Join-Path $project "release\v$version"
$portable = Join-Path $release "XAOCEN-ImgTor-v$version-portable"

New-Item -ItemType Directory -Force -Path $portable | Out-Null
Copy-Item -LiteralPath (Join-Path $project "dist\$exeName") -Destination $portable -Force
Copy-Item -LiteralPath (Join-Path $project 'README.md'), (Join-Path $project 'LICENSE'), (Join-Path $project 'NOTICE') -Destination $portable -Force
New-Item -ItemType Directory -Force -Path (Join-Path $portable 'docs') | Out-Null
Copy-Item -LiteralPath (Join-Path $project 'docs\FFMPEG_SETUP.md') -Destination (Join-Path $portable 'docs') -Force

$zip = Join-Path $release "XAOCEN-ImgTor-v$version-portable.zip"
if (Test-Path -LiteralPath $zip) {
    throw "Release archive already exists: $zip"
}
Compress-Archive -Path $portable -DestinationPath $zip -CompressionLevel Optimal

$iscc = Join-Path $env:LOCALAPPDATA 'Programs\Inno Setup 6\ISCC.exe'
if (-not (Test-Path -LiteralPath $iscc)) {
    throw 'Inno Setup 6 ISCC.exe was not found.'
}
& $iscc (Join-Path $project 'installer\XAOCEN-ImgTor-v5.3.2.iss')
if ($LASTEXITCODE -ne 0) {
    throw "Inno Setup failed with exit code $LASTEXITCODE"
}

Get-ChildItem -LiteralPath $release -Recurse -File |
    Select-Object FullName, Length, LastWriteTime
