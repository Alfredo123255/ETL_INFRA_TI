[CmdletBinding()]
param(
    [ValidateSet('equipos','listar','retirar','restaurar')]
    [string]$Accion = 'listar',
    [string]$Equipo,
    [ValidateSet('cpu','ram','disco','fuente_poder','ventilador','tarjeta_red','controladora_raid','fuente','psu','fan','nic','raid','memoria')]
    [string]$Tipo,
    [int[]]$Numero = @(),
    [switch]$Todos,
    [switch]$VistaPrevia
)
$ErrorActionPreference = 'Stop'
$raiz = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$python = Join-Path $raiz '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) { throw 'No existe el Python de .venv. Instala primero las dependencias del proyecto.' }
if ($Accion -ne 'equipos' -and [string]::IsNullOrWhiteSpace($Equipo)) { throw 'Indica -Equipo con el nombre de la carpeta dentro de data.' }

# No se consultan, detienen ni arrancan procesos. snmpsim detecta el cambio
# de la captura por su fecha de modificación en la siguiente consulta.
$argumentos = @('-B', (Join-Path $PSScriptRoot 'componentes_snmp.py'), $Accion.ToLowerInvariant())
if ($Equipo) { $argumentos += @('--equipo', $Equipo) }
if ($Tipo) { $argumentos += @('--tipo', $Tipo.ToLowerInvariant()) }
if ($Numero.Count) { $argumentos += '--numero'; $argumentos += @($Numero | ForEach-Object { [string]$_ }) }
if ($Todos) { $argumentos += '--todos' }
if ($VistaPrevia) { $argumentos += '--vista-previa' }
& $python @argumentos
exit $LASTEXITCODE
