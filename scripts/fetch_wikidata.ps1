# PowerShell equivalent of fetch_wikidata.py (for machines without Python).
# Runs every scripts/sparql/*.rq against WDQS and writes data/raw/wikidata_<date>.json.
# Usage:  powershell -ExecutionPolicy Bypass -File scripts\fetch_wikidata.ps1
$root = Split-Path -Parent $PSScriptRoot
$t = Get-Content "$root\data\seed\wikidata_targets.json" -Raw -Encoding UTF8 | ConvertFrom-Json
$qids = [ordered]@{}
foreach ($g in "items", "events", "persons", "places") {
    if ($t.$g) { $t.$g.PSObject.Properties | Where-Object { -not $_.Name.StartsWith("_") } | ForEach-Object { $qids[$_.Name] = $_.Value } }
}
$values = (($qids.Values | Sort-Object -Unique) | ForEach-Object { "wd:$_" }) -join " "
$headers = @{ "User-Agent" = "GeoChronosPOC/0.1 (research prototype)"; "Accept" = "application/sparql-results+json" }
$now = (Get-Date).ToUniversalTime()
$snap = [ordered]@{
    endpoint     = "https://query.wikidata.org/sparql"
    retrieved_at = $now.ToString("yyyy-MM-ddTHH:mm:ss+00:00")
    license      = "CC0 1.0 (Wikidata structured data)"
    fetched_with = "scripts/fetch_wikidata.ps1"
    targets      = $qids
    queries      = [ordered]@{}
}
foreach ($f in Get-ChildItem "$root\scripts\sparql\*.rq" | Sort-Object Name) {
    $sparql = (Get-Content $f.FullName -Raw -Encoding UTF8).Replace("{{VALUES}}", $values)
    $body = "query=" + [uri]::EscapeDataString($sparql)
    $resp = Invoke-WebRequest -UseBasicParsing -Method Post -Uri $snap.endpoint -Headers $headers -Body $body `
        -ContentType "application/x-www-form-urlencoded" -TimeoutSec 120
    $txt = [System.Text.Encoding]::UTF8.GetString($resp.RawContentStream.ToArray())
    $snap.queries[$f.BaseName] = [ordered]@{ sparql = $sparql; results = ($txt | ConvertFrom-Json) }
    Write-Output ("{0}: {1} rows" -f $f.BaseName, $snap.queries[$f.BaseName].results.results.bindings.Count)
    Start-Sleep -Seconds 2   # be polite to WDQS
}
New-Item -ItemType Directory -Force "$root\data\raw" | Out-Null
$out = "$root\data\raw\wikidata_$($now.ToString('yyyy-MM-dd')).json"
[System.IO.File]::WriteAllText($out, ($snap | ConvertTo-Json -Depth 30), (New-Object System.Text.UTF8Encoding($false)))
Write-Output "wrote $out"
