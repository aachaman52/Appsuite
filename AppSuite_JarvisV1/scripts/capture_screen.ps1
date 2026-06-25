Add-Type -AssemblyName System.Windows.Forms, System.Drawing
$screen = [System.Windows.Forms.Screen]::PrimaryScreen
$bounds = $screen.Bounds
$bitmap = New-Object System.Drawing.Bitmap $bounds.Width, $bounds.Height
$graphics = [System.Drawing.Graphics]::FromImage($bitmap)
$graphics.CopyFromScreen($bounds.Location, [System.Drawing.Point]::Empty, $bounds.Size)
$bitmap.Save("c:\Users\Aachman_the_great\Desktop\New folder (2)\godot_screenshot.png")
$graphics.Dispose()
$bitmap.Dispose()
Write-Output "Screenshot saved successfully to c:\Users\Aachman_the_great\Desktop\New folder (2)\godot_screenshot.png"
