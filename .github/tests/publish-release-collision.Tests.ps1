Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

function Assert-NoReleaseCollision([object]$Response, [string]$Tag) {
  if ($Response -isnot [array] -or $Response.Count -gt 100) {
    throw 'GitHub returned an unexpected Releases API response'
  }
  $releases = [object[]]$Response
  foreach ($release in $releases) {
    $tagName = $release.PSObject.Properties['tag_name']
    if ($release -isnot [pscustomobject] -or
        $null -eq $tagName -or
        $tagName.Value -isnot [string] -or
        [string]::IsNullOrWhiteSpace($tagName.Value)) {
      throw 'GitHub returned a malformed Release entry'
    }
    if ([string]::Equals(
        $tagName.Value,
        $Tag,
        [StringComparison]::Ordinal
    )) {
      throw "destination Release $Tag already exists"
    }
  }
  $releases.Count
}

function Invoke-TestJson([string]$Uri) {
  $response = Invoke-RestMethod -Method Get -Uri $Uri
  Write-Output -NoEnumerate $response
}

function Assert-Throws([scriptblock]$Action, [string]$Message) {
  try {
    & $Action | Out-Null
  } catch {
    if ($_.Exception.Message -cne $Message) {
      throw "Expected '$Message', got '$($_.Exception.Message)'"
    }
    return
  }
  throw "Expected failure: $Message"
}

$tag = 'v1.2.3'
$responses = @(
  '[]'
  '[{"tag_name":"v1.2.3\u0000"}]'
  '[{"tag_name":"v1.2.3"}]'
  '{"tag_name":"v9.9.9"}'
  '[{"name":"missing tag_name"}]'
  ('[' + ((1..101 | ForEach-Object {
    '{"tag_name":"v9.9.' + $_ + '"}'
  }) -join ',') + ']')
)

$probe = [Net.Sockets.TcpListener]::new([Net.IPAddress]::Loopback, 0)
$probe.Start()
$port = ([Net.IPEndPoint]$probe.LocalEndpoint).Port
$probe.Stop()

$listener = [Net.HttpListener]::new()
$listener.Prefixes.Add("http://127.0.0.1:$port/")
$listener.Start()
$server = Start-ThreadJob -ArgumentList $listener, $responses -ScriptBlock {
  param($Listener, $Bodies)
  foreach ($body in $Bodies) {
    $context = $Listener.GetContext()
    $bytes = [Text.Encoding]::UTF8.GetBytes($body)
    $context.Response.ContentType = 'application/json'
    $context.Response.ContentLength64 = $bytes.Length
    $context.Response.OutputStream.Write($bytes, 0, $bytes.Length)
    $context.Response.Close()
  }
}

try {
  $actual = foreach ($index in 0..($responses.Count - 1)) {
    Invoke-TestJson "http://127.0.0.1:$port/$index"
  }

  if ($actual[0] -isnot [array] -or $actual[0].Count -ne 0) {
    throw 'Invoke-RestMethod no longer preserves an empty JSON array as Object[]'
  }
  if ((Assert-NoReleaseCollision $actual[0] $tag) -ne 0) {
    throw 'An empty Releases response did not normalize to zero entries'
  }
  if ((Assert-NoReleaseCollision $actual[1] $tag) -ne 1) {
    throw 'A different Release did not normalize to one entry'
  }
  Assert-Throws {
    Assert-NoReleaseCollision $actual[2] $tag
  } "destination Release $tag already exists"
  Assert-Throws {
    Assert-NoReleaseCollision $actual[3] $tag
  } 'GitHub returned an unexpected Releases API response'
  Assert-Throws {
    Assert-NoReleaseCollision $actual[4] $tag
  } 'GitHub returned a malformed Release entry'
  Assert-Throws {
    Assert-NoReleaseCollision $actual[5] $tag
  } 'GitHub returned an unexpected Releases API response'
} finally {
  $listener.Stop()
  $listener.Close()
  Receive-Job -Job $server -Wait -AutoRemoveJob | Out-Null
}

'Release collision regression tests passed'
