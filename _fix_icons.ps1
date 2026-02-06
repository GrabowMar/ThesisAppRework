$count = 0
Get-ChildItem -Path 'src\templates' -Recurse -Include '*.html' | ForEach-Object {
    $content = Get-Content $_.FullName -Raw -ErrorAction SilentlyContinue
    if ($content -and ($content -match 'fas fa-')) {
        $count++
        $newContent = $content -replace 'fas fa-', 'fa-solid fa-'
        Set-Content $_.FullName -Value $newContent -NoNewline
        Write-Output "Updated: $($_.Name)"
    }
}
Write-Output "Total HTML files updated: $count"

$jscount = 0
Get-ChildItem -Path 'src\static\js' -Include '*.js' | ForEach-Object {
    $content = Get-Content $_.FullName -Raw -ErrorAction SilentlyContinue
    if ($content -and ($content -match 'fas fa-')) {
        $jscount++
        $newContent = $content -replace 'fas fa-', 'fa-solid fa-'
        Set-Content $_.FullName -Value $newContent -NoNewline
        Write-Output "Updated JS: $($_.Name)"
    }
}
Write-Output "Total JS files updated: $jscount"
