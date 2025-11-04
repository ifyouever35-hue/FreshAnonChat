# Останавливает и отключает службы Postgres в Windows (опционально)
$services = Get-Service | Where-Object { $_.Name -match '^postgres' -or $_.DisplayName -match 'PostgreSQL' }
foreach ($s in $services) {
    try {
        if ($s.Status -eq 'Running') { Stop-Service -Name $s.Name -Force -ErrorAction Stop }
        Set-Service -Name $s.Name -StartupType Disabled -ErrorAction Stop
        Write-Host "Отключено: $($s.Name)"
    } catch { Write-Warning "Не удалось обработать $($s.Name): $_" }
}
Write-Host "Готово."
