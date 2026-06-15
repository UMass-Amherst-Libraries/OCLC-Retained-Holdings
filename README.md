# OCLC-Retained-Holdings
Copyright (C) 2026  Amelia Sutton

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  

See the file "[LICENSE](LICENSE)" for more details.

## Requirements
- Python 3.10+
- pandas
- dotenv
- tqdm
- aiohttp
- sv_ttk
- numpy

## Setup (Basic)
- Download the program files from github.
- Extract the files to a folder where you plan to run the script.
- In that directory create a subfolder "Output"
- Open terminal in the program folder
- Run ```pip install -r requirements.txt```

## Configuration
In the main program folder, create a file named ```.env``` with the following fields:
> WSKEY = {Your WSKEY}
> 
> SECRET = {Your SECRET}
> 
> SCOPE = WorldCatMetadataAPI
> 
> TOKEN_URL = https://oauth.oclc.org/token
> 
> API_URL = https://metadata.api.oclc.org/worldcat/search/bibs-retained-holdings
>
> LOG_PATH = {Folder where Logs should be saved}
> 
> EAST_SYMBOLS = EAST_symbols.txt

## Usage
- Run the program
  - Using terminal -> Open terminal in the program folder and run ```python main.py```
- Press "Select .csv file"
  - Find and select your input file in the file system dialogue
- Press "Retrieve and Save OCLC Retained Holdings"
  - Once finished a popup window will appear with the message "Results Saved!"