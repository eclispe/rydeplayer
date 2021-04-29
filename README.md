# Ryde Player

This is the player and user interface application as part of the BATC ryde project. It allows the control of Longmynd compatible tuners using an IR remote control handset and on screen display on a Raspberry Pi 4.

The software is designed and tested on a Raspberry Pi 4 although it will likely run on older hardware this is unsupported. Primary target tuner hardware is the BATC MiniTiouner V2 although it should work with any Longmynd compatible hardware although some features may not be supported.

## Install

Install packaged dependencies:

```sudo apt-get install python3-pygame python3-vlc python3-yaml python3-evdev python3-pil vlc-plugin-base```

Install pyDispmanx driver from https://github.com/eclispe/pyDispmanx and ensure the .so file is in your PYTHONPATH

Install Longmynd. Currently recommending that you use this fork as it has fixes that have not been merged upstream yet: https://github.com/eclispe/longmynd

## Config Files
A complete sample YAML config file is provided as `config.sample.yaml`, this contains all currently configurable options. If some options are omitted from the config file then internal defaults will be used.
### Config file options
* ```configRev``` The config format revision of this file, if present but wrong the file will not load, if missing file will load with warning. Current revision is 2
* ```longmynd``` This section defines the paths for your Longmynd installation
  * ```binpath``` path to the Longmynd binary.
  * ```mediapath``` path to Longmynd's media FIFO, this will be auto-created if it doesn't exist.
  * ```statuspath``` path to Longmynd's status FIFO, this will be auto-created if it doesn't exist.
  * ```tstimeout``` TS timeout in ms, passed to longmynd with ```-r```, see longmynd manual for more details.
* ```bands```
  * Name of the band, you may have to put it in double quotes ```"``` if you want to use names with various caracters such as ```:``` in it. It is recommended that you add an anchor if you need to reference the band later, e.g. ```"LNB Low": &bandlnblow```
    * ```lofreq``` LO frequency value in kHz
    * ```loside``` Select either ```HIGH``` or ```LOW``` when using the difference mixing product where the LO is above or below the RF frequency respectively or ```SUM``` if using the sum mixing product.
    * ```pol``` Band polarity, selects bias voltage. Choose from ```NONE```, ```HORIZONTAL``` or ```VERTICAL```
    * ```port``` Band input port. Choose from ```TOP``` or ```BOTTOM```
    * ```gpioid``` Band GPIO ID, valid values are 0-7.
* ```presets```
  * Name of the preset, following the same naming rules as for bands above. It is also recommended you add an anchor to a preset to use as the default also similar to bands above, e.g. ```"QO-100 Beacon": &presetdefault```
    * ```freq``` Preset frequency to tune, this can either be a single frequency or a list of frequencies to enable frequency scanning
    * ```band``` Preset band, its recommended to use an alias to a band in the band library, e.g. ```band: *bandlnblow```
    * ```sr``` Preset symbol rate in kSps, this can either be a single symbol rate or a list of symbol rates to enable symbol rate scanning

* ```default```
  * Initial settings, its recommended to use an alias to a preset in the preset library, e.g. ```default: *presetdefault```
* ```ir``` This section defines the IR handset behaviour.
  * ```repeatFirst``` The time to wait before beginning to repeat an IR events in ms.
  * ```repeatDelay``` The time between repeats once repeating has begun in ms.
  * ```repeatReset``` How long to wait with no IR signals before requiring repeatFirst again in ms.
  * ```libraryPath``` Path to the directory containing the handset library files, see the Handset Configuration sestion for the library format
  * ```handsets``` A list of handset names to load from the library
* ```gpio``` This section defines the pins and other options for interacting with the Raspberry Pi GPIO.
  * ```repeatFirst``` The time to wait before beginning to repeat an GPIO button press event in ms.
  * ```repeatDelay``` The time between repeats once repeating has begun in ms.
  * ```rxGood``` The BCM pin number to output the reciver locked indication to. For example to output the signal on pin 7 set this to 4.
  * ```buttons``` A map of button names to BCM pin numbers.
  * ```switches``` Container for switch event to BCM pin number mappings.
    * ```highgoing``` A map of high going events to BCM pin numbers.
    * ```lowgoing``` A map of low going events to BCM pin numbers.
* ```osd``` This section contains the configuration for the on screen display
  * ```timers``` Contains deactiate timers for various triggers in seconds, ```0``` disables the initial event, ```null``` disables the auto deactivate
    * ```USERTRIGGER``` Activate triggered by user pressing select button
    * ```PROGRAMTRIGGER``` Activated when a new or different signal is received
  * ```active``` Contains a list of modules and their configurations for when the OSD is active. Include any modules from the list below that should be displayed in this mode.
    * ```MUTE``` Displays a mute icon when the player is muted. Set value to ```null``` for default size and location, use all sub elements to set size and location.
      * ```datum``` Where to measure the new location relative to. Options: ```TL``` Top Left, ```TC``` Top Centre, ```TR``` Top Right, ```CR``` Centre Right, ```CC``` Centre both, ```CL``` Centre Left, ```BL``` Bottom Left, ```BC``` Bottom Centre or ```BR``` Bottom Right.
      * ```x``` The fraction of the display height the left/right (depending on datum) of the module is from the left/right of the display, valid values 0-1 for edges or -0.5 to 0.5 for centres.
      * ```y``` Same as for ```x``` but what fraction of the display height is the top/bottom (depending on datum).
      * ```w``` The width of the module as a fraction of the display height, valid values 0-1.
      * ```x``` Same as for ```w``` but for module height.
    * ```MER``` Displays the MER of the current recived signal, size/location configuration the same as for ```MUTE```.
    * ```REPORT``` Displays the difference between the MER and the minimal viable MER for the current modulation and FEC, size/location configuration the same as for ```MUTE```.
    * ```PROGRAM``` Displays the service, provider, preset name, modulation type and transport stream PID details for the current signal, size/location configuration the same as for ```MUTE```.
  * ```inactive``` The same as the active list but for when the OSD is inactive.
* ```network``` This section contains the network control configuration
  * ```bindaddr``` The address of the local network interface use or '' to use all interfaces
  * ```port```  The TCP port number to use
* ```shutdownBehavior``` The default shutdown option when the power button is double pressed. Choose from ```APPSTOP``` or ```APPREST``` to stop the player or restart the player respectively.
* ```debug``` Debug options, for advanced users, do not rely on these, they may go away without notice
  * ```enableMenu``` Enable the debug menu entry
  * ```autoplay``` Auto play the stream on lock, should be set to True.
  * ```disableHardwareCodec``` Disable hardware decoder in VLC, recommend setting to True, uses more CPU but is more reliable at decoding.

### Handset Configuration
To configure a handset you need to add the handset configuration file to the handset library directory and add the filename (without the `.yaml` extension) to the main config file. Currently you also need to activate the driver listed in the handset file manually using the instructions in the Manual driver activation section.

#### Handset file options
A complete example handset file is available as handset.sample.yaml
* ```name``` The name of the new handset, this should be meaningful and unique
* ```driver``` The name of the driver used by this handset
* ```buttons``` A map of button names to scan codes

#### Manual driver activation
If you know which driver you need it can be enabled with ```sudo ir-keytable -p <driver name>```. Common values include rc-5, rc-6 and nec, a full list can be seen by running ```ir-keytable```. If you are unsure you can enable all drivers with ```sudo ir-keytable -p all``` although this is not recommended as a permanent solution due to the risk of code conflicts.

#### New handset setup procedure
Once you have the correct driver setup you should be able to see the IR codes when you run ```ir-keytable -t``` and press buttons on the  handset you should see something like this:
```
54132.040051: lirc protocol(nec): scancode = 0x40
54132.040074: event type EV_MSC(0x04): scancode = 0x40
54132.040074: event type EV_SYN(0x00).
```
Now press each button you wish to map on the handset and add the scancode to the new handset file. To access the core functionality you need to add at least the core 5 codes, `UP` or `DOWN`, `LEFT` or `RIGHT`, `SELECT`, `BACK` and `MENU` for each remote. The full list of supported codes is available in the sample handset file, it is recommended that you map all codes that are supported by your handset.

## Network Interface
The interface uses TCP sockets with JSON payloads, all requests and responses consist of a JSON object. All requests must contain a minimum of a ```request``` attribute string. All responses will contain a minimum of a ```success``` attribute boolean, if there is an error an ```error``` attribute string will be present.

The network interface is disabled by default and is only enabled if a bind address is specified in the config file. A very basic sample client is provided in ```networktest.py```.

### ```getBands```
The ```getBands``` request returns a ```bands``` attribute object containing the bands in the band library using the same format as the config file.

### ```setTune```
The ```setTune``` request accepts a ```tune``` attribute object containing a preset in the same format as the config file. The ```band``` attribute of the preset is in the same format as returned by the ```getBands``` request.

### ```setMute```
The ```setMute``` request accepts a ```mute``` attribute boolean for the new mute state.

### ```sendEvent```
The ```sendEvent``` request accepts an ```event``` attribute string containing the button event to trigger.

### ```debugFire```
The ```debugFire``` request accepts a ```function``` attribute string containing the name of the debug function, these are shown in the UI debug menu.

## Run
With both pyDispmanx and rydeplayer in the current directory or your ```PYTHONPATH``` and optionally a config.yaml in the current directory run:

```python3 -m rydeplayer```

You can also specify a config file path at the commandline:

```python3 -m rydeplayer ~/myconfig.yaml```

## License

Ryde Player provides a on screen interface and video player for Longmynd compatible tuners. 

Copyright (C) 2020  Tim Clark

This program is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version.

This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more details.

You should have received a copy of the GNU General Public License along with this program.  If not, see https://www.gnu.org/licenses/.
