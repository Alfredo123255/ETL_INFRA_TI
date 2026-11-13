[CmdletBinding()]
param(
    [ValidateSet('equipos','listar','retirar','restaurar')]
    [string]$Accion = 'listar',
    [string]$Equipo,
    [ValidateSet('cpu','ram','disco','fuente_poder','ventilador','tarjeta_red','controladora_raid','fuente','psu','fan','nic','raid','memoria')]
    [string]$Tipo,
    [int[]]$Numero = @(),
    [switch]$Todos,
    [switch]$VistaPrevia,
    [switch]$Reiniciar
)
$ErrorActionPreference = 'Stop'
$raiz = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$python = Join-Path $raiz '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) { throw 'No existe el Python de .venv. Instala primero las dependencias del proyecto.' }
if ($Accion -ne 'equipos' -and [string]::IsNullOrWhiteSpace($Equipo)) { throw 'Indica -Equipo con el nombre de la carpeta dentro de data.' }
if ($Reiniciar -and ($Accion -notin @('retirar','restaurar') -or $VistaPrevia)) { throw '-Reiniciar solo corresponde a retirar o restaurar, sin -VistaPrevia.' }

# Recuperar el comando en memoria permite reiniciar solo ese agente, sin copiar sus claves a archivos.
$procesoAgente = $null
if ($Reiniciar) {
    if ($Equipo -notmatch '^[A-Za-z0-9_-]+$') { throw 'Nombre de equipo inválido.' }
    $carpeta = [IO.Path]::GetFullPath((Join-Path (Join-Path $raiz 'data') $Equipo))
    $coincidencias = @(Get-CimInstance Win32_Process | Where-Object {
        if ($_.Name -notlike 'python*' -or $_.CommandLine -notmatch 'run_responder\.py') { return $false }
        $m = [regex]::Match($_.CommandLine, '--data-dir(?:=|\s+)(?:"([^"]+)"|([^\s"]+))')
        if (-not $m.Success) { return $false }
        $directorio = if ($m.Groups[1].Success) { $m.Groups[1].Value } else { $m.Groups[2].Value }
        [IO.Path]::GetFullPath($directorio).TrimEnd('\') -eq $carpeta.TrimEnd('\')
    })
    if ($coincidencias.Count -gt 1) { throw 'Hay varios procesos para este agente. Detén los duplicados antes de editar la captura.' }
    if ($coincidencias.Count -eq 1) {
        $procesoAgente = $coincidencias[0]
        if (-not $procesoAgente.ExecutablePath) { throw 'No se puede determinar el ejecutable del agente; no se modificó la captura.' }
        $argumentosAgente = [regex]::Replace($procesoAgente.CommandLine, '^(?:"[^"]+"|\S+)\s*', '')
    }
}
$argumentos = @('-B', (Join-Path $PSScriptRoot 'componentes_snmp.py'), $Accion.ToLowerInvariant())
if ($Equipo) { $argumentos += @('--equipo', $Equipo) }
if ($Tipo) { $argumentos += @('--tipo', $Tipo.ToLowerInvariant()) }
if ($Numero.Count) { $argumentos += '--numero'; $argumentos += @($Numero | ForEach-Object { [string]$_ }) }
if ($Todos) { $argumentos += '--todos' }
if ($VistaPrevia) { $argumentos += '--vista-previa' }
if ($Reiniciar -and $null -ne $procesoAgente) {
    # Windows impide reemplazar un archivo que snmpsim mantiene abierto.
    # Validar primero; detener solo después de saber que la operación es admisible.
    & $python @argumentos --vista-previa | Out-Null
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    Stop-Process -Id $procesoAgente.ProcessId -ErrorAction Stop
    $limite = [DateTime]::UtcNow.AddSeconds(10)
    while (Get-Process -Id $procesoAgente.ProcessId -ErrorAction SilentlyContinue) {
        if ([DateTime]::UtcNow -gt $limite) { throw 'El agente no se detuvo; no se modificó su captura.' }
        Start-Sleep -Milliseconds 100
    }
}
$codigo = 1
try {
    & $python @argumentos
    $codigo = $LASTEXITCODE
} finally {
    # Arrancar de nuevo también si la escritura falla; nunca dejarlo detenido por ese error.
    if ($Reiniciar -and $null -ne $procesoAgente) {
        $logDir = Join-Path $raiz 'logs\componentes_snmp'
        New-Item -ItemType Directory -Path $logDir -Force | Out-Null
        $nuevo = Start-Process -FilePath $procesoAgente.ExecutablePath -ArgumentList $argumentosAgente `
            -WorkingDirectory $raiz -WindowStyle Hidden -PassThru `
            -RedirectStandardOutput (Join-Path $logDir "$Equipo.out.log") `
            -RedirectStandardError (Join-Path $logDir "$Equipo.err.log")
        Start-Sleep -Seconds 2
        $nuevo.Refresh()
        if ($nuevo.HasExited) { throw 'El agente no pudo arrancar. Revisa logs\componentes_snmp y vuelve a iniciarlo; el respaldo se conserva.' }
        Write-Host "Agente $Equipo reiniciado. Los demás agentes se conservaron."
    }
}
if ($codigo -ne 0) { exit $codigo }
if ($Reiniciar -and $null -eq $procesoAgente) {
    Write-Warning "La captura se guardó, pero $Equipo no estaba ejecutándose. Inícialo para que responda con estos datos."
}
