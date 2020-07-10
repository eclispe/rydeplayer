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
* ```longmynd``` This section defines the paths for your Longmynd installation
  * ```binpath``` path to the Longmynd binary.
  * ```mediapath``` path to Longmynd's media FIFO, this will be auto-created if it doesn't exist.
  * ```statuspath``` path to Longmynd's status FIFO, this will be auto-created if it doesn't exist.
* ```ir``` This section defines the IR handset behaviour.
  * ```repeatFirst``` The time to wait before beginning to repeat an IR events in ms.
  * ```repeatDelay``` The time between repeats once repeating has begun in ms.
  * ```repeatReset``` How long to wait with no IR signals before requiring repeatFirst again in ms.
  * ```libraryPath``` Path to the directory containing the handset library files, see the Handset Configuration sestion for the library format
  * ```handsets``` A list of handset names to load from the library
* ```debug``` Debug options, for advanced users, do not rely on these, they may go away without notice
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
