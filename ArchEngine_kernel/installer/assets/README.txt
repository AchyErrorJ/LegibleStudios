ArchEngine Installer Assets
===========================

Required Files:
--------------

icon.ico
  - Application icon for the installer and shortcuts
  - Recommended sizes: 16x16, 32x32, 48x48, 64x64, 128x128, 256x256 (multi-resolution)
  - Must be in ICO format

  To create an icon from an existing image:
  - Online: Use https://convertio.co/png-ico/ or similar
  - Windows: Use Visual Studio's image editor
  - Extract from EXE: Use Resource Hacker or similar tool

Optional Files:
--------------

installer_banner.bmp (164x314 pixels)
  - Left panel image shown on welcome/finish pages
  - If not provided, Inno Setup uses default styling

installer_small.bmp (55x55 pixels)
  - Small image shown in top right corner during installation
  - If not provided, Inno Setup uses default styling

To use custom images, add these lines to ArchEngine.iss [Setup] section:
  WizardImageFile=assets\installer_banner.bmp
  WizardSmallImageFile=assets\installer_small.bmp
